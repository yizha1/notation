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

"""Fixed-owner, fixed-plan manual executor authorization for an isolated fork trial."""
import argparse
import base64
import hashlib
import html
import json
import os
import pathlib
import re

import monthly_release as release
from fork_producer_policy import producer_manifests

OWNER = "yizha1"
HOST = "yizha1/notation"
MODE = "execute"
DEPLOYMENT = "monthly-manual-executor-20261018"
CYCLE_ID = "manual-review-20261018"
MONTH = "2026-10"
REPOSITORIES = tuple(f"{OWNER}/{name}" for name in release.PROJECTS)
PLAN_COMMIT = "99ae7773ce6e85f2858c39f4b5727fe149c4ef60"
PLAN_HASH = "d7a9cd8f0235aa78b2af278596a76a94f1ad38fff034bce1bfcc19800f62e9b3"
PLAN_FILE_HASH = "1732d20190901d5972c0f81b5cdfba59610b4d873531de09d0a66c64c74ade95"
BODY_HASH = "5d51fe1ac8d64c66a99ad5ebffdad7ccc4a7c9b5bf2e6180b04a5295d92d0184"
INVENTORY_HASH = "bf076a2646893f1aaa40ed40d310bd7cdbe01e28a5d1ce2f2ff45d1e8da4dc56"
APPROVAL_ID = 6260449311
APPROVAL_NOT_BEFORE = "2026-10-19T05:34:35Z"
ISSUE = 26


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def load_json(text):
    return json.loads(text, object_pairs_hook=unique_object)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def safe_title(value):
    text = html.escape(" ".join(str(value).split())[:1000], quote=True)
    return re.sub(r"[\\`*_{}\[\]()#+.!|@]", lambda match: f"&#{ord(match[0])};", text)


def content_bytes(api, repository, path, ref):
    item = api.request(f"repos/{repository}/contents/{path}?ref={ref}")
    if item.get("encoding") != "base64" or item.get("type") != "file":
        raise ValueError("Missing immutable plan content")
    return base64.b64decode("".join(item["content"].split()), validate=True)


def approved_plan(api):
    branch = api.request(f"repos/{HOST}/git/ref/heads/monthly-plan-review-manual-20261018")
    signed = api.request(f"repos/{HOST}/commits/{PLAN_COMMIT}")
    if (branch.get("object", {}).get("sha") != PLAN_COMMIT
            or signed.get("sha") != PLAN_COMMIT
            or signed.get("commit", {}).get("verification", {}).get("verified") is not True):
        raise ValueError("Signed plan artifact branch changed")
    raw = content_bytes(api, HOST, f".github/release-trials/{CYCLE_ID}/plan.json", PLAN_COMMIT)
    if hashlib.sha256(raw).hexdigest() != PLAN_FILE_HASH:
        raise ValueError("Approved plan file changed")
    envelope = load_json(raw)
    payload = envelope["payload"]
    if envelope["plan_sha256"] != PLAN_HASH or digest(payload) != PLAN_HASH:
        raise ValueError("Approved scope digest mismatch")
    inventory = content_bytes(api, HOST, f".github/release-trials/{CYCLE_ID}/inventory.json", PLAN_COMMIT)
    if hashlib.sha256(inventory).hexdigest() != INVENTORY_HASH or payload["inventory_sha256"] != INVENTORY_HASH:
        raise ValueError("Captured inventory changed")
    if (payload["cycle_id"] != CYCLE_ID or payload["owner"] != OWNER
            or {item["repository"] for item in payload["repositories"]} != set(REPOSITORIES)):
        raise ValueError("Plan escapes fixed fork trial")
    issue = api.request(f"repos/{HOST}/issues/{ISSUE}")
    if (issue.get("user", {}).get("login") != OWNER or issue.get("state") != "open"
            or "pull_request" in issue or hashlib.sha256(issue.get("body", "").strip().encode()).hexdigest() != BODY_HASH):
        raise ValueError("Owner-approved plan issue changed or closed")
    editor = api.issue_editor(HOST, ISSUE)
    if editor not in {None, OWNER}:
        raise ValueError("Plan issue has an untrusted editor")
    approval = api.request(f"repos/{HOST}/issues/comments/{APPROVAL_ID}")
    if (approval.get("user", {}).get("login") != OWNER or approval.get("user", {}).get("type") != "User"
            or approval.get("body", "").strip() != "/approve"
            or approval.get("created_at") != approval.get("updated_at")
            or approval.get("created_at", "") < APPROVAL_NOT_BEFORE
            or approval.get("issue_url") != f"https://api.github.com/repos/{HOST}/issues/{ISSUE}"):
        raise ValueError("Exact owner approval was deleted, edited or revoked")
    return payload


