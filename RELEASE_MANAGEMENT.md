# Release Management

## Overview

This document describes Notation project release management, which includes release versioning, supported releases, and supported upgrades.

## Glossary of Terms

- **X.Y.Z** refers to the version (based on git tag) of Notation that is released. This is the version of the Notation binary.
- **Breaking changes** refer to schema changes, flag changes, and behavior changes of Notation that may require existing content to be upgraded and may also introduce changes that could break backward compatibility.
- **Milestone** GitHub milestones are used by maintainers to manage each release. PRs and Issues for each release should be created as part of a corresponding milestone.
- **Patch releases** refer to applicable fixes, including security fixes, may be backported to support releases, depending on severity and feasibility.

## Release Versioning

All releases will be of the form _vX.Y.Z_ where X is the major version, Y is the minor version and Z is the patch version. This project strictly follows semantic versioning.

The rest of the doc will cover the release process for the following kinds of releases:

### Major Releases

The Notation project has reached a stable target version of 1.0.0 and all previous RC, BETA, and ALPHA releases will no longer be supported. It's recommended to upgrade the Notation version to v1.0.0 if you are still using a previous version.

### Minor Releases

- **ALPHA:** X.Y.0-alpha.W, W >= 0 (Branch : main)
  - Alpha release, cut from main branch
  - Unstable release which should only be used for early development purposes
  - Released as needed before we cut a beta X.Y release
  - Not supported
- **BETA:** X.Y.0-beta.W, W >= 0 (Branch : main)
  - More stable than the alpha release to be used for testing purposes only
  - Beta release, cut from main branch
  - Released as needed before we cut a stable X.Y release
  - Not supported
- **RC:** X.Y.0-rc.W, W >= 0 (Branch : main)
  - Released as needed before we cut a stable X.Y release
  - soak for ~ 2 weeks before cutting a stable release
  - Bugfixes on new features only as reported through usage
  - Release candidate release, cut from main branch
  - Not supported
- **STABLE:** X.Y.0 (Branch: main)
  - Stable release, cut from master when X.Y milestone is complete
  - X.Y release branch cut for subsequent patch releases
  - Supported as per the supported releases process defined below

### Patch Releases

- Patch Releases X.Y.Z, Z > 0 (Branch: release-X.Y, only cut when a patch is needed)
  - No breaking changes
  - Applicable fixes, including security fixes, may be cherry-picked from master into the latest supported minor release-X.Y branches.
  - Patch release, cut from a release-X.Y branch

### Proposed Monthly Patch Cadence

The latest stable CLI line has a monthly preparation cycle focused on dependency
updates and CVE remediation. Publish a patch only when approved changes are ready;
record an empty cycle as skipped. Urgent security fixes may be released outside
the monthly cycle. This cadence does not change the supported releases policy.
The previous supported line receives patches on demand for customer needs and
applicable security fixes, rather than an automatic monthly dependency refresh.

Each cycle has a tracking issue, a release owner, and a backup. A scheduled
workflow opens the issue on the first day of the month at 09:00 UTC; manual
dispatch provides recovery if scheduled execution is delayed or disabled.
The owner confirms the stable release line, selects patch-safe changes, records
dependency and CVE dispositions, and follows [the release checklist](RELEASE_CHECKLIST.md).
Publication depends on qualification and maintainer approval, not the calendar.

Include compatible direct and transitive dependency updates, patched Go compiler
and standard-library versions, and relevant build-tool updates. Exclude new
features, unrelated refactoring, and breaking behavior. Review upstream release
notes and any increased minimum Go or operating-system requirements. Changes on
`main` do not automatically update a stable branch, particularly when `main`
develops a different major version.

For each vulnerability, record the advisory, affected versions and supported
lines, production versus test/build exposure, reachability, fixed version, owner,
and remediation or explicit exception rationale. Untriaged findings and scanner
execution errors block qualification. Known exploitation or serious reachable
impact requires immediate triage and an out-of-cycle release decision. Keep
embargoed findings in the project's private security process, not public issues.

When library patches are needed, qualify and release `notation-core-go` first,
then `notation-go`, then the CLI consuming those versions. Each project retains
its own release approval requirements. Do not assume independent library and CLI
version numbers must match.

#### Fork-First Trial

This process is initially a trial in `yizha1/notation`, with dependency trials in
`yizha1/notation-core-go` and `yizha1/notation-go`. It is not active upstream.
The scheduler requires the exact fork identity and the repository variable
`PATCH_TRIAL_ENABLED=true`. Official upstream release metadata is read-only;
all issues, preparation PRs, tags, and draft releases target the forks explicitly.
No upstream support-policy change, announcement, or website update is included.

The selected trial dependency updates require Go 1.26 or later. Review that
minimum-toolchain increase explicitly before any upstream adoption.

Use stable release branches or the libraries' official stable tags as candidate
bases. Inventory open Dependabot PRs in all three projects and record updates as
applied, superseded, or deferred with rationale. Do not merge or close upstream
PRs as part of the trial.

