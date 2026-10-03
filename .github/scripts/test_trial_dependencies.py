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
import pathlib
import subprocess
import unittest
from unittest.mock import patch

from check_trial_dependencies import DEPENDENCIES, MODULES, module_metadata, verify


class TrialDependencyTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path("/candidate")
        self.metadata = {}
        self.calls = []
        for library, (base, version, commit) in DEPENDENCIES.items():
            upstream = f"github.com/notaryproject/{library}"
            fork = f"github.com/yizha1/{library}"
            self.metadata[(f"{fork}@{commit}", self.root)] = {
                "Path": fork, "Version": version, "Origin": {"Hash": commit},
            }
            for module in MODULES:
                self.metadata[(upstream, self.root / module)] = {
                    "Path": upstream, "Version": base,
                    "Replace": {"Path": fork, "Version": version},
                }

    def lookup(self, query, directory):
        self.calls.append((query, directory))
        return self.metadata[(query, directory)]

    def test_checks_both_commits_and_all_three_modules(self):
        verify(self.root, self.lookup)
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(set(self.calls), set(self.metadata))

    def test_every_module_requires_both_replacements(self):
        for library in DEPENDENCIES:
            for module in MODULES:
                with self.subTest(library=library, module=module):
                    key = (f"github.com/notaryproject/{library}", self.root / module)
                    replacement = self.metadata[key].pop("Replace")
                    with self.assertRaisesRegex(ValueError, "Expected .* in"):
                        verify(self.root, self.lookup)
                    self.metadata[key]["Replace"] = replacement

    def test_wrong_base_fork_or_version_is_rejected(self):
        for library in DEPENDENCIES:
            key = (f"github.com/notaryproject/{library}", self.root)
            original = copy.deepcopy(self.metadata[key])
            for field, value in (
                ("Path", f"github.com/yizha1/{library}"),
                ("Version", "v9.9.9"),
                ("replacement-path", "/local/workspace"),
                ("replacement-version", "v1.3.3-trial.1"),
                ("replacement-version", "v1.3.3-trial.20"),
            ):
                with self.subTest(library=library, field=field, value=value):
                    self.metadata[key] = copy.deepcopy(original)
                    if field.startswith("replacement-"):
                        self.metadata[key]["Replace"][field.split("-")[1].title()] = value
                    else:
                        self.metadata[key][field] = value
                    with self.assertRaisesRegex(ValueError, "Expected .* in"):
                        verify(self.root, self.lookup)
            self.metadata[key] = original

    def test_commit_resolution_must_match_path_version_and_hash(self):
        for library, (_, _, commit) in DEPENDENCIES.items():
            key = (f"github.com/yizha1/{library}@{commit}", self.root)
            original = copy.deepcopy(self.metadata[key])
            for field, value in (
                ("Path", f"github.com/notaryproject/{library}"),
                ("Version", "v1.3.3-trial.1"),
                ("Origin", {"Hash": "0" * 40}),
                ("Origin", {}),
            ):
                with self.subTest(library=library, field=field):
                    self.metadata[key] = {**original, field: value}
                    with self.assertRaisesRegex(ValueError, "resolved"):
                        verify(self.root, self.lookup)
            self.metadata[key] = original

    def test_resolution_failure_is_not_success(self):
        def failed_lookup(query, directory):
            raise subprocess.CalledProcessError(1, ["go", "list", query])

        with self.assertRaises(subprocess.CalledProcessError):
            verify(self.root, failed_lookup)

    @patch("check_trial_dependencies.subprocess.check_output")
    @patch.dict("os.environ", {"GOWORK": "/local/workspace/go.work", "GOFLAGS": "-mod=vendor"})
    def test_go_queries_disable_workspace_and_vendor_overrides(self, command):
        command.return_value = '{"Path": "test"}'
        self.assertEqual(module_metadata("test", self.root), {"Path": "test"})
        self.assertEqual(command.call_args.kwargs["env"]["GOWORK"], "off")
        self.assertEqual(command.call_args.kwargs["env"]["GOFLAGS"], "-mod=readonly")
        self.assertEqual(command.call_args.args[0], ["go", "list", "-m", "-json", "test"])


if __name__ == "__main__":
    unittest.main()