def invocation(api, repository, readonly=False):
    environment = os.environ
    worker = environment.get("MONTHLY_PATCH_WORKER_SHA", "")
    caller = environment.get("GITHUB_SHA", "")
    if (repository not in REPOSITORIES or environment.get("GITHUB_REPOSITORY") != repository
            or environment.get("GITHUB_REF") != f"refs/heads/{DEPLOYMENT}"
            or environment.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or environment.get("GITHUB_ACTOR") != OWNER or environment.get("MONTHLY_PATCH_ACTOR") != OWNER
            or environment.get("MONTHLY_PATCH_FORK_MANUAL_ENABLED") != "true"
            or not release.SHA.fullmatch(worker) or not release.SHA.fullmatch(caller)
            or worker != environment.get("MONTHLY_PATCH_FORK_DEPLOYMENT_SHA")
            or caller != environment.get("MONTHLY_PATCH_FORK_CALLER_SHA")):
        raise ValueError("Dispatch is not the explicitly pinned fork deployment")
    run_id = environment.get("GITHUB_RUN_ID", "")
    if not run_id.isdecimal() or int(run_id) <= 0:
        raise ValueError("Missing workflow run identity")
    run = api.request(f"repos/{repository}/actions/runs/{run_id}")
    expected = f"{HOST}/.github/workflows/monthly-patch-worker.yml@{worker}"
    references = [item for item in run.get("referenced_workflows", [])
                  if item.get("path", "").split("@", 1)[0] == expected.split("@", 1)[0]]
    if (run.get("repository", {}).get("full_name") != repository or run.get("event") != "workflow_dispatch"
            or run.get("head_sha") != caller or run.get("head_branch") != DEPLOYMENT
            or run.get("actor", {}).get("login") != OWNER or run.get("run_attempt") != 1
            or references != [next((item for item in references if item.get("path") == expected
                                   and item.get("sha") == worker), None)]):
        raise ValueError("Fork workflow run or actual reusable provenance changed; dispatch a fresh resume")
    metadata = api.request(f"repos/{repository}")
    if (metadata.get("fork") is not True or metadata.get("owner", {}).get("login") != OWNER
            or metadata.get("full_name") != repository):
        raise ValueError("Repository is not an owner-controlled fork")
    if not readonly and api.request("user").get("login") != OWNER:
        raise ValueError("Release credential is not the fixed trial owner")
    if api.request(f"repos/{HOST}/branches/{DEPLOYMENT}")["commit"]["sha"] != worker:
        raise ValueError("Shared fork deployment ref moved during execution")
    if api.request(f"repos/{repository}/branches/{DEPLOYMENT}")["commit"]["sha"] != caller:
        raise ValueError("Caller fork deployment ref moved during execution")
    return worker


def snapshot_for(plan, repository):
    if repository not in REPOSITORIES:
        raise ValueError("Not an authorized fork repository")
    matches = [item for item in plan["repositories"] if item["repository"] == repository]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate fork snapshot")
    source = matches[0]
    return {
        "baseline": source["baseline_tag"], "baseline_sha": source["baseline_commit"],
        "baseline_release_id": source["baseline_release_id"],
        "main": source["source_branch"], "main_head": source["source_head"],
        "branch": source["release_branch"], "release_head": source["release_head"],
        "tag": source["proposed_prerelease_tag"], "pulls": source["pulls"],
        "automation_sha": os.environ.get("GITHUB_SHA", source["default_head"]),
        "producer_requirements": source["producer_requirements"],
    }


def compare_commits(api, repository, base, head):
    commits = []
    for page in range(1, 11):
        result = api.request(f"repos/{repository}/compare/{base}...{head}?per_page=100&page={page}")
        if result.get("status") not in {"identical", "ahead"} or result.get("behind_by") != 0:
            raise ValueError("Fork source diverged from approved progress")
        commits.extend(result["commits"])
        if len(commits) == result["ahead_by"]:
            if any(not release.SHA.fullmatch(item.get("sha", "")) for item in commits):
                raise ValueError("Invalid source comparison")
            return {item["sha"] for item in commits}
        if len(result["commits"]) < 100:
            raise ValueError("Incomplete source progress comparison")
    raise ValueError("Source comparison exceeds reviewed bound")