Create uniquely numbered, signed trial prerelease tags, for example
`v1.3.3-trial.1`, only after candidate qualification and the user's recorded
approval. Trial approval does not represent an upstream maintainer vote.
Qualify and create the core library draft, then the Go library draft, then the
CLI draft. Every release remains unpublished and clearly marked as a trial.
Tags themselves are public and can resolve as Go module versions even when
GitHub Release objects remain drafts.

Fork library tags do not redirect an upstream Go module requirement. Use explicit
temporary fork replacements in every affected module and record the actual tested
commits. Remove those overrides in favor of approved official library versions
before any separately authorized upstream adoption.

The current CLI candidate requires core `v1.3.1-trial.4` at
`03171674c94728622c5b1534b5e3396fcb468733` and notation-go
`v1.3.3-trial.2` at `e45b78bc5fbd4495b3cbe4effc4e0009c5594642`.
The qualification workflow checks both commits through normal Go module
resolution and requires the exact versioned replacements in the root, E2E,
and plugin modules with workspace overrides disabled. It tests Go 1.26 and
the current stable toolchain. No producer workflow or draft-release polling
is used.
Qualification also requires the pinned license workflow to check headers
and all three dependency manifests. That workflow retains the project's
existing weak-compatible license mode; no new license exception is introduced.

The notation-go trial includes LDAP `v3.4.14`, which rejects malformed
RFC 4514 distinguished names previously accepted in trusted identities.
For example, a JSON policy value containing quotation marks must escape them
at both the JSON and DN layers:
`"x509.subject:C=US,ST=WA,O=My \\\"special\\\" Org"`.
Correct existing malformed policies before using the candidate.

The CLI workflow builds all six platform archives without publishing,
checks their hashes and exact embedded version/commit metadata, and scans
each binary before uploading an unpublished draft. Actionable binary findings
and scanner failures block the upload unless an explicitly scoped trial
disposition applies. Native smoke jobs then download and
inspect the Linux, macOS, and Windows assets.
Go symbol tables are retained for precise binary vulnerability analysis,
while DWARF debugging data remains omitted. Archives are therefore larger
than fully stripped builds; this does not waive vulnerability findings.

The unpublished `yizha1/notation` retry `v1.3.3-trial.2` has one explicit
disposition for GO-2024-2472 in `.github/trial-advisory-disposition.json`.
It records owner `yizha1`, community guidance, the unchanged advisory revision,
and a review deadline of November 3, 2026 (UTC). It cannot apply to another
repository, tag, mismatched commit, or a run on or after that deadline.
The database also lists this advisory for the previous stable `v1.3.2`.
The official released binary embeds `(devel)`, so its binary scan cannot
establish that version-range match; the baseline module-version query does.

This disposition does not fix the CVE or assert that consumers enforce the
published deployment mitigations. Notation verification behavior is unchanged.
Every binary is still scanned with pinned govulncheck `v1.8.0`; complete JSON,
the scanner's rendered text, and per-platform disposition summaries are retained
even when qualification fails. Every other symbol-level finding and every
scanner/protocol error remains blocking. Module-only findings remain visible
and informational, matching the existing symbol-level gate.
JSON scanner success alone is not a clean result: findings are parsed explicitly.
An updated advisory or a listed fixed version requires renewed review.
Without the explicit disposition argument the original fail-on-finding gate
remains in force. Official release adoption requires a separate disposition.
Generated release notes live in the runner's temporary directory, outside
the source checkout, so GoReleaser retains its clean-tree validation.
The first CLI trial tag is preserved as failed packaging evidence; retries
use a new signed tag rather than moving an existing one.

Inspect inherited workflows before activation and prevent external project,
coverage, and notification integrations from running in the trial. Do not copy
upstream secrets or force-update existing fork branches. Verify workflow
permissions, fork authentication, candidate refs, and outgoing scope before each
authorized remote change. Keep scheduling on the fork's default branch and the
qualification/release workflows on the tagged candidate branch.

Successful trial evidence includes an idempotent monthly issue, passing candidate
checks, three signed trial tags in dependency order, unpublished drafts, and
inspected CLI assets, checksums, and version/commit metadata. Record blocked or
skipped outcomes honestly. Upstream adoption and publication require a separate
decision after reviewing that evidence.

## Supported Releases

We expect to "support" n (current) and n-1 major.minor releases. "Support" means we expect users to be running that version in production. For example, when v1.3.0 comes out, v1.1.x will no longer be supported for patches, and we encourage users to upgrade to a supported version as soon as possible. Support will be provided best effort by the maintainers via GitHub issues and pull requests.

We expect users to stay up-to-date with the versions of Notation they use in production, but understand that it may take time to upgrade. We expect users to be running approximately the latest patch release of a given minor release and encourage users to upgrade as soon as possible.

Applicable fixes, including security fixes, may be cherry-picked into the release branch, depending on severity and feasibility. Patch releases are cut from that branch as needed.

## Attribution

This document builds on the ideas and implementations of release processes from Kubernetes, Helm, and Gatekeeper.
