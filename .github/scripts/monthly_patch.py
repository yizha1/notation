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

"""Fork-only monthly issue preparation and release-line tag selection."""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys


TRIAL_REPOSITORY = "yizha1/notation"
SOURCE_REPOSITORY = "notaryproject/notation"
DEPENDENCY_REPOSITORIES = (
    "notaryproject/notation-core-go",
    "notaryproject/notation-go",
    SOURCE_REPOSITORY,
)
STABLE_TAG = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CANDIDATE_TAG = re.compile(
    r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-trial\.[1-9]\d*)?$"
)


def version(tag):
    match = STABLE_TAG.fullmatch(tag)
    return tuple(map(int, match.groups())) if match else None


def latest_stable(releases):
    versions = [
        (version(release["tag_name"]), release["tag_name"])
        for release in releases
        if not release["draft"]
        and not release["prerelease"]
        and version(release["tag_name"]) is not None
    ]
    if not versions:
        raise ValueError("No official stable SemVer release found")
    return max(versions)[1]


def previous_tag(candidate, tags):
    match = CANDIDATE_TAG.fullmatch(candidate)
    if not match:
        raise ValueError("Expected a stable version or a numbered trial prerelease")
    target = tuple(map(int, match.groups()))
    candidates = [
        (version(tag), tag)
        for tag in tags
        if version(tag) is not None
        and version(tag)[:2] == target[:2]
        and version(tag) < target
    ]
    if not candidates:
        raise ValueError("No preceding stable tag in the candidate release line")
    return max(candidates)[1]


def marker(month):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("Month must have YYYY-MM format")
    return f"<!-- notation-monthly-patch:{month} -->"


def require_trial(repository, enabled):
    if repository != TRIAL_REPOSITORY or enabled != "true":
        raise ValueError("Writes require yizha1/notation and explicit trial opt-in")


class GitHub:
    def __init__(self, token):
        self.token = token

    def request(self, path, data=None):
        command = ["gh", "api", path, "--method", "POST" if data is not None else "GET"]
        environment = os.environ.copy()
        if self.token:
            environment["GH_TOKEN"] = self.token
        if data is not None:
            command.extend(["--input", "-"])
        output = subprocess.check_output(
            command,
            input=json.dumps(data) if data is not None else None,
            text=True,
            env=environment,
        )
        return json.loads(output)

    def pages(self, path):
        for page in range(1, 1001):
            separator = "&" if "?" in path else "?"
            items = self.request(f"{path}{separator}per_page=100&page={page}")
            if not isinstance(items, list):
                raise ValueError("Expected a paginated GitHub list")
            yield from items
            if len(items) < 100:
                return
        raise ValueError("Pagination limit exceeded; refusing incomplete discovery")


def issue_body(month, tag, updates=()):
    major, minor, _ = version(tag)
    inventory = "\n".join(
        f"- [{repository}#{pull['number']}]({pull['html_url']}): "
        f"{pull['title']} (base: `{pull['base']['ref']}`)"
        for repository, pull in updates
    ) or "No open upstream Dependabot PRs found at initiation."
    return f"""{marker(month)}
# Monthly patch trial: {month}

Trial only; not an official Notary Project release.
Official baseline: [{tag}](https://github.com/{SOURCE_REPOSITORY}/releases/tag/{tag}).
Proposed CLI branch: `release-{major}.{minor}`. Confirm before preparation.

## Ownership and candidate

- Trial owner: unassigned
- Backup: unassigned
- Confirmed branch:
- Candidate version and exact commit:
- Previous stable tag:

## Checklist

- [ ] Confirm the official stable line and fork destination.
- [ ] Inventory Dependabot PRs in notation-core-go, notation-go, and notation.
- [ ] Record each update as applied, superseded, or deferred with rationale.
- [ ] Triage public CVEs, toolchain updates, and test/build exposure.
- [ ] Check previous-line customer demand and applicable security fixes.
- [ ] Test and scan notation-core-go; approve its signed trial tag and draft.
- [ ] Consume the tested core tag in notation-go; test, scan, and draft it.
- [ ] Consume both tested library tags in all applicable CLI modules.
- [ ] Link passing build, vet/lint, race-test, E2E, and vulnerability evidence.
- [ ] Review the release-line changelog and exact candidate commit.
- [ ] Record trial approval before pushing the signed CLI trial tag.
- [ ] Inspect artifact checksums, version/commit metadata, and platform checks.
- [ ] Confirm all three draft releases remain unpublished.
- [ ] Record draft-ready, skipped (no eligible changes), or blocked outcome.

## Dependency and CVE dispositions

Open upstream Dependabot PRs at initiation (read-only inventory):

{inventory}

For each finding, record its advisory, affected module/toolchain and lines,
production/test/build exposure, reachability, fixed version, owner, and rationale.
Do not disclose embargoed findings here. Scanner errors and untriaged findings
block qualification. Urgent security fixes need not wait for the next month.

## Evidence and outcome

Library tags and drafts:
CLI tag and draft:
Check runs:
Platform smoke tests:
Unresolved findings or deferred updates:
Outcome:

No upstream writes, publication, website updates, or community announcements.
Fork replacements must be removed before any separately approved upstream adoption.
"""


def initiate(api, repository, enabled, month, write=False):
    require_trial(repository, enabled)
    identity = marker(month)
    matches = [
        issue
        for issue in api.pages(f"repos/{repository}/issues?state=all")
        if "pull_request" not in issue and identity in (issue.get("body") or "")
    ]
    if len(matches) > 1:
        raise ValueError("Multiple monthly tracking issues found; reconcile manually")
    if matches:
        return {"outcome": "existing", "url": matches[0]["html_url"]}
    tag = latest_stable(list(api.pages(f"repos/{SOURCE_REPOSITORY}/releases")))
    major, minor, _ = version(tag)
    api.request(f"repos/{repository}/branches/release-{major}.{minor}")
    updates = [
        (source, pull)
        for source in DEPENDENCY_REPOSITORIES
        for pull in api.pages(f"repos/{source}/pulls?state=open")
        if pull["user"]["login"] == "dependabot[bot]"
    ]
    payload = {
        "title": f"Monthly patch trial: {month}",
        "body": issue_body(month, tag, updates),
    }
    if not write:
        return {"outcome": "preview", "repository": repository, "payload": payload}
    issue = api.request(f"repos/{repository}/issues", payload)
    return {"outcome": "created", "url": issue["html_url"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    issue_parser = subparsers.add_parser("initiate")
    issue_parser.add_argument(
        "--month", default=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    )
    issue_parser.add_argument("--write", action="store_true")
    tag_parser = subparsers.add_parser("previous-tag")
    tag_parser.add_argument("candidate")
    args = parser.parse_args()
    try:
        if args.command == "previous-tag":
            tags = subprocess.check_output(
                ["git", "tag", "--list", "v*"], text=True
            ).splitlines()
            print(previous_tag(args.candidate, tags))
        else:
            print(json.dumps(initiate(
                GitHub(os.environ.get("GH_TOKEN")),
                os.environ.get("GITHUB_REPOSITORY", ""),
                os.environ.get("PATCH_TRIAL_ENABLED", ""),
                args.month,
                args.write,
            ), indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Monthly patch preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