def worker_authorization(api, repository, month, plan=None, allow_previous=False, notification=False, readonly=False):
    if month != MONTH:
        raise ValueError("Trial cannot reopen another cycle")
    invocation(api, repository, readonly=readonly)
    approved = approved_plan(api)
    snapshot = snapshot_for(approved, repository)
    if snapshot["main"] != "monthly-patch-test-main" or snapshot["branch"] != "monthly-patch-test-release-1.3":
        raise ValueError("Fork branches escape isolated namespace")
    cycle = release.Cycle(api, repository, MONTH, MODE, CYCLE_ID)
    state = cycle.state
    if state is None:
        if (api.optional(f"repos/{repository}/git/ref/tags/{snapshot['tag']}") is not None
                or api.optional(f"repos/{repository}/releases/tags/{snapshot['tag']}") is not None
                or any(item.get("tag_name") == snapshot["tag"] for item in api.pages(f"repos/{repository}/releases"))):
            raise ValueError("Reserved new-trial tag or release already exists without a recorded cycle")
    if plan and any(plan.get(key) != snapshot[key] for key in ("baseline", "main", "branch", "tag")):
        raise ValueError("Worker candidate differs from owner-approved scope")
    if plan and (plan.get("controller_issue") != ISSUE or plan.get("controller_plan_id") != PLAN_HASH):
        raise ValueError("Worker candidate has another plan approval receipt")
    current = api.request(f"repos/{repository}/branches/{snapshot['main']}")["commit"]["sha"]
    merged = (state or {}).get("merged", [])
    if compare_commits(api, repository, snapshot["main_head"], current) != {item["commit"] for item in merged}:
        raise ValueError("Fork source contains unrecorded merges or edits")
    if not state or state["status"] in {"merging", "waiting"}:
        if api.request(f"repos/{repository}/branches/{snapshot['branch']}")["commit"]["sha"] != snapshot["release_head"]:
            raise ValueError("Initial fork release branch lease changed")
    producers = {}
    for dependency in snapshot["producer_requirements"]:
        producer = dependency["repository"]
        if producer not in REPOSITORIES:
            raise ValueError("Producer escapes owner namespace")
        upstream = release.Cycle(api, producer, MONTH, MODE, CYCLE_ID).state
        if not upstream or upstream["status"] != "published" or upstream["tag"] != dependency["exact_version"]:
            raise ValueError(f"Waiting for owner publication and anonymous verification of {producer}")
        release.assert_tag(api, upstream)
        release.check_public_assets(api, upstream)
        finished = api.request(f"repos/{producer}/actions/runs/{upstream['public_verification_run']}")
        if finished.get("status") != "completed" or finished.get("conclusion") != "success":
            raise ValueError("Producer public verification workflow has not succeeded")
        producers[producer.split("/")[1]] = {"repository": producer, "version": dependency["exact_version"]}
    return {"snapshot": snapshot, "producers": producers, "plan_id": PLAN_HASH, "issue": ISSUE}


def propagation_branch(month, plan_id):
    if month != MONTH or plan_id != PLAN_HASH:
        raise ValueError("Unapproved propagation cycle")
    return f"monthly-patch/{CYCLE_ID}/{PLAN_HASH}/producer"


