# Release Checklist

## Overview

This document describes the checklist to publish a release for Notation CLI via GitHub workflow.

## Release Process

For the proposed monthly cadence, first confirm the latest stable line, assign
an owner and backup, and link the tracking issue. Skip an empty cycle rather than
publishing a no-op version. Urgent security releases need not wait for the next
cycle. See [Release Management](RELEASE_MANAGEMENT.md#proposed-monthly-patch-cadence).

### Monthly Candidate Qualification

- Inventory dependency updates and CVEs against the actual stable candidate
  branch, not only `main`. Include the compiler used for release artifacts.
- Record applied, superseded, and deferred Dependabot updates across
  `notation-core-go`, `notation-go`, and the CLI. If library patches are needed,
  qualify and release core first, then the Go library, then the CLI.
- Review all three CLI module graphs: root, `test/e2e`, and `test/e2e/plugin`.
  Update and verify the applicable `go.mod` and `go.sum` files.
- Run existing build, vet/lint, race-enabled unit, and E2E checks. Run pinned
  `govulncheck` checks, including tests, for all three modules. Scanner errors and
  untriaged findings block release; do not suppress exit codes.
- Record the compiler version and compatibility implications of toolchain
  upgrades. Review production binaries separately from source and test findings.
- Generate the changelog from the preceding stable tag in the same release line,
  not whichever tag was most recently created across all branches.
- Confirm the approved, tested candidate commit is the exact commit being tagged.
  Review expected OS/architecture assets, checksums, metadata, and platform smoke
  test evidence before publishing. Do not move a published version tag.

### Fork Trial Only

- Use explicit `yizha1` repository destinations and verified credentials.
  Upstream release discovery is read-only. Inspect inherited external integrations
  before enabling trial workflows.
- Obtain trial approval before each library tag, then the CLI tag. Use unique
  signed `-trial.N` prerelease versions, not official stable versions.
- Consume the tested library tags with explicit temporary fork replacements.
  Verify the packaged binary uses the same dependency sources.
- Confirm tag-triggered qualification and artifact generation pass. Inspect the
  draft artifacts and record evidence in the fork tracking issue.
- Leave all trial drafts unpublished. Do not request upstream release votes,
  update the website, or announce an official release.

The steps below remain the official release process. A fork rehearsal does not
fulfill upstream approval requirements.

- Check if there are any security vulnerabilities fixed and security advisories published before a release. Security advisories should be linked on the release notes.
- Determine a [SemVer2](https://semver.org/)-valid version prefixed with the letter `v` for release. For example, `version="v1.0.0-alpha.1"`.
- If there is new release in [notation-go](https://github.com/notaryproject/notation-go) or [notation-core-go](https://github.com/notaryproject/notation-core-go) library that are required to be upgraded in Notation CLI, update the dependency versions in the follow `go.mod` and `go.sum` files of Notation CLI:
  - [go.mod](go.mod), [go.sum](go.sum)
  - [test/e2e/go.mod](test/e2e/go.mod), [test/e2e/go.sum](test/e2e/go.sum)
  - [test/e2e/plugin/go.mod](test/e2e/plugin/go.mod) and [test/e2e/plugin/go.sum](test/e2e/plugin/go.sum)
- Open a PR submit the changes in the previous step to the notation repository. Please make sure this PR is merged with all E2E test cases passed before starting the next step. See [PR #754](https://github.com/notaryproject/notation/pull/754) as an example.
- Create another PR to update the Notation CLI version with a single commit when PRs in above steps are merged. The commit message MUST follow the [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) and could be `bump: tag and release $version`. Record the digest of that commit as `<commit_digest>`. This PR is also used for voting purpose of the new release. Add the link of change logs and repo-level maintainer list in the PR's description. The PR title could be `bump: tag and release $version`. Make sure to reach a majority of approvals from the [repo-level maintainers](MAINTAINERS) before releasing it. This PR should be merged using [Create a merge commit](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github) method in GitHub. See [PR #748](https://github.com/notaryproject/notation/pull/748) as an example.
- After the voting PR is merged in the [Notation](https://github.com/notaryproject/notation.git) repository, execute `git clone git@github.com:notaryproject/notation.git` to clone the repository to your local file system.
- Enter the cloned repository and execute `git checkout <commit_digest>` to switch to the specified branch based on the voting result.
- Create a tag by running `git tag -am $version $version -s`.
- Run `git tag` and ensure the desired tag name in the list looks correct, then push the new tag directly to the repository by running `git push origin $version`.
- Wait for the completion of the GitHub action [release-github](https://github.com/notaryproject/notation/actions/workflows/release-github.yml).
- Check the new draft release, revise the release description, and publish the release.
- Update the necessary documentation in the [notaryproject.dev](https://github.com/notaryproject/notaryproject.dev) repository to reflect the changes of the release on the Notary Project website, includes but not limited to [installation guide](https://github.com/notaryproject/notaryproject.dev/blob/main/content/en/docs/installation/cli.md), [user guide](https://github.com/notaryproject/notaryproject.dev/tree/main/content/en/docs/how-to), [banner](https://github.com/notaryproject/notaryproject.dev/blob/main/layouts/partials/banner.html), [release blog](https://github.com/notaryproject/notaryproject.dev/tree/main/content/en/blog).
- Announce the new release in the Notary Project community.
