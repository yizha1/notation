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

"""Require the exact tested fork dependencies in every standalone CLI module."""

import argparse
import json
import os
import pathlib
import subprocess


MODULES = (".", "test/e2e", "test/e2e/plugin")
DEPENDENCIES = {
    "notation-core-go": (
        "v1.3.0", "v1.3.1-trial.4",
        "03171674c94728622c5b1534b5e3396fcb468733",
    ),
    "notation-go": (
        "v1.3.2", "v1.3.3-trial.2",
        "e45b78bc5fbd4495b3cbe4effc4e0009c5594642",
    ),
}


def module_metadata(query, directory):
    output = subprocess.check_output(
        ["go", "list", "-m", "-json", query], cwd=directory, text=True,
        env={**os.environ, "GOWORK": "off", "GOFLAGS": "-mod=readonly"},
    )
    return json.loads(output)


def verify(root, lookup=module_metadata):
    root = pathlib.Path(root).resolve()
    for library, (base, version, commit) in DEPENDENCIES.items():
        upstream = f"github.com/notaryproject/{library}"
        fork = f"github.com/yizha1/{library}"
        producer = lookup(f"{fork}@{commit}", root)
        resolved = (
            producer.get("Path"), producer.get("Version"),
            producer.get("Origin", {}).get("Hash"),
        )
        if resolved != (fork, version, commit):
            raise ValueError(
                f"Expected {fork}@{version} at {commit}; resolved {resolved}"
            )
        for module in MODULES:
            dependency = lookup(upstream, root / module)
            replacement = dependency.get("Replace", {})
            actual = (
                dependency.get("Path"), dependency.get("Version"),
                replacement.get("Path"), replacement.get("Version"),
            )
            expected = (upstream, base, fork, version)
            if actual != expected:
                raise ValueError(
                    f"Expected {upstream}@{base} => {fork}@{version} "
                    f"in {module}; got {actual}"
                )
            print(f"{module}: {upstream}@{base} => {fork}@{version} ({commit})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    verify(parser.parse_args().root)