def fork_propagation_pull(api, repository, pull, authorization):
    branch = propagation_branch(MONTH, PLAN_HASH)
    if pull.get("head", {}).get("ref") != branch:
        return False
    if (pull.get("user", {}).get("login") != OWNER
            or pull.get("head", {}).get("repo", {}).get("full_name") != repository
            or pull.get("base", {}).get("ref") != authorization["snapshot"]["main"]):
        raise ValueError("Producer-only PR has an untrusted identity")
    marker = f"<!-- notation-fork-propagation:{MONTH}:{PLAN_HASH} -->"
    blocks = re.findall(r"```json\n(.*?)\n```", pull.get("body") or "", re.DOTALL)
    if marker not in (pull.get("body") or "") or len(blocks) != 1:
        raise ValueError("Missing producer-only scope receipt")
    record = load_json(blocks[0])
    if (record.get("repository") != repository or record.get("plan_id") != PLAN_HASH
            or record.get("controller_issue") != ISSUE or record.get("producers") != authorization["producers"]
            or record.get("head") != pull["head"]["sha"]):
        raise ValueError("Producer-only receipt changed")
    from monthly_release_pr import commit_identity
    commit_identity(api, repository, record["head"])
    paths = [file["filename"] for file in api.pages(f"repos/{repository}/pulls/{pull['number']}/files")]
    allowed = {f"{directory}/go.{extension}".removeprefix("./")
               for directory in release.modules(repository) for extension in ("mod", "sum")}
    if not paths or not set(paths) <= allowed:
        raise ValueError("Producer-only PR escapes module files")
    before = {directory: api.manifest(repository, record["base"], directory) for directory in release.modules(repository)}
    after = {directory: api.manifest(repository, record["head"], directory) for directory in release.modules(repository)}
    source = {name: api.manifest(item["repository"], item["version"], ".")
              for name, item in authorization["producers"].items()}
    if not producer_manifests(before, after, authorization["producers"], source, release.run(["go", "env", "GOVERSION"]).strip()):
        raise ValueError("Producer-only PR changes unrelated manifest authority")
    return True


def scoped_pull(api, repository, pull, authorization, merged=()):
    expected = next((item for item in authorization["snapshot"]["pulls"] if item["number"] == pull["number"]), None)
    if expected is None:
        return fork_propagation_pull(api, repository, pull, authorization)
    if (not release.dependabot(pull, "monthly-patch-test-main")
            or pull["head"]["sha"] != expected["head"]
            or pull["head"]["repo"]["full_name"] != repository):
        raise ValueError("Approved Dependabot source HEAD or actor changed")
    commits = list(api.pages(f"repos/{repository}/pulls/{pull['number']}/commits"))
    files = list(api.pages(f"repos/{repository}/pulls/{pull['number']}/files"))
    if ([item["sha"] for item in commits] != [item["sha"] for item in expected["commits"]]
            or sorted(item["filename"] for item in files) != sorted(expected["files"])):
        raise ValueError("Approved full commit/file inventory changed")
    if merged and pull.get("merged_at"):
        if not any(item["number"] == pull["number"] and item["commit"] == pull.get("merge_commit_sha") for item in merged):
            raise ValueError("Merged PR has no exact persisted receipt")
    return True


def failure(api, repository, stage, reason):
    if repository not in REPOSITORIES or not re.fullmatch(r"[a-z][a-z0-9-]{0,50}", stage):
        raise ValueError("Failure notification escapes fixed fork trial")
    invocation(api, repository)
    run_id = int(os.environ["GITHUB_RUN_ID"])
    marker = f"<!-- fork-manual-failure:{CYCLE_ID}:{repository}:{run_id}:{stage} -->"
    comments = list(api.pages(f"repos/{HOST}/issues/{ISSUE}/comments"))
    matches = [item for item in comments if marker in (item.get("body") or "")]
    if matches:
        if len(matches) != 1 or matches[0].get("user", {}).get("login") != OWNER:
            raise ValueError("Failure receipt has an untrusted duplicate")
        return {"action": "already-notified", "comment": matches[0]["id"]}
    downstream = [repo for repo in REPOSITORIES
                  if repository.split("/")[1] in release.PROJECTS[repo.split("/")[1]]]
    body = (f"{marker}\n@yizha1 Fork trial stopped in `{repository}` at `{stage}`.\n\n"
            f"Reason: {safe_title(reason)}\n\n"
            f"Logs and retained evidence: https://github.com/{repository}/actions/runs/{run_id}\n\n"
            f"Blocked consumers: {', '.join(downstream) or 'None; this repository remains blocked'}.\n\n"
            "Owner decision: inspect the failed gate and approve any scope change separately. "
            "Automation granted no security waiver, moved no tag, and did not publish a release. "
            "A fresh resume must pass all gates. "
            "GitHub inbox/email delivery depends on notification settings; the supervising agent also reports in chat.")
    comment = api.request(f"repos/{HOST}/issues/{ISSUE}/comments", "POST", {"body": body})
    return {"action": "notified", "comment": comment["id"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("authorize", "failure"))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--stage", default="workflow")
    parser.add_argument("--reason", default="A required job failed. Inspect retained evidence before retrying.")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    api = release.GitHub()
    result = (worker_authorization(api, args.repository, MONTH) if args.command == "authorize"
              else failure(api, args.repository, args.stage, args.reason))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "authorization.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
