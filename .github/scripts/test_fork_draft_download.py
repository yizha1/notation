# Copyright The Notary Project Authors.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Actual draft download credential isolation and native-byte gates, ported from signed 8ccc."""
import gzip
import hashlib
import io
import json
import os
import pathlib
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
import monthly_release as release
import test_monthly_public_release as packages
CORE = "yizha1/notation-core-go"
def plan(status):
    return {"schema": 1, "repository": CORE, "month": "2026-10", "mode": "execute",
            "cycle_id": "manual-review-20261018", "baseline": "v1.3.2-monthly-test.202610",
            "tag": "v1.3.3-manual-review.20261018", "main": "monthly-patch-test-main",
            "branch": "monthly-patch-test-release-1.3", "commit": "a" * 40,
            "previous_head": "b" * 40, "status": status}

class DraftDownloadTests(unittest.TestCase):
    def test_artifact_bridge_receipt_must_match_exact_plan_and_public_mode_cannot_use_it(self):
        candidate = plan(status="draft")
        candidate.update(release_id=44, assets=[])
        with tempfile.TemporaryDirectory() as temporary, patch.object(packages, "assert_tag"):
            root = pathlib.Path(temporary)
            (root / "draft-download-receipt.json").write_text(json.dumps({"plan_sha256": "wrong"}))
            with self.assertRaisesRegex(ValueError, "receipt"):
                packages.verify(candidate, root, "linux_amd64", root / "evidence", root)
            candidate["status"] = "verifying"
            with self.assertRaisesRegex(ValueError, "anonymous"):
                packages.verify(candidate, root, "linux_amd64", root / "public-evidence", root)

    def test_direct_download_uses_recorded_id_and_read_only_token(self):
        response = io.BytesIO(b"qualified")
        with patch.dict(os.environ, {"GH_TOKEN": "readonly"}), patch.object(packages.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(packages.download_draft(CORE, 100), b"qualified")
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, f"https://api.github.com/repos/{CORE}/releases/assets/100")
            self.assertEqual(request.headers["Authorization"], "Bearer readonly")

    def test_redirect_download_never_forwards_authorization(self):
        redirect = urllib.error.HTTPError("https://api.github.com", 302, "redirect",
                                         {"Location": "https://release-assets.githubusercontent.com/signed"}, None)
        with patch.dict(os.environ, {"GH_TOKEN": "readonly"}), \
             patch.object(packages.urllib.request, "build_opener") as opener, \
             patch.object(packages.urllib.request, "urlopen", return_value=io.BytesIO(b"bytes")) as download:
            opener.return_value.open.side_effect = redirect
            self.assertEqual(packages.download_draft(CORE, 100), b"bytes")
            self.assertEqual(download.call_args.args, ("https://release-assets.githubusercontent.com/signed",))
            self.assertNotIn("readonly", str(download.call_args))

    def test_denied_missing_network_and_untrusted_redirects_fail_closed(self):
        for code in (401, 403, 404, 500):
            error = urllib.error.HTTPError("https://api.github.com", code, "denied", {}, None)
            with patch.dict(os.environ, {"GH_TOKEN": "readonly"}), \
                 patch.object(packages.urllib.request, "build_opener") as opener, \
                 patch.object(packages.urllib.request, "urlopen") as fallback:
                opener.return_value.open.side_effect = error
                with self.assertRaisesRegex(ValueError, "no write-token fallback"):
                    packages.download_draft(CORE, 100)
                fallback.assert_not_called()
        for location in ("http://release-assets.githubusercontent.com/x", "https://evil.invalid/x"):
            with patch.dict(os.environ, {"GH_TOKEN": "readonly"}), \
                 patch.object(packages.urllib.request, "build_opener") as opener:
                opener.return_value.open.side_effect = urllib.error.HTTPError("", 302, "", {"Location": location}, None)
                with self.assertRaisesRegex(ValueError, "Untrusted"):
                    packages.download_draft(CORE, 100)

    def test_draft_native_gate_hashes_downloaded_bytes_and_writes_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source = root / "source"
            source.mkdir()
            candidate = plan(status="draft")
            candidate["release_id"] = 44
            names = release.asset_names("notation-core-go", candidate["tag"])
            content = {name: gzip.compress(b"source") if name.endswith(".tar.gz") else b"checksums" for name in names}
            candidate["assets"] = [{"id": index + 100, "name": name, "size": len(data),
                                    "sha256": hashlib.sha256(data).hexdigest()} for index, (name, data) in enumerate(content.items())]
            by_id = {item["id"]: content[item["name"]] for item in candidate["assets"]}
            archive = next(name for name in names if name.endswith(".tar.gz"))
            with patch.object(packages, "assert_tag"), patch.object(packages, "check_release_assets"), \
                 patch.object(packages, "git", return_value=candidate["commit"]), \
                 patch.object(packages, "download_draft", side_effect=lambda repository, identifier: by_id[identifier]), \
                 patch.object(packages, "verify_checksums", return_value=[archive]), \
                 patch.object(packages, "library_source_archive", return_value=b"source"):
                packages.verify(candidate, source, "linux_amd64", root / "passed")
                evidence = json.loads((root / "passed/verified.json").read_text())
                self.assertTrue(evidence["draft_downloads"])
                self.assertFalse(evidence["public_downloads"])
                by_id[100] = b"tampered"
                with self.assertRaisesRegex(ValueError, "Downloaded bytes differ"):
                    packages.verify(candidate, source, "linux_amd64", root / "failed")
                self.assertFalse((root / "failed/verified.json").exists())
            by_id[100] = content[candidate["assets"][0]["name"]]
            candidate["status"] = "verifying"
            def anonymous(url, timeout):
                self.assertIsInstance(url, str)
                self.assertTrue(url.startswith(f"https://github.com/{CORE}/releases/download/"))
                return io.BytesIO(content[url.rsplit("/", 1)[1]])
            with patch.object(packages, "assert_tag"), patch.object(packages, "check_public_assets"), \
                 patch.object(packages, "git", return_value=candidate["commit"]), \
                 patch.object(packages, "download_draft") as authenticated, \
                 patch.object(packages.urllib.request, "urlopen", side_effect=anonymous), \
                 patch.object(packages, "verify_checksums", return_value=[archive]), \
                 patch.object(packages, "library_source_archive", return_value=b"source"):
                packages.verify(candidate, source, "linux_amd64", root / "public")
                authenticated.assert_not_called()
                self.assertTrue(json.loads((root / "public/verified.json").read_text())["public_downloads"])
