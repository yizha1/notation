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

"""Trusted metadata/download-only draft bridge. Never executes candidate code."""
import argparse
import hashlib
import json
import pathlib

import monthly_release as release
import notation_release_controller as controller
from test_monthly_public_release import download_draft


def download(api, manifest, output):
    repository = manifest["repository"]
    controller.worker_authorization(api, repository, controller.MONTH, manifest)
    cycle = release.Cycle(api, repository, controller.MONTH, "execute", controller.CYCLE_ID)
    state = cycle.state
    keys = ("status", "commit", "tag", "release_id", "assets", "controller_plan_id")
    if not state or state["status"] != "draft" or any(state.get(key) != manifest.get(key) for key in keys):
        raise ValueError("Recorded draft changed before trusted download")
    release.assert_tag(api, state)
    release.check_release_assets(api, state, True)
    output.mkdir(parents=True, exist_ok=True)
    for asset in state["assets"]:
        content = download_draft(repository, asset["id"])
        if len(content) != asset["size"] or hashlib.sha256(content).hexdigest() != asset["sha256"]:
            raise ValueError("Draft download differs from exact qualified bytes")
        (output / asset["name"]).write_bytes(content)
    release.check_release_assets(api, state, True)
    (output / "draft-download-receipt.json").write_text(json.dumps({
        "plan_sha256": controller.digest(state), "repository": repository,
        "release_id": state["release_id"], "tag": state["tag"], "assets": state["assets"],
    }, indent=2) + "\n")
    (output / "plan.json").write_text(json.dumps(state, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    download(release.GitHub(), json.loads(args.plan.read_text()), args.output)
