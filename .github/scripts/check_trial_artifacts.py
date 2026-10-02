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

"""Verify CLI archives and scan binaries without extracting archive paths."""

import argparse
import hashlib
import pathlib
import subprocess
import tarfile
import tempfile
import zipfile


EXPECTED = {
    "linux_amd64", "linux_arm64", "linux_armv7",
    "darwin_amd64", "darwin_arm64", "windows_amd64",
}


def verify(directory, expected_version=None, expected_commit=None, smoke_platform=None):
    expected = {smoke_platform} if smoke_platform else EXPECTED
    if not expected.issubset(EXPECTED):
        raise ValueError("Unsupported smoke-test platform")
    directory = pathlib.Path(directory)
    checksums = list(directory.glob("*checksums.txt"))
    if len(checksums) != 1:
        raise ValueError("Expected exactly one checksum manifest")
    entries = {}
    for line in checksums[0].read_text().splitlines():
        digest, name = line.split()
        name = name.removeprefix("*")
        if pathlib.PurePosixPath(name).name != name or name in entries:
            raise ValueError("Invalid or duplicate checksum filename")
        entries[name] = digest
    archives = sorted(list(directory.glob("*.tar.gz")) + list(directory.glob("*.zip")))
    if len(archives) != len(expected):
        raise ValueError("Unexpected number of platform archives")
    platforms = set()
    failed = False
    for archive in archives:
        platform = next(
            (item for item in EXPECTED if archive.name.endswith(f"_{item}.tar.gz")
             or archive.name.endswith(f"_{item}.zip")), None
        )
        if platform is None or platform in platforms:
            raise ValueError(f"Unexpected or duplicate platform: {archive.name}")
        platforms.add(platform)
        if entries.get(archive.name) != hashlib.sha256(archive.read_bytes()).hexdigest():
            raise ValueError(f"Checksum mismatch: {archive.name}")
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as source:
                members = [name for name in source.namelist()
                           if pathlib.PurePosixPath(name).name == "notation.exe"]
                if len(members) != 1:
                    raise ValueError(f"Expected one CLI binary in {archive.name}")
                binary = source.read(members[0])
        else:
            with tarfile.open(archive, "r:gz") as source:
                members = [member for member in source.getmembers()
                           if member.isfile()
                           and pathlib.PurePosixPath(member.name).name == "notation"]
                if len(members) != 1:
                    raise ValueError(f"Expected one CLI binary in {archive.name}")
                binary = source.extractfile(members[0]).read()
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / (
                "notation.exe" if platform == "windows_amd64" else "notation"
            )
            path.write_bytes(binary)
            metadata = subprocess.check_output(
                ["go", "version", "-m", str(path)], text=True
            )
            print(metadata)
            if expected_version and f"/internal/version.Version={expected_version.removeprefix('v')}" not in metadata:
                raise ValueError(f"Version metadata mismatch: {archive.name}")
            if expected_commit and f"/internal/version.GitCommit={expected_commit}" not in metadata:
                raise ValueError(f"Commit metadata mismatch: {archive.name}")
            result = subprocess.run(["govulncheck", "-mode=binary", str(path)])
            failed = failed or result.returncode != 0
            if platform == smoke_platform:
                path.chmod(0o755)
                output = subprocess.check_output([str(path), "version"], text=True)
                print(output)
                if expected_version and expected_version.removeprefix("v") not in output:
                    raise ValueError("Native CLI version mismatch")
                if expected_commit and expected_commit not in output:
                    raise ValueError("Native CLI commit mismatch")
    if platforms != expected:
        raise ValueError("Missing platform archives")
    if failed:
        raise ValueError("Binary vulnerability scan failed; draft is not qualified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--version")
    parser.add_argument("--commit")
    parser.add_argument("--smoke-platform", choices=sorted(EXPECTED))
    args = parser.parse_args()
    verify(args.directory, args.version, args.commit, args.smoke_platform)
