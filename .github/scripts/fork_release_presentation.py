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

"""Reviewed presentation-only migration for the fixed, already approved fork trial."""
import hashlib
import json
import pathlib

import release_issue_topology as threads

RECEIPT_SHA256 = "890550329bc413a5e30550bf1d3144a625e9a62152de60520ab07a2eb2135767"
HOST = "yizha1/notation"
ROUTES = {"yizha1/notation-core-go": 20, "yizha1/notation-go": 16, HOST: 26}
QUALITY_KEYS = ("repository", "month", "tag", "commit", "previous_head", "release_id",
                "assets", "tag_object", "draft_verification", "qualification",
                "release_backport", "merged", "backports", "controller_plan_id", "draft_plan_id")


def receipt():
    raw = (pathlib.Path(__file__).resolve().parents[1] / "release-trials" /
           "manual-review-20261018" / "presentation-v1.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECEIPT_SHA256:
        raise ValueError("Reviewed presentation receipt changed")
    result = json.loads(raw)
    if (result["schema"] != 1 or result["routes"] != ROUTES
            or result["plan_sha256"] != "d7a9cd8f0235aa78b2af278596a76a94f1ad38fff034bce1bfcc19800f62e9b3"
            or result["approval_comment_id"] != 6260449311
            or result["plan_metadata_commit"] != "99ae7773ce6e85f2858c39f4b5727fe149c4ef60"):
        raise ValueError("Presentation receipt changes approved release authority")
    for repository in ROUTES:
        record = result["issues"][repository]
        if threads.body_hash(record["body"]) != record["body_sha256"]:
            raise ValueError("Presentation body hash changed")
    return result


def route_issue(api, repository):
    if repository not in ROUTES:
        raise ValueError("Release issue routing escapes fixed fork trial")
    record = receipt()["issues"][repository]
    issue = api.request(f"repos/{repository}/issues/{ROUTES[repository]}")
    if ("pull_request" in issue or issue.get("user", {}).get("login") != "yizha1"
            or issue.get("state") != "open"
            or threads.body_hash(issue.get("body", "")) not in {record["body_sha256"], record["previous_body_sha256"]}
            or api.issue_editor(repository, ROUTES[repository]) not in (None, "yizha1")):
        raise ValueError("Release issue presentation changed outside reviewed migration")
    return issue


def migrated_approval_body(api, issue):
    expected = receipt()["issues"][HOST]
    if threads.body_hash(issue.get("body", "")) != expected["body_sha256"]:
        return False
    route_issue(api, HOST)
    return True


def check_existing_quality(api, plan):
    data = receipt()
    if {key: plan.get(key) for key in QUALITY_KEYS} != data["existing_core_quality"]:
        raise ValueError("Presentation migration cannot change draft/source/asset/native identity")
    repository = "yizha1/notation-core-go"
    issue = route_issue(api, repository)
    if plan.get("draft_review_issue") != ROUTES[repository]:
        raise ValueError("Existing qualified draft review route changed")
    expected = data["qualification_run"]
    run = api.request(f"repos/{repository}/actions/runs/{expected['id']}")
    if {key: run.get(key) for key in expected} != expected:
        raise ValueError("Original qualified draft workflow provenance changed")
    return issue


def ready_comment(api, plan, body):
    repository = plan["repository"]
    issue = route_issue(api, repository)
    item = threads.comment_once(
        api, "yizha1", repository, ROUTES[repository],
        f"draft-ready:{repository}:{plan['tag']}:{plan['release_id']}",
        "@yizha1\n\n" + body,
    )
    return issue, item


def check_ready_comment(api, plan):
    repository = plan["repository"]
    issue = route_issue(api, repository)
    if plan.get("draft_review_issue") != ROUTES[repository]:
        raise ValueError("Qualified draft release issue route changed")
    item = api.request(f"repos/{repository}/issues/comments/{plan['draft_review_comment']}")
    if (item.get("user", {}).get("login") != "yizha1"
            or item.get("body") != plan["draft_review_body"]
            or item.get("issue_url") != f"https://api.github.com/repos/{repository}/issues/{ROUTES[repository]}"):
        raise ValueError("Qualified draft review notification changed")
    return issue


def notify_failure(api, repository, run_id, stage, reason):
    issue = route_issue(api, repository)
    identity = f"failure:{repository}:{run_id}:{stage}"
    body = (f"@yizha1 Release blocked in `{repository}` at `{stage}`.\n\n"
            f"Reason: {threads.text(reason)}\n\n"
            f"Logs and retained evidence: https://github.com/{repository}/actions/runs/{run_id}\n\n"
            "Owner decision: inspect and resolve the failed gate before a fresh resume. "
            "Scope changes need separate approval. No security waiver or publication is authorized.")
    comment = threads.comment_once(api, "yizha1", repository, issue["number"], identity, body)
    for target in ROUTES:
        if repository.split("/")[1] in threads.PROJECTS[target.split("/")[1]]:
            route_issue(api, target)
            threads.comment_once(
                api, "yizha1", target, ROUTES[target], f"dependency-{identity}",
                f"Blocked by [{repository}#{ROUTES[repository]}]"
                f"({threads.issue_url(repository, ROUTES[repository])}). "
                "Review the dependency release issue for the blocker.",
            )
    return {"action": "notified", "comment": comment["id"], "repository": repository, "issue": issue["number"]}
