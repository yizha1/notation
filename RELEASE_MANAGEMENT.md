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

### Monthly Dependency Patch Workflow

The workflow, activation prerequisites, dependency ordering, retry behavior and
isolated fork modes are documented in
[Monthly dependency patch workflows](.github/MONTHLY_PATCH.md).

The latest stable CLI line has a monthly preparation cycle focused on dependency
updates and CVE remediation. Publish a patch only when approved changes are ready;
record an empty cycle as skipped. Urgent security fixes may be released outside
the monthly cycle. This cadence does not change the supported releases policy.
The previous supported line receives patches on demand for customer needs and
applicable security fixes, rather than an automatic monthly dependency refresh.

The central GitHub Agentic Workflow assesses all three repositories on the first
day at 09:00 UTC, when explicitly enabled. Its validated artifact proposes
release, skip or defer decisions. A separate deterministic controller invokes
included release workers in dependency order, using persistent state rather than
waiting on a runner. Workers merge checked Dependabot updates, backport them,
qualify signed candidates and verify public packages. One planned patch per
included repository avoids known producer updates causing a second consumer
patch. Required checks and reviews are never bypassed. The initial implementation
is assessment-only in the `yizha1` forks; writing rehearsals require explicit
plan approval, credentials, reviewed isolated branches and separate activation.

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

Each project has third-party dependencies. Within the Notation repositories,
notation-go consumes core and the CLI consumes both libraries. A core patch plan
includes notation-go and CLI; a notation-go-only plan includes CLI; a CLI-only
plan skips both libraries. Consumers wait only for producers included in the
approved plan and their checked producer-update PRs. Late, unrelated updates do
not silently expand the plan. Urgent out-of-cycle patches require a separate
decision. Each project retains its checks and independent version numbering.

## Supported Releases

We expect to "support" n (current) and n-1 major.minor releases. "Support" means we expect users to be running that version in production. For example, when v1.3.0 comes out, v1.1.x will no longer be supported for patches, and we encourage users to upgrade to a supported version as soon as possible. Support will be provided best effort by the maintainers via GitHub issues and pull requests.

We expect users to stay up-to-date with the versions of Notation they use in production, but understand that it may take time to upgrade. We expect users to be running approximately the latest patch release of a given minor release and encourage users to upgrade as soon as possible.

Applicable fixes, including security fixes, may be cherry-picked into the release branch, depending on severity and feasibility. Patch releases are cut from that branch as needed.

## Attribution

This document builds on the ideas and implementations of release processes from Kubernetes, Helm, and Gatekeeper.
