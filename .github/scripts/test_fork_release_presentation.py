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
import copy
import hashlib
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import fork_release_presentation as presentation
import monthly_release as release
import notation_release_controller as controller
from test_fork_manual_executor import API, ENV, CORE, GO, CLI


class PresentationMigrationTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, ENV, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.api = API()
        self.receipt = presentation.receipt()

    def test_windows_checkout_preserves_frozen_receipt_bytes(self):
        root = pathlib.Path(presentation.__file__).resolve().parents[2]
        relative = pathlib.Path(".github/release-trials/manual-review-20261018/presentation-v1.json")
        with tempfile.TemporaryDirectory(prefix="presentation-checkout-") as directory:
            checkout = pathlib.Path(directory)
            target = checkout / relative
            target.parent.mkdir(parents=True)
            target.write_bytes((root / relative).read_bytes())
            (checkout / ".gitattributes").write_bytes((root / ".gitattributes").read_bytes())
            for arguments in (("init", "--quiet"), ("add", ".gitattributes", relative.as_posix())):
                subprocess.run(["git", "-C", directory, "-c", "core.autocrlf=true", *arguments],
                               check=True, capture_output=True)
            target.unlink()
            subprocess.run(["git", "-C", directory, "-c", "core.autocrlf=true",
                            "checkout-index", "--force", "--all"], check=True, capture_output=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), presentation.RECEIPT_SHA256)
            with patch.object(presentation, "__file__", str(checkout / ".github/scripts/fork_release_presentation.py")):
                self.assertEqual(presentation.receipt(), self.receipt)

    def test_new_cli_body_preserves_exact_original_scope_and_owner_approval(self):
        self.api.issue["body"] = self.receipt["issues"][CLI]["body"]
        self.assertEqual(controller.digest(controller.approved_plan(self.api)), controller.PLAN_HASH)
        self.assertEqual(self.api.approval["id"], 6260449311)
        self.assertFalse(self.api.writes)

    def test_body_tampering_new_dependency_or_revoked_approval_is_not_presentation(self):
        self.api.issue["body"] = self.receipt["issues"][CLI]["body"] + "\nAdd unrelated producer"
        with self.assertRaises(ValueError):
            controller.approved_plan(self.api)
        self.api.issue["body"] = self.receipt["issues"][CLI]["body"]
        self.api.approval["body"] = "/revoke"
        with self.assertRaises(ValueError):
            controller.approved_plan(self.api)

    def test_preserve_existing_core_draft_and_original_old_shared_worker_proof(self):
        plan = {**self.receipt["existing_core_quality"], "draft_review_issue": 20}
        expected = copy.deepcopy(self.receipt["qualification_run"])
        original = self.api.request
        def request(path, method="GET", payload=None):
            if path == f"repos/{CORE}/actions/runs/39210327124":
                return expected
            return original(path, method, payload)
        with patch.object(self.api, "request", side_effect=request):
            review = release.check_draft_review(self.api, plan)
        self.assertEqual(review["number"], 20)
        self.assertEqual(plan["release_id"], 416979094)
        self.assertEqual([item["id"] for item in plan["assets"]], [655453799, 655453836])
        self.assertEqual(plan["draft_verification"]["worker_sha"], "059ed8e00de14358e42f53872195d2675cb47b2d")
        self.assertFalse(self.api.writes)

    def test_quality_identity_or_original_run_changes_cannot_migrate(self):
        plan = {**self.receipt["existing_core_quality"], "draft_review_issue": 20}
        for key in presentation.QUALITY_KEYS:
            changed = copy.deepcopy(plan)
            changed[key] = None if changed[key] is not None else "injected"
            with self.subTest(key=key), self.assertRaises(ValueError):
                presentation.check_existing_quality(self.api, changed)
        with patch.object(self.api, "request", side_effect=lambda path: (
            {"conclusion": "failure"} if "/actions/runs/" in path
            else copy.deepcopy(self.api.scopes[CORE]))):
            with self.assertRaisesRegex(ValueError, "provenance"):
                presentation.check_existing_quality(self.api, plan)

    def test_frozen_receipt_and_bodies_have_only_own_pr_scope(self):
        for repo, numbers in ((CORE, (17, 16, 15)), (GO, (15, 13)), (CLI, (25, 22, 21, 20, 19, 18))):
            body = self.receipt["issues"][repo]["body"]
            for number in numbers:
                self.assertIn(f"https://github.com/{repo}/pull/{number}", body)
            for other in (CORE, GO, CLI):
                if other != repo:
                    self.assertNotIn(f"https://github.com/{other}/pull/", body)
        self.assertIn(f"{CORE}#20", self.receipt["issues"][GO]["body"])
        self.assertNotIn(f"{CLI}#26", self.receipt["issues"][GO]["body"])

    def test_ready_notice_reuses_scope_issue_and_is_idempotent(self):
        plan = {"repository": GO, "tag": "v1.3.5-manual-review.20261018", "release_id": 123}
        issue, first = presentation.ready_comment(self.api, plan, "Exact qualified draft evidence")
        _, second = presentation.ready_comment(self.api, plan, "Exact qualified draft evidence")
        self.assertEqual(issue["number"], 16)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.api.comments), 1)
        self.assertFalse(any(path.endswith("/issues") for path, _, _ in self.api.writes))

    def test_go_failure_details_stay_in_go_only_cli_gets_link(self):
        presentation.notify_failure(self.api, GO, 7, "package", "Go-only failure @untrusted")
        self.assertEqual(len(self.api.comments), 2)
        for item in self.api.comments:
            if "/repos/yizha1/notation-go/" in item["issue_url"]:
                self.assertIn("Go-only failure", item["body"])
                self.assertNotIn("@untrusted", item["body"])
            else:
                self.assertIn(f"Blocked by [{GO}#16]", item["body"])
                self.assertNotIn("Go-only failure", item["body"])
                self.assertNotIn("@yizha1", item["body"])


if __name__ == "__main__":
    unittest.main()
