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

"""Reviewed producer-only manifest scope, copied from signed 8ccc implementation."""
import copy
import re
import monthly_release as release
MODE = "execute"

def module_version(value):
    match = re.fullmatch(
        r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
        value if isinstance(value, str) else "",
    )
    if match is None:
        raise ValueError("Invalid producer module version")
    major, minor, patch, prerelease = match.groups()
    identifiers = []
    for identifier in prerelease.split(".") if prerelease is not None else ():
        if identifier.isdecimal():
            if len(identifier) > 1 and identifier.startswith("0"):
                raise ValueError("Invalid numeric producer prerelease identifier")
            identifiers.append((0, int(identifier)))
        else:
            identifiers.append((1, identifier))
    return int(major), int(minor), int(patch), prerelease is None, tuple(identifiers)


def producer_manifests(before_modules, after_modules, producers, producer_modules, current):
    changed = False
    allowed = {f"github.com/notaryproject/{name}" for name in producers}
    def go_version(value):
        if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", value):
            raise ValueError("Invalid producer Go requirement")
        return tuple(map(int, value.split("."))) + (0,) * (3 - len(value.split(".")))
    producer_go = {name: go_version(manifest["Go"]) for name, manifest in producer_modules.items()}
    for directory, before in before_modules.items():
        after = after_modules[directory]
        changed_go = []
        changed_producers = []
        for name, item in producers.items():
            module = f"github.com/notaryproject/{name}"
            def dependency(manifest):
                return ([entry for entry in manifest.get("Require") or [] if entry["Path"] == module],
                        [entry for entry in manifest.get("Replace") or [] if entry["Old"]["Path"] == module])
            if dependency(before) != dependency(after):
                if release.requirement(after, module, item["repository"], MODE) != item["version"]:
                    return False
                changed = True
                changed_go.append(producer_go[name])
                changed_producers.append(name)
        floor = max([go_version(before["Go"]), *changed_go])
        if before["Go"] != after["Go"] and go_version(after["Go"]) != floor:
            return False
        if before.get("Toolchain") != after.get("Toolchain"):
            chain = after.get("Toolchain") or ""
            if not isinstance(chain, str) or not chain.startswith("go"):
                return False
            if not floor <= go_version(chain.removeprefix("go")) <= go_version(current.removeprefix("go")):
                return False
        required = {}
        for name in changed_producers:
            for entry in producer_modules[name].get("Require") or []:
                path, version = entry["Path"], entry["Version"]
                if path not in required or module_version(version) > module_version(required[path]):
                    required[path] = version
        original = {entry["Path"]: entry for entry in before.get("Require") or []}
        updated = {entry["Path"]: entry for entry in after.get("Require") or []}
        for path, previous in original.items():
            if path not in allowed and not previous.get("Indirect") and path in required:
                if (module_version(required[path]) > module_version(previous["Version"])
                        and updated.get(path, {}).get("Version") != required[path]):
                    return False
        def unrelated(manifest, normalize=False):
            result = copy.deepcopy(manifest)
            # MVS can change indirect requirements when a producer is updated.
            result["Require"] = [item for item in result.get("Require") or [] if item["Path"] not in allowed and not item.get("Indirect")]
            for entry in result["Require"]:
                path = entry["Path"]
                previous = original.get(path)
                if (normalize and previous is not None and path in required
                        and entry["Version"] == required[path]
                        and module_version(required[path]) > module_version(previous["Version"])):
                    entry["Version"] = previous["Version"]
            result["Replace"] = [item for item in result.get("Replace") or [] if item["Old"]["Path"] not in allowed]
            result.pop("Go", None)
            result.pop("Toolchain", None)
            return result
        if unrelated(before) != unrelated(after, normalize=True):
            return False
    return changed
