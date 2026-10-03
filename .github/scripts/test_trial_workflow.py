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

    def test_e2e_runner_matches_the_updated_ginkgo_dependency(self):
        manifest = (ROOT / "test/e2e/go.mod").read_text()
        version = re.search(r"github\.com/onsi/ginkgo/v2 (v\S+)", manifest).group(1)
        runner = (ROOT / "test/e2e/run.sh").read_text()
        self.assertIn(
            f"go install -mod=mod github.com/onsi/ginkgo/v2/ginkgo@{version}",
            runner,
        )


if __name__ == "__main__":
    unittest.main()
