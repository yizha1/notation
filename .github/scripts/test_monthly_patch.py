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

import unittest
from unittest.mock import patch

from monthly_patch import (
    DEPENDENCY_REPOSITORIES,
    GitHub,
    SOURCE_REPOSITORY,
    TRIAL_REPOSITORY,
    initiate,
    latest_stable,
    marker,
    previous_tag,
)


class FakeGitHub:
    def __init__(self, issues=(), branch_exists=True):
        self.issues = list(issues)
        self.branch_exists = branch_exists
        self.calls = []

    def pages(self, path):
        self.calls.append((path, None))
        if path == f"repos/{TRIAL_REPOSITORY}/issues?state=all":
            return iter(self.issues)
        if path == f"repos/{SOURCE_REPOSITORY}/releases":
            return iter([
                {"tag_name": "v2.0.0-alpha.1", "draft": False, "prerelease": True},
                {"tag_name": "v1.2.9", "draft": False, "prerelease": False},
                {"tag_name": "v1.3.2", "draft": False, "prerelease": False},
            ])
        if path in [f"repos/{source}/pulls?state=open" for source in DEPENDENCY_REPOSITORIES]:
            repository = path.split("/pulls?")[0].removeprefix("repos/")
            return iter([
                {
                    "number": 1, "html_url": f"https://github.com/{repository}/pull/1",
                    "title": "Update dependency", "base": {"ref": "main"},
                    "user": {"login": "dependabot[bot]"},
                },
                {
                    "number": 2, "html_url": f"https://github.com/{repository}/pull/2",
                    "title": "Unrelated feature", "base": {"ref": "main"},
                    "user": {"login": "contributor"},
                },
            ])
        raise AssertionError(path)

    def request(self, path, data=None):
        self.calls.append((path, data))
        if data is None:
            if not self.branch_exists:
                raise ValueError("Missing stable branch")
            return {"name": "release-1.3"}
        if path != f"repos/{TRIAL_REPOSITORY}/issues":
            raise AssertionError("Write escaped the fork")
        return {"html_url": "https://github.com/yizha1/notation/issues/1"}


class MonthlyPatchTests(unittest.TestCase):
    @patch("monthly_patch.subprocess.check_output")
    def test_platform_operations_use_cli_without_token_arguments(self, command):
        command.return_value = '{"ok": true}'
        api = GitHub("test-only-token")
        self.assertEqual(api.request("repos/yizha1/notation"), {"ok": True})
        self.assertEqual(command.call_args.args[0][-2:], ["--method", "GET"])
        api.request("repos/yizha1/notation/issues", {"title": "Trial"})
        self.assertEqual(command.call_args.args[0][-2:], ["--input", "-"])
        self.assertEqual(command.call_args.kwargs["input"], '{"title": "Trial"}')
        self.assertNotIn("test-only-token", command.call_args.args[0])

    def test_release_selection_is_semver_not_date_or_latest_flag(self):
        releases = [
            {"tag_name": tag, "draft": draft, "prerelease": pre}
            for tag, draft, pre in [
                ("v1.9.0", False, False), ("v1.10.2", False, False),
                ("v2.0.0", True, False), ("v3.0.0-rc.1", False, True),
                ("v01.10.3", False, False),
            ]
        ]
        self.assertEqual(latest_stable(releases), "v1.10.2")

    def test_previous_tag_ignores_other_lines_and_trials(self):
        tags = ["v1.2.9", "v1.3.1", "v1.3.2", "v1.3.3-trial.1", "v2.0.0"]
        for candidate in ("v1.3.3", "v1.3.3-trial.2"):
            self.assertEqual(previous_tag(candidate, tags), "v1.3.2")

    def test_bad_versions_fail(self):
        for candidate in ("v1.3.0", "v1.3.3-rc.1", "v01.3.3", "v1.3.3-trial.0"):
            with self.assertRaises(ValueError):
                previous_tag(candidate, ["v1.2.9"])
        with self.assertRaises(ValueError):
            latest_stable([])
        for month in ("2026-00", "2026-13", "2026-1", "2026-10\n"):
            with self.assertRaises(ValueError):
                marker(month)

    def test_wrong_identity_or_missing_opt_in_never_calls_api(self):
        for repository, enabled in [
            (SOURCE_REPOSITORY, "true"), ("yizha1_microsoft/notation", "true"),
            (TRIAL_REPOSITORY, ""), (TRIAL_REPOSITORY, "false"),
        ]:
            api = FakeGitHub()
            with self.assertRaises(ValueError):
                initiate(api, repository, enabled, "2026-10", write=True)
            self.assertEqual(api.calls, [])

    def test_dry_run_reads_upstream_but_never_writes(self):
        api = FakeGitHub()
        result = initiate(api, TRIAL_REPOSITORY, "true", "2026-10")
        self.assertEqual(result["outcome"], "preview")
        self.assertIn("release-1.3", result["payload"]["body"])
        for source in DEPENDENCY_REPOSITORIES:
            self.assertIn(f"{source}#1", result["payload"]["body"])
        self.assertNotIn("Unrelated feature", result["payload"]["body"])
        self.assertTrue(all(data is None for _, data in api.calls))

    def test_only_fork_issue_can_be_created(self):
        api = FakeGitHub()
        result = initiate(api, TRIAL_REPOSITORY, "true", "2026-10", write=True)
        self.assertEqual(result["outcome"], "created")
        writes = [(path, data) for path, data in api.calls if data is not None]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], f"repos/{TRIAL_REPOSITORY}/issues")
        self.assertIn(marker("2026-10"), writes[0][1]["body"])

    def test_closed_issue_retry_does_not_duplicate(self):
        api = FakeGitHub([{
            "state": "closed", "body": marker("2026-10"),
            "html_url": "https://github.com/yizha1/notation/issues/1",
        }])
        self.assertEqual(
            initiate(api, TRIAL_REPOSITORY, "true", "2026-10", write=True)["outcome"],
            "existing",
        )
        self.assertEqual(len(api.calls), 1)

    def test_pull_request_with_marker_is_not_an_issue(self):
        api = FakeGitHub([{"pull_request": {}, "body": marker("2026-10")}])
        self.assertEqual(
            initiate(api, TRIAL_REPOSITORY, "true", "2026-10")["outcome"], "preview"
        )

    def test_duplicates_and_missing_branch_fail_without_writes(self):
        for api in (
            FakeGitHub([{"body": marker("2026-10")}] * 2),
            FakeGitHub(branch_exists=False),
        ):
            with self.assertRaises(ValueError):
                initiate(api, TRIAL_REPOSITORY, "true", "2026-10", write=True)
            self.assertTrue(all(data is None for _, data in api.calls))

    def test_api_failure_is_not_success(self):
        class FailedAPI(FakeGitHub):
            def pages(self, path):
                raise OSError("API unavailable")

        with self.assertRaises(OSError):
            initiate(FailedAPI(), TRIAL_REPOSITORY, "true", "2026-10", write=True)


if __name__ == "__main__":
    unittest.main()
