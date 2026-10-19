# Manual fork release trial

This deployment executes only the owner-approved `manual-review-20261018`
scope in `yizha1/notation-core-go`, `yizha1/notation-go`, and `yizha1/notation`.
It is an isolated fork copy of signed canonical design revision
`8ccc041e0bc2afc5c8a99cda24abd280cdffbd58`, not an upstream implementation change.
It cannot write canonical repositories or the forks' default `main`.

The approval binds signed plan commit
`99ae7773ce6e85f2858c39f4b5727fe149c4ef60`, plan digest
`d7a9cd8f0235aa78b2af278596a76a94f1ad38fff034bce1bfcc19800f62e9b3`,
the unchanged normalized body of [owner review issue](https://github.com/yizha1/notation/issues/26),
and its unedited owner `/approve` comment. The executor rechecks those records
before privileged operations. The reviewed presentation-v1 receipt permits only
the owner's requested issue reorganization, not scope or authority changes.
Any other body edit revokes execution. The owner separately
authorized this deployment and execution through qualified drafts only.

## Deployment and dispatch

The parent deploys reviewed code only to
`monthly-manual-executor-20261018`. The registered
`monthly-patch-release.yml` entrypoint accepts a manual dispatch on that ref.
CLI's existing `notation-release-controller.yml` also calls the same worker.
Neither workflow schedules itself or dispatches consumers automatically.
The source branch remains `monthly-patch-test-main`, and the stable test branch
remains `monthly-patch-test-release-1.3`.

Core and Go need only the thin `monthly-patch-release.yml` caller on the same
deployment branch. Both literal central SHA values must match the reviewed CLI
deployment SHA. They do not copy helpers. Each caller has Contents, Actions,
Issues, and Pull requests read permissions, with two explicitly named secrets.

The owner sets only these new fork Actions variables:

| Variable | Value |
|---|---|
| `MONTHLY_PATCH_FORK_MANUAL_ENABLED` | `true`, only after deployment review |
| `MONTHLY_PATCH_FORK_DEPLOYMENT_SHA` | Exact reviewed full CLI shared-worker commit |
| `MONTHLY_PATCH_FORK_CALLER_SHA` | Exact reviewed full caller commit in this repository |

The executor still requires the existing `MONTHLY_PATCH_ACTOR=yizha1`,
`MONTHLY_PATCH_SIGNER_LOGIN`, `MONTHLY_PATCH_SIGNER_EMAIL`, and optionally
`MONTHLY_PATCH_SIGNER_NAME`. It reuses secrets `MONTHLY_PATCH_TOKEN` and
`MONTHLY_PATCH_SIGNING_KEY`; no new secret or canonical activation is needed.
The signing public key must remain registered on the signer account.
Existing monthly/production flags do not authorize this new deployment.

The bootstrap checks the actual run's reusable-workflow path and resolved SHA,
the caller SHA, fixed owner, reviewed branch tip, and deployment variables before
checking out helpers. The writer repeats those checks and authenticates the token
with `GET /user`. A rerun of an old run cannot write; issue a fresh manual dispatch
to resume. Changing helper/caller code requires a separately reviewed pin update.

The parent starts only Core:

```sh
gh workflow run monthly-patch-release.yml \
  --repo yizha1/notation-core-go \
  --ref monthly-manual-executor-20261018 \
  -f mode=execute -f month=2026-10
```

Subsequent fresh dispatches resume persisted state. Consumer dispatches use the
same command with their repository, but cannot progress before their exact
producers are manually published and anonymously verified.

## Source, candidate, and draft boundaries

The executor accepts only the eleven original Dependabot PR numbers, exact
HEADs, full commit lists, and file scopes in the signed plan. It rechecks current
CI and normal review requirements instead of freezing historical CI observations.
The old CLI PR21 transient failure is not a permanent veto if the unchanged
approved HEAD now passes; changing that HEAD requires new scope approval.
All later source advances must be recorded dependency merge receipts.

If GraphQL reports an empty CI rollup, the fork worker reads real repository-local
check runs and latest commit statuses for the exact PR HEAD through paginated
REST APIs. It checks the PR HEAD before and after discovery. Missing checks,
incomplete responses, failed or pending checks, and API errors do not qualify a
merge. Existing GraphQL failures and merge/review protections remain binding.
Backport branches must run normal CI, including when a fork's existing workflow
needs a manual dispatch at the exact backport HEAD.

The proposed tags remain Core `v1.3.3-manual-review.20261018` and Go/CLI
`v1.3.5-manual-review.20261018`. The executor rechecks absence, existing signed
baselines, source/stable leases, and recorded producer versions. It cannot reopen
the completed 202610 cycle, refresh versions on retry, adopt an unrecorded release,
or move a tag.

Stable changes use signed dependency backport PRs with normal CI/reviews and
normal merge commits. Go/CLI retain separate signed metadata-only PRs. Fork
governance uses an exact unedited owner comment
`/approve-release <signed-metadata-HEAD>` in that PR; it does not impersonate
the upstream maintainers or count their copied roster as fork authority.

Dependabot does not generate the required fork-replacement updates. After
producer publication, a read-only preparation job may produce a producer-only
manifest patch. A separate trusted job verifies its exact source hashes, module
scope, and producer requirements, signs it, and opens an owner-authored source PR.
It is never presented as a Dependabot PR or merged without CI/normal reviews.
Transitive changes must follow the reviewed producer manifest policy.

All reachable findings and scanner/protocol failures block qualification.
The deployment does not inherit prior fork advisory dispositions, and it does not
implement new exceptions or arbitrary source fixes.

The worker qualifies source, package contents, and exact candidate bytes without
release-write credentials. Only the isolated trusted stager signs immutable tags
and creates **true draft prereleases**. The tag is public before draft review;
draft visibility does not hide it. Upload retries retain the original release ID,
asset IDs, hashes, and sizes; changed rebuilt bytes block instead of replacing.

The trusted draft download job receives the release credential only for metadata
and exact asset download. It checks out no candidate and runs no candidate
programs. It verifies downloaded hashes and exports a plan-bound artifact.
Native source/package tests receive only that artifact and the read-only workflow
token, never the release token or key. This avoids relying on read-only tokens
being permitted to access private draft metadata. Credential-bearing asset API
redirects never forward authorization to the storage host.

Each repository has one human release issue: Core20, Go16, and CLI26.
Each shows only its own scope; Go links Core, and CLI links both dependencies.
Only successful downloaded-draft native checks add a qualified-draft comment
to the existing issue, never another human review thread. The technical cycle
issue retains full source/backport/metadata, release and asset identity.
The worker **never publishes**. The owner reviews the draft and uses GitHub
Publish release without changing tag/assets. A later dispatch requires that same
release and bytes, then performs real anonymous public-package verification.
Only a successful verification run unlocks consumers. The unattended trial stops
with the first qualified Core draft while Go and CLI remain blocked.

## Failure notification and local checks

A failed job stops that chain. Once trusted bootstrap identity exists, the
failure job posts one deduplicated comment per run/stage to the affected
repository's release issue, mentioning
`@yizha1` with repository, stage, short reason, run/evidence link, blocked
consumers, and required owner decision. Consumer issues receive only a concise
dependency blocker link, not copied error details. Required check/review blockers
also notify the same repository thread. Routine progress sends no comments.
The parent monitors and reports failures in chat. Early bootstrap/provenance
failures may prevent a credentialed comment safely; the parent monitor must report
those. GitHub inbox/email delivery depends on the owner's notification settings,
especially because the automation uses the owner's own account.

```sh
cd .github/scripts
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  test_fork_manual_executor test_fork_draft_download test_fork_release_presentation \
  test_worker_bootstrap_release test_monthly_release_checks
```

The inherited canonical controller/vote tests are not the fork contract. The
fork-specific suite covers this deliberately different owner protocol and fixed
deployment namespace. Tests are fixtures, not a live release rehearsal. Hosted
credential permissions, source qualification, actual asset transfer, and all
three native operating systems still have to pass during the real run.

## Presentation-only migration

The deployment embeds the exact `presentation-v1.json` receipt and its SHA-256.
It binds the three fixed issue IDs, old and new byte-exact bodies, the same
99ae plan metadata, d7a scope digest, and original owner comment6260449311.
The parent applies only those exact new bodies. Either recorded old or new body
is accepted during this bounded rollout; arbitrary edits or new dependencies fail.
The original bodies remain in the receipt's audit data, not in visible issues.

Core's existing unpublished release416979094 and asset IDs655453799/655453836
retain the same signed source, original bytes/hashes, branch lease, and native
proof from run39210327124 using shared worker059ed8. A reviewed presentation
deployment must not rewrite the old run as if it used new code, rebuild assets,
requalify the draft, or adopt another tag/release. The runtime checks the original
run's immutable provenance as well as the frozen qualification receipt.
This migration does not authorize publication or add bug-fix proposals to the
approved eleven-PR trial.
