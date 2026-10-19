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

import base64
import copy
import hashlib
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import monthly_release as release
import notation_release_controller as controller
from monthly_release_checks import accepted_findings, asset_names

ROOT = pathlib.Path(__file__).resolve().parents[1] / "release-trials" / controller.CYCLE_ID
CORE, GO, CLI = controller.REPOSITORIES
SHA = "a" * 40
CALLER = "b" * 40
ENV = {
    "GITHUB_REPOSITORY": CORE, "GITHUB_REF": f"refs/heads/{controller.DEPLOYMENT}",
    "GITHUB_SHA": CALLER, "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": "yizha1",
    "GITHUB_RUN_ID": "123", "MONTHLY_PATCH_ACTOR": "yizha1",
    "MONTHLY_PATCH_WORKER_SHA": SHA, "MONTHLY_PATCH_FORK_DEPLOYMENT_SHA": SHA,
    "MONTHLY_PATCH_FORK_CALLER_SHA": CALLER, "MONTHLY_PATCH_FORK_MANUAL_ENABLED": "true",
}


class API:
    def __init__(self):
        fixture = json.loads((ROOT / "approval-fixture.json").read_text())
        self.issue, self.approval = fixture["issue"], fixture["approval"]
        self.envelope = json.loads((ROOT / "plan.json").read_text())
        self.comments, self.writes, self.issues, self.assets, self.releases = [], [], [], [], []
        self.remote = None
        self.run = {
            "repository": {"full_name": CORE}, "event": "workflow_dispatch",
            "head_sha": CALLER, "head_branch": controller.DEPLOYMENT,
            "actor": {"login": "yizha1"}, "run_attempt": 1,
            "referenced_workflows": [{"path": f"{CLI}/.github/workflows/monthly-patch-worker.yml@{SHA}", "sha": SHA}],
        }
        self.pull_overrides = {}
        self.source = self.envelope["payload"]["repositories"][0]["source_head"]

    def issue_editor(self, repository, number):
        return "yizha1"

    def optional(self, path):
        try:
            return self.request(path)
        except release.APIError as error:
            if error.status != 404:
                raise
            return None

    def pages(self, path):
        if path.endswith("/assets"):
            return iter(copy.deepcopy(self.assets))
        if path.endswith("/releases"):
            return iter(copy.deepcopy(self.releases))
        if path.endswith("/comments"):
            return iter(copy.deepcopy(self.comments))
        if "/issues?" in path:
            return iter(copy.deepcopy(self.issues))
        if path.endswith("/commits") or path.endswith("/files"):
            number = int(path.split("/pulls/")[1].split("/")[0])
            original = next(item for item in self.envelope["payload"]["repositories"][0]["pulls"]
                            if item["number"] == number)
            if path.endswith("/commits"):
                return iter(self.pull_overrides.get("commits", original["commits"]))
            return iter(self.pull_overrides.get("files", [{"filename": file} for file in original["files"]]))
        raise AssertionError(path)

    def request(self, path, method="GET", payload=None):
        if method != "GET":
            self.writes.append((path, method, copy.deepcopy(payload)))
        if "/contents/" in path:
            name = path.split("/contents/")[1].split("?")[0].rsplit("/", 1)[1]
            raw = (ROOT / name).read_bytes()
            return {"type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode()}
        if path == f"repos/{CLI}/git/ref/heads/monthly-plan-review-manual-20261018":
            return {"object": {"sha": controller.PLAN_COMMIT}}
        if path == f"repos/{CLI}/commits/{controller.PLAN_COMMIT}":
            return {"sha": controller.PLAN_COMMIT, "commit": {"verification": {"verified": True}}}
        if "/git/ref/tags/" in path or "/releases/tags/" in path:
            raise release.APIError("HTTP 404 no reserved tag")
        if path == f"repos/{CLI}/issues/26":
            return copy.deepcopy(self.issue)
        if path == f"repos/{CLI}/issues/comments/{controller.APPROVAL_ID}":
            return copy.deepcopy(self.approval)
        if path.endswith("/actions/runs/123"):
            return copy.deepcopy(self.run)
        if path == "user":
            return {"login": "yizha1"}
        if path.endswith(f"/branches/{controller.DEPLOYMENT}"):
            return {"commit": {"sha": SHA if path.startswith(f"repos/{CLI}/") else CALLER}}
        if path in {f"repos/{repo}" for repo in controller.REPOSITORIES}:
            return {"full_name": path.removeprefix("repos/"), "fork": True, "owner": {"login": "yizha1"}, "default_branch": "main"}
        if "/compare/" in path:
            return {"status": "identical", "behind_by": 0, "ahead_by": 0, "commits": []}
        if path.endswith("/branches/monthly-patch-test-main"):
            return {"commit": {"sha": self.source}}
        if path.endswith("/branches/monthly-patch-test-release-1.3"):
            repo = path.removeprefix("repos/").split("/branches/")[0]
            snapshot = next(item for item in self.envelope["payload"]["repositories"] if item["repository"] == repo)
            return {"commit": {"sha": snapshot["release_head"]}}
        if path.endswith("/issues/26/comments") and method == "POST":
            comment = {"id": len(self.comments) + 1, "user": {"login": "yizha1"}, **payload}
            self.comments.append(comment)
            return copy.deepcopy(comment)
        if path == f"repos/{CORE}/releases" and method == "POST":
            self.remote = {"id": 44, "html_url": f"https://github.com/{CORE}/releases/tag/untagged-draft-44", **payload}
            self.releases.append(self.remote)
            return copy.deepcopy(self.remote)
        if path == f"repos/{CORE}/releases/44":
            if self.remote is None:
                raise release.APIError("HTTP 404 missing draft")
            return copy.deepcopy(self.remote)
        if path == f"repos/{CORE}/issues" and method == "POST":
            issue = {"number": 70 + len(self.issues), "user": {"login": "yizha1"}, **payload}
            self.issues.append(issue)
            return copy.deepcopy(issue)
        if path.startswith(f"repos/{CORE}/issues/"):
            issue = next(issue for issue in self.issues if issue["number"] == int(path.rsplit("/", 1)[1]))
            if method == "PATCH":
                issue.update(payload)
            return copy.deepcopy(issue)
        raise AssertionError((path, method))

    def upload(self, command):
        path = pathlib.Path(command[-1])
        item = {"id": len(self.assets) + 100, "name": path.name, "size": path.stat().st_size,
                "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}
        self.assets.append(item)
        return json.dumps(item)


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, ENV, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.api = API()

    def test_exact_signed_plan_file_inventory_body_and_owner_receipt(self):
        plan = controller.approved_plan(self.api)
        self.assertEqual(controller.digest(plan), controller.PLAN_HASH)
        self.assertEqual(len(plan["repositories"]), 3)
        self.assertEqual(sum(len(item["pulls"]) for item in plan["repositories"]), 11)
        controller.invocation(self.api, CORE)

    def test_body_mutation_rejects_approval_without_editing_recorded_scope(self):
        self.api.issue["body"] += "Changed"
        with self.assertRaisesRegex(ValueError, "issue"):
            controller.approved_plan(self.api)

    def test_missing_edited_foreign_or_earlier_comment_rejects(self):
        for key, value in (("body", "/approve other"), ("updated_at", "2026-10-20T00:00:00Z"),
                           ("issue_url", "https://api.github.com/repos/yizha1/notation/issues/25"),
                           ("created_at", "2026-10-19T00:00:00Z"), ("user", {"login": "attacker", "type": "User"})):
            api = API()
            api.approval[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                controller.approved_plan(api)

    def test_api_auth_network_errors_are_not_absence(self):
        for code in (401, 403, 429, 500):
            with patch.object(self.api, "request", side_effect=release.APIError(f"HTTP {code}")):
                with self.assertRaises(release.APIError):
                    self.api.optional("anything")

    def test_canonical_main_wrong_ref_actor_disabled_or_unpinned_cannot_write(self):
        for key, value in (
            ("GITHUB_REPOSITORY", "notaryproject/notation"), ("GITHUB_REF", "refs/heads/main"),
            ("GITHUB_ACTOR", "attacker"), ("MONTHLY_PATCH_FORK_MANUAL_ENABLED", "false"),
            ("MONTHLY_PATCH_WORKER_SHA", "main"), ("MONTHLY_PATCH_FORK_CALLER_SHA", SHA)):
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                controller.invocation(self.api, CORE)

    def test_missing_mismatched_called_workflow_or_rerun_rejects(self):
        for references in ([], [{"path": f"{CLI}/.github/workflows/monthly-patch-worker.yml@main", "sha": SHA}],
                           [{"path": f"{CLI}/.github/workflows/monthly-patch-worker.yml@{SHA}", "sha": CALLER}]):
            self.api.run["referenced_workflows"] = references
            with self.assertRaises(ValueError):
                controller.invocation(self.api, CORE)
        self.api = API()
        self.api.run["run_attempt"] = 2
        with self.assertRaises(ValueError):
            controller.invocation(self.api, CORE)

    def test_unrecorded_source_merge_blocks_but_recorded_progress_resumes(self):
        with patch.object(release, "Cycle") as cycle:
            cycle.return_value.state = None
            controller.worker_authorization(self.api, CORE, controller.MONTH)
            with patch.object(controller, "compare_commits", return_value={SHA}):
                with self.assertRaisesRegex(ValueError, "unrecorded"):
                    controller.worker_authorization(self.api, CORE, controller.MONTH)
                cycle.return_value.state = {"status": "merging", "merged": [{"number": 17, "commit": SHA}]}
                controller.worker_authorization(self.api, CORE, controller.MONTH)

    def test_no_old_cycle_reopening(self):
        with self.assertRaisesRegex(ValueError, "another cycle"):
            controller.worker_authorization(self.api, CORE, "2026-11")
        with self.assertRaisesRegex(ValueError, "cycle identity"):
            release.cycle_marker(controller.MONTH, "execute", "monthly")

    def test_unpublished_or_unverified_producer_blocks_consumers(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": GO}), patch.object(controller, "invocation"), \
             patch.object(release, "Cycle") as cycle, patch.object(controller, "compare_commits", return_value=set()):
            cycle.return_value.state = None
            with self.assertRaisesRegex(ValueError, "Waiting for owner"):
                controller.worker_authorization(self.api, GO, controller.MONTH)

    def test_current_head_commit_and_file_scope_are_exact(self):
        snapshot = controller.snapshot_for(self.api.envelope["payload"], CORE)
        expected = snapshot["pulls"][0]
        pull = {"number": expected["number"], "user": {"login": "dependabot[bot]", "type": "Bot"},
                "base": {"ref": "monthly-patch-test-main"}, "head": {"sha": expected["head"], "repo": {"full_name": CORE}}}
        auth = {"snapshot": snapshot, "producers": {}}
        self.assertTrue(controller.scoped_pull(self.api, CORE, pull, auth))
        for field, value in (("commits", [{"sha": SHA}]), ("files", [{"filename": "arbitrary.go"}])):
            self.api.pull_overrides = {field: value}
            with self.assertRaisesRegex(ValueError, "inventory changed"):
                controller.scoped_pull(self.api, CORE, pull, auth)

    def test_rechecked_success_at_same_head_does_not_mutate_historical_plan(self):
        original = self.api.envelope["payload"]["repositories"][-1]["pulls"]
        stale = next(item for item in original if item["number"] == 21)
        self.assertEqual(stale["checks"]["mergeStateStatus"], "UNSTABLE")
        live = {"headRefOid": stale["head"], "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
                "reviewDecision": "", "statusCheckRollup": [{"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"}]}
        self.assertTrue(release.checks_ready({"head": {"sha": stale["head"]}}, live)[0])
        self.assertEqual(controller.digest(self.api.envelope["payload"]), controller.PLAN_HASH)

    def test_reachable_findings_and_prior_dispositions_never_waived(self):
        with patch.dict(os.environ, {"MONTHLY_PATCH_ADVISORY_DISPOSITIONS": "{}"}):
            with self.assertRaisesRegex(ValueError, "dispositions"):
                accepted_findings({"GO-2026-1"}, {})

    def test_failure_comment_is_fixed_issue_deduped_and_escaped(self):
        first = controller.failure(self.api, CORE, "qualification", "[bad](x) @evil | `cmd`")
        second = controller.failure(self.api, CORE, "qualification", "second")
        self.assertEqual(first["action"], "notified")
        self.assertEqual(second["action"], "already-notified")
        self.assertEqual(len(self.api.comments), 1)
        body = self.api.comments[0]["body"]
        self.assertIn("@yizha1", body)
        self.assertIn("actions/runs/123", body)
        self.assertIn(GO, body)
        self.assertNotIn("@evil", body)
        self.assertFalse(any(path.endswith("/issues/26") and method == "PATCH" for path, method, _ in self.api.writes))


class DraftLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.api = API()
        env = patch.dict(os.environ, ENV, clear=True)
        env.start()
        self.addCleanup(env.stop)
        for name in ("policy", "coordinator_authorization", "assert_tag"):
            guard = patch.object(release, name, return_value=None)
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch("monthly_release_pr.validate")
        guard.start()
        self.addCleanup(guard.stop)
        self.plan = {"schema": 1, "repository": CORE, "month": controller.MONTH, "mode": "execute",
                     "cycle_id": controller.CYCLE_ID, "baseline": "v1.3.2-monthly-test.202610",
                     "branch": "monthly-patch-test-release-1.3", "main": "monthly-patch-test-main",
                     "tag": "v1.3.3-manual-review.20261018", "status": "tagged", "commit": SHA,
                     "previous_head": CALLER, "controller_issue": 26, "controller_plan_id": controller.PLAN_HASH,
                     "qualification": {"run_id": 122, "worker_sha": SHA, "commit": SHA},
                     "merged": [{"number": 17, "commit": "c" * 40, "title": "Dependency patch"}]}
        self.cycle = release.Cycle(self.api, CORE, controller.MONTH, "execute")
        self.cycle.save(self.plan)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = pathlib.Path(temp.name)
        for name in asset_names("notation-core-go", self.plan["tag"]):
            (self.directory / name).write_bytes(("qualified " + name).encode())

    def stage(self):
        with patch.object(release, "run", side_effect=self.api.upload):
            return release.publish(self.api, self.plan, self.directory)

    def test_true_draft_prerelease_exact_assets_then_qualified_review_waits(self):
        result = self.stage()
        self.assertEqual(result["action"], "draft-check")
        self.assertTrue(self.api.remote["draft"])
        self.assertTrue(self.api.remote["prerelease"])
        self.assertTrue(all(asset["id"] >= 100 for asset in result["assets"]))
        self.assertFalse(any("Qualified draft release review" in issue["body"] for issue in self.api.issues))
        qualified = release.complete(self.api, result)
        self.assertEqual(qualified["status"], "awaiting-publication")
        self.assertIn("Publish release", self.api.issues[-1]["body"])
        self.assertIn("untagged-draft-44", self.api.issues[-1]["body"])
        self.assertFalse(any(method == "PATCH" and "/releases/" in path for path, method, _ in self.api.writes))

    def test_publication_before_qualification_rejects(self):
        result = self.stage()
        self.api.remote["draft"] = False
        with self.assertRaises(ValueError):
            release.complete(self.api, result)

    def test_same_release_and_assets_then_public_completion(self):
        qualified = release.complete(self.api, self.stage())
        self.api.remote["draft"] = False
        self.assertEqual(release.check_public_assets(self.api, qualified)["id"], 44)
        qualified["status"] = "verifying"
        release.Cycle(self.api, CORE, controller.MONTH, "execute").save(qualified)
        result = release.complete(self.api, qualified)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["public_verification_run"], 123)

    def test_changed_asset_id_size_digest_extra_or_release_identity_rejects(self):
        result = self.stage()
        original = copy.deepcopy(self.api.assets)
        for key, value in (("id", 999), ("size", 1), ("digest", "sha256:" + "0" * 64)):
            self.api.assets = copy.deepcopy(original)
            self.api.assets[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.check_release_assets(self.api, result, True)
        self.api.assets = original + [{"name": "unexpected"}]
        with self.assertRaises(ValueError):
            release.check_release_assets(self.api, result, True)
        self.api.assets = original
        self.api.remote["id"] = 45
        with self.assertRaises(ValueError):
            release.check_release_assets(self.api, result, True)

    def test_review_body_edit_blocks_public_progress(self):
        qualified = release.complete(self.api, self.stage())
        issue = next(item for item in self.api.issues if item["number"] == qualified["draft_review_issue"])
        issue["body"] += "modified"
        self.api.remote["draft"] = False
        with self.assertRaises(ValueError):
            release.check_public_assets(self.api, qualified)

    def test_old_or_canonical_namespaces_cannot_be_candidate_plans(self):
        for key, value in (("cycle_id", "monthly"), ("repository", "notaryproject/notation-core-go"),
                           ("branch", "release-1.3"), ("tag", "v1.3.3")):
            altered = {**self.plan, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.validate_plan(altered)

    def test_partial_upload_retry_keeps_release_and_original_bytes(self):
        upload = self.api.upload
        def interrupt(command):
            if len(self.api.assets) == 1:
                raise RuntimeError("HTTP 503 upload interrupted")
            return upload(command)
        with patch.object(release, "run", side_effect=interrupt), self.assertRaises(RuntimeError):
            release.publish(self.api, self.plan, self.directory)
        reserved = release.Cycle(self.api, CORE, controller.MONTH, "execute").state
        self.assertEqual(reserved["status"], "staging")
        self.assertEqual(reserved["release_id"], 44)
        finished = self.stage()
        self.assertEqual(finished["release_id"], 44)
        self.assertEqual(len(self.api.assets), 2)
        self.assertEqual(sum(method == "POST" and path.endswith("/releases")
                             for path, method, _ in self.api.writes), 1)

    def test_changed_rebuilt_bytes_cannot_resume_partial_upload(self):
        with patch.object(release, "run", side_effect=RuntimeError("upload unavailable")), self.assertRaises(RuntimeError):
            release.publish(self.api, self.plan, self.directory)
        next(self.directory.iterdir()).write_bytes(b"different rebuild")
        with self.assertRaisesRegex(ValueError, "exact originally"):
            self.stage()

    def test_existing_unrecorded_release_cannot_be_adopted(self):
        self.api.releases.append({"tag_name": self.plan["tag"], "id": 777, "draft": True})
        with self.assertRaisesRegex(ValueError, "Unrecorded"):
            self.stage()

    def test_missing_or_changed_source_qualification_receipt_blocks_staging(self):
        del self.plan["qualification"]
        with self.assertRaisesRegex(ValueError, "qualification run"):
            self.stage()

    def test_trusted_download_bridge_binds_exact_bytes_and_plan_without_candidate_execution(self):
        import fork_draft_download as bridge
        state = self.stage()
        content = {asset["id"]: (self.directory / asset["name"]).read_bytes() for asset in state["assets"]}
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(controller, "worker_authorization"), \
             patch.object(bridge, "download_draft", side_effect=lambda repo, identifier: content[identifier]), \
             patch.object(release, "run") as execute:
            output = pathlib.Path(temporary)
            bridge.download(self.api, state, output)
            receipt = json.loads((output / "draft-download-receipt.json").read_text())
            persisted = json.loads((output / "plan.json").read_text())
            self.assertEqual(receipt["plan_sha256"], controller.digest(persisted))
            self.assertEqual(receipt["assets"], persisted["assets"])
            execute.assert_not_called()
        content[state["assets"][0]["id"]] = b"changed"
        with tempfile.TemporaryDirectory() as temporary, patch.object(controller, "worker_authorization"), \
             patch.object(bridge, "download_draft", side_effect=lambda repo, identifier: content[identifier]):
            with self.assertRaisesRegex(ValueError, "qualified bytes"):
                bridge.download(self.api, state, pathlib.Path(temporary))


class ProducerAndVoteTests(unittest.TestCase):
    def test_producer_only_scope_rejects_unrelated_direct_dependency_or_module_changes(self):
        before = {".": {"Module": {"Path": "github.com/notaryproject/notation-go"}, "Go": "1.26.0",
                        "Require": [{"Path": "github.com/notaryproject/notation-core-go", "Version": "v1.3.0"},
                                    {"Path": "example.com/ordinary", "Version": "v1.0.0"}],
                        "Replace": [{"Old": {"Path": "github.com/notaryproject/notation-core-go"},
                                     "New": {"Path": "github.com/yizha1/notation-core-go", "Version": "v1.3.2-monthly-test.202610"}}]}}
        after = copy.deepcopy(before)
        tag = "v1.3.3-manual-review.20261018"
        after["."]["Replace"][0]["New"]["Version"] = tag
        producers = {"notation-core-go": {"repository": CORE, "version": tag}}
        manifests = {"notation-core-go": {"Go": "1.26.0", "Require": []}}
        self.assertTrue(controller.producer_manifests(before, after, producers, manifests, "go1.27.1"))
        for field, value in (("Module", {"Path": "other"}), ("Require", [
                {"Path": "github.com/notaryproject/notation-core-go", "Version": "v1.3.0"},
                {"Path": "example.com/ordinary", "Version": "v1.0.1"}])):
            changed = copy.deepcopy(after)
            changed["."][field] = value
            self.assertFalse(controller.producer_manifests(before, changed, producers, manifests, "go1.27.1"))

    def test_mismatched_or_duplicate_fork_replacements_cannot_qualify(self):
        manifest = {"Require": [{"Path": "github.com/notaryproject/notation-core-go", "Version": "v1.3.0"}],
                    "Replace": [{"Old": {"Path": "github.com/notaryproject/notation-core-go"},
                                 "New": {"Path": "github.com/attacker/notation-core-go", "Version": "v1.3.3"}}]}
        with self.assertRaisesRegex(ValueError, "replacement"):
            release.requirement(manifest, "github.com/notaryproject/notation-core-go", CORE, "execute")

    def test_untrusted_propagation_artifact_rejected_before_signing(self):
        import notation_fork_propagation as propagation
        api = API()
        plan = {"repository": GO, "month": controller.MONTH, "mode": "execute", "main": "monthly-patch-test-main"}
        with patch.object(controller, "worker_authorization", return_value={"plan_id": controller.PLAN_HASH}), \
             patch.object(propagation, "source_head", return_value=SHA), patch.object(release, "policy"), \
             patch.object(release, "signing_environment") as signing, tempfile.TemporaryDirectory() as output:
            prepared = {"schema": 1, "action": "pull-request", "plan": plan, "base": SHA,
                        "original": {}, "files": {"source.go": "malicious source"}}
            with self.assertRaisesRegex(ValueError, "file set"):
                propagation.publish(api, prepared, pathlib.Path(output))
            signing.assert_not_called()

    def test_owner_metadata_approval_is_exact_unedited_and_not_canonical_votes(self):
        import monthly_release_vote as voting
        base, head, tree, candidate = [character * 40 for character in "abcd"]
        expected = {"repository": GO, "number": 42, "actor": "yizha1",
                    "base_ref": "monthly-patch-test-release-1.3", "base_sha": base,
                    "head_ref": "monthly-patch/vote", "head_sha": head, "head_tree": tree,
                    "candidate_sha": base, "candidate_tree": candidate,
                    "tag": "v1.3.5-manual-review.20261018",
                    "metadata_before": 'package signer\nconst signingAgent = "notation-go/1.3.4"\n',
                    "metadata_after": 'package signer\nconst signingAgent = "notation-go/1.3.5-manual-review.20261018"\n'}
        pull = {"number": 42, "state": "open", "draft": False, "user": {"login": "yizha1"},
                "base": {"ref": expected["base_ref"], "sha": base, "repo": {"full_name": GO}},
                "head": {"ref": expected["head_ref"], "sha": head, "repo": {"full_name": GO}},
                "body": f"https://github.com/{GO}/blob/{base}/MAINTAINERS\nhttps://github.com/{GO}/compare/",
                "created_at": "2026-10-19T00:00:00Z"}
        diff = {"files": [{"filename": "signer/signer.go", "status": "modified"}],
                "before": expected["metadata_before"], "after": expected["metadata_after"]}
        comment = {"id": 1, "user": {"login": "yizha1", "type": "User"},
                   "body": f"/approve-release {head}", "created_at": "2026-10-19T01:00:00Z",
                   "updated_at": "2026-10-19T01:00:00Z", "issue_url": f"https://api.github.com/repos/{GO}/issues/42"}
        self.assertEqual(voting.assess_vote(expected, pull, [comment], "", diff)["status"], "ready")
        for key, value in (("body", "/approve"), ("updated_at", "2026-10-20T00:00:00Z"),
                           ("user", {"login": "canonical-maintainer", "type": "User"})):
            changed = {**comment, key: value}
            self.assertEqual(voting.assess_vote(expected, pull, [changed], "", diff)["status"], "waiting")
        altered = copy.deepcopy(diff)
        altered["files"].append({"filename": "unrelated.go", "status": "modified"})
        with self.assertRaises(ValueError):
            voting.assess_vote(expected, pull, [comment], "", altered)


class WorkflowTests(unittest.TestCase):
    def test_secret_free_source_package_and_native_jobs(self):
        import re
        workflow = (ROOT.parents[1] / "workflows/monthly-patch-worker.yml").read_text()
        for name in ("qualify", "package", "verify", "propagation-prepare"):
            text = re.search(rf"(?ms)^  {name}:\n(.*?)(?=^  [a-z][a-z-]*:|\Z)", workflow)[1]
            self.assertNotIn("secrets.MONTHLY_PATCH", text, name)
            self.assertNotIn("secrets: inherit", text)
        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)
        downloader = re.search(r"(?ms)^  download-draft:\n(.*?)(?=^  [a-z][a-z-]*:|\Z)", workflow)[1]
        self.assertIn("secrets.MONTHLY_PATCH_TOKEN", downloader)
        self.assertNotIn("MONTHLY_PATCH_SIGNING_KEY", downloader)
        self.assertNotIn("path: candidate", downloader)
        self.assertNotIn("go test", downloader)
        self.assertIn("fork_draft_download.py", downloader)

    def test_no_automatic_publication_or_default_branch_dispatch(self):
        root = ROOT.parents[1]
        workflow = (root / "workflows/monthly-patch-worker.yml").read_text()
        self.assertNotIn("draft: false", workflow)
        self.assertNotIn("--draft=false", workflow)
        self.assertNotIn("refs/heads/main", workflow)
        self.assertIn("monthly-manual-executor-20261018", workflow)
        source = (root / "scripts/monthly_release.py").read_text()
        self.assertNotIn('"draft": False', source)
        self.assertNotIn('f"repos/notaryproject/', source)


if __name__ == "__main__":
    unittest.main()
