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

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class TrialWorkflowTests(unittest.TestCase):
    def test_binary_scan_precedes_draft_upload(self):
        workflow = (ROOT / ".github/workflows/trial-release.yml").read_text()
        build = workflow.index("args: release --clean --skip=publish")
        scan = workflow.index("python3 .github/scripts/check_trial_artifacts.py dist")
        upload = workflow.index("gh release create")
        self.assertLess(build, scan)
        self.assertLess(scan, upload)
        self.assertNotIn("continue-on-error", workflow[build:upload])
        self.assertNotIn("|| true", workflow[build:upload])
        self.assertIn("--verify-tag --draft --prerelease", workflow[upload:])

    def test_draft_requires_qualification_and_matching_annotated_tag(self):
        workflow = (ROOT / ".github/workflows/trial-release.yml").read_text()
        self.assertIn("needs: qualification", workflow)
        self.assertIn("needs.qualification.result == 'success'", workflow)
        self.assertIn('git cat-file -t "refs/tags/$GITHUB_REF_NAME"', workflow)
        self.assertIn(
            'git rev-parse "refs/tags/$GITHUB_REF_NAME^{commit}")" != "$GITHUB_SHA"',
            workflow,
        )
        self.assertIn("ref: ${{ github.sha }}", workflow)

    def test_qualification_covers_both_toolchains_and_exact_dependencies(self):
        workflow = (ROOT / ".github/workflows/patch-qualification.yml").read_text()
        self.assertIn("go-version: ['1.26', stable]", workflow)
        self.assertIn("GOWORK: 'off'", workflow)
        self.assertIn("python3 .github/scripts/check_trial_dependencies.py", workflow)
        self.assertIn("name: vulnerability-results-${{ matrix.go-version }}", workflow)

    def test_qualification_requires_the_pinned_license_workflow_for_all_modules(self):
        workflow = (ROOT / ".github/workflows/patch-qualification.yml").read_text()
        job = workflow.split("  licenses:\n", 1)[1].split("  qualify:\n", 1)[0]
        self.assertIn(
            "uses: yizha1/notation-core-go/.github/workflows/"
            "reusable-license-checker.yml@03171674c94728622c5b1534b5e3396fcb468733",
            job,
        )
        self.assertIn("github.repository == 'yizha1/notation'", job)
        self.assertIn("vars.PATCH_TRIAL_ENABLED == 'true'", job)
        config = (ROOT / ".github/licenserc.yml").read_text()
        for manifest in ("../go.mod", "../test/e2e/go.mod", "../test/e2e/plugin/go.mod"):
            self.assertIn(f"    - {manifest}", config.splitlines())

    def test_e2e_runner_matches_the_updated_ginkgo_dependency(self):
        manifest = (ROOT / "test/e2e/go.mod").read_text()
        version = re.search(r"github\.com/onsi/ginkgo/v2 (v\S+)", manifest).group(1)
        runner = (ROOT / "test/e2e/run.sh").read_text()
        self.assertIn(
            f"go install -mod=mod github.com/onsi/ginkgo/v2/ginkgo@{version}",
            runner,
        )

    def test_binary_scans_retain_symbols_without_dwarf_debug_information(self):
        config = (ROOT / ".goreleaser.yml").read_text()
        flags = config.split("    ldflags:\n", 1)[1].split("\narchives:", 1)[0]
        self.assertRegex(flags, r"\s-w(?:\s|$)")
        self.assertNotRegex(flags, r"\s-s(?:\s|=|$)")

    def test_trial_disposition_and_evidence_apply_before_and_after_upload(self):
        workflow = (ROOT / ".github/workflows/trial-release.yml").read_text()
        self.assertEqual(workflow.count(
            "--trial-disposition .github/trial-advisory-disposition.json"
        ), 2)
        self.assertEqual(workflow.count("--evidence-directory binary-vulnerability-results"), 2)
        upload = workflow.index("gh release create")
        self.assertIn("if: always()", workflow[:upload])
        self.assertIn("if: always()", workflow[upload:])
        self.assertIn("cat .github/trial-advisory-disposition.json", workflow[:upload])
        self.assertIn("name: binary-vulnerability-results-${{ matrix.platform }}", workflow)


if __name__ == "__main__":
    unittest.main()
