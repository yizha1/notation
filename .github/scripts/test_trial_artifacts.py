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

import hashlib
import io
import pathlib
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from check_trial_artifacts import EXPECTED, verify


class TrialArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = pathlib.Path(self.temporary.name)
        entries = []
        for platform in sorted(EXPECTED):
            suffix = "zip" if platform == "windows_amd64" else "tar.gz"
            path = self.directory / f"notation_1.3.3-trial.1_{platform}.{suffix}"
            if suffix == "zip":
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("notation.exe", b"fake binary")
            else:
                with tarfile.open(path, "w:gz") as archive:
                    member = tarfile.TarInfo("notation")
                    member.size = len(b"fake binary")
                    archive.addfile(member, io.BytesIO(b"fake binary"))
            entries.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
        self.checksums = self.directory / "notation_checksums.txt"
        self.checksums.write_text("\n".join(entries))
        self.metadata = (
            '\tbuild\t-ldflags="-s -w '
            '-X github.com/notaryproject/notation/internal/version.Version=1.3.3-trial.1 '
            '-X github.com/notaryproject/notation/internal/version.GitCommit=abc123"\n'
        )

    @patch("check_trial_artifacts.subprocess.run")
    @patch("check_trial_artifacts.subprocess.check_output")
    def test_every_platform_is_scanned(self, metadata, scanner):
        metadata.return_value = self.metadata
        scanner.return_value = subprocess.CompletedProcess([], 0)
        verify(self.directory, "v1.3.3-trial.1", "abc123")
        self.assertEqual(metadata.call_count, 6)
        self.assertEqual(scanner.call_count, 6)

    def test_checksum_mismatch_fails(self):
        self.checksums.write_text(self.checksums.read_text().replace(
            self.checksums.read_text()[:64], "0" * 64
        ))
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            verify(self.directory)

    def test_missing_platform_fails(self):
        next(self.directory.glob("*.zip")).unlink()
        with self.assertRaisesRegex(ValueError, "number of platform archives"):
            verify(self.directory)

    def test_invalid_checksum_filename_fails(self):
        self.checksums.write_text("0" * 64 + "  ../outside.tar.gz")
        with self.assertRaisesRegex(ValueError, "checksum filename"):
            verify(self.directory)

    @patch("check_trial_artifacts.subprocess.run")
    @patch("check_trial_artifacts.subprocess.check_output")
    def test_finding_or_scanner_failure_blocks_qualification(self, metadata, scanner):
        metadata.return_value = self.metadata
        for status in (1, 3):
            scanner.return_value = subprocess.CompletedProcess([], status)
            with self.assertRaisesRegex(ValueError, "vulnerability scan failed"):
                verify(self.directory)

    @patch("check_trial_artifacts.subprocess.check_output")
    def test_version_and_commit_mismatches_fail(self, metadata):
        metadata.return_value = self.metadata
        with self.assertRaisesRegex(ValueError, "Version metadata mismatch"):
            verify(self.directory, "v1.3.3-trial.2", "abc123")
        with self.assertRaisesRegex(ValueError, "Commit metadata mismatch"):
            verify(self.directory, "v1.3.3-trial.1", "def456")

    @patch("check_trial_artifacts.subprocess.run")
    @patch("check_trial_artifacts.subprocess.check_output")
    def test_metadata_prefixes_do_not_match(self, metadata, scanner):
        scanner.return_value = subprocess.CompletedProcess([], 0)
        for output, error in (
            (self.metadata.replace("1.3.3-trial.1", "1.3.3-trial.10"),
             "Version metadata mismatch"),
            (self.metadata.replace("abc123", "abc123def456"),
             "Commit metadata mismatch"),
        ):
            with self.subTest(error=error):
                metadata.return_value = output
                with self.assertRaisesRegex(ValueError, error):
                    verify(self.directory, "v1.3.3-trial.1", "abc123")

    @patch("check_trial_artifacts.subprocess.run")
    @patch("check_trial_artifacts.subprocess.check_output")
    def test_equal_sign_linker_assignments_are_supported(self, metadata, scanner):
        metadata.return_value = self.metadata.replace("-X ", "-X=")
        scanner.return_value = subprocess.CompletedProcess([], 0)
        verify(self.directory, "v1.3.3-trial.1", "abc123")
        self.assertEqual(scanner.call_count, 6)

    @patch("check_trial_artifacts.subprocess.run")
    @patch("check_trial_artifacts.subprocess.check_output")
    def test_duplicate_linker_assignments_fail(self, metadata, scanner):
        metadata.return_value = self.metadata.replace(
            "-s -w", "-s -w -X "
            "github.com/notaryproject/notation/internal/version.Version=1.3.3-trial.10"
        )
        scanner.return_value = subprocess.CompletedProcess([], 0)
        with self.assertRaisesRegex(ValueError, "Version metadata mismatch"):
            verify(self.directory, "v1.3.3-trial.1", "abc123")

    @patch("check_trial_artifacts.subprocess.run")
    @patch("check_trial_artifacts.subprocess.check_output")
    def test_metadata_without_linker_flags_fails(self, metadata, scanner):
        metadata.return_value = (
            "/internal/version.Version=1.3.3-trial.1 "
            "/internal/version.GitCommit=abc123"
        )
        scanner.return_value = subprocess.CompletedProcess([], 0)
        with self.assertRaisesRegex(ValueError, "linker flags"):
            verify(self.directory, "v1.3.3-trial.1", "abc123")

    @patch("check_trial_artifacts.subprocess.run")
    @patch("check_trial_artifacts.subprocess.check_output")
    def test_native_smoke_checks_real_command_output(self, metadata, scanner):
        for path in self.directory.glob("notation_1.*"):
            if not path.name.endswith("_linux_amd64.tar.gz"):
                path.unlink()
        scanner.return_value = subprocess.CompletedProcess([], 0)
        metadata.side_effect = [
            self.metadata, "Version: 1.3.3-trial.1\nGit commit: abc123\n",
        ]
        verify(self.directory, "v1.3.3-trial.1", "abc123", "linux_amd64")
        self.assertEqual(metadata.call_args_list[1].args[0][-1], "version")

    @patch("check_trial_artifacts.subprocess.run")
    @patch("check_trial_artifacts.subprocess.check_output")
    def test_native_smoke_requires_exact_labeled_values(self, metadata, scanner):
        for path in self.directory.glob("notation_1.*"):
            if not path.name.endswith("_linux_amd64.tar.gz"):
                path.unlink()
        scanner.return_value = subprocess.CompletedProcess([], 0)
        for output, error in (
            ("Version: 1.3.3-trial.10\nGit commit: abc123\n",
             "Native CLI version mismatch"),
            ("Version: 1.3.3-trial.1\nGit commit: abc123def456\n",
             "Native CLI commit mismatch"),
            ("Other: 1.3.3-trial.1 abc123\n", "Native CLI version mismatch"),
            ("Version: 1.3.3-trial.1\nVersion: other\nGit commit: abc123\n",
             "Native CLI version mismatch"),
        ):
            with self.subTest(output=output):
                metadata.side_effect = [self.metadata, output]
                with self.assertRaisesRegex(ValueError, error):
                    verify(self.directory, "v1.3.3-trial.1", "abc123", "linux_amd64")


if __name__ == "__main__":
    unittest.main()
