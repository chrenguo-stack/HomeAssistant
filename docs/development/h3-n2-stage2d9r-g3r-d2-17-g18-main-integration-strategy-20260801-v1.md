# H3/N2 Stage2D-9R G3R D2-17 G18 main integration strategy

## Authorization

This integration is created under:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G18-FINAL-CLOSURE-MAIN-INTEGRATION-STRATEGY-AND-CONSOLIDATED-PR-AUTHORIZATION-20260801-01`

The authorization permits dependency inventory, integration planning, creation of a Draft consolidated PR from the exact current `main`, CI execution, and a public review Artifact. It does not authorize Ready, merge, release, tag, deployment, physical access, replay, or private-runtime access.

## Exact base and divergence

The consolidated branch starts from exact `main`:

`6525e8a81c140853e2b0de0eba78ad1227ca7305`

The historical final closure HEAD is:

`570279e5df22c9092dad670dc9a6bf762589471c`

The two histories are diverged at merge base:

`25a21b38d470992b09c64820d46f56b39917f0dc`

At review time the historical closure branch was 1063 commits ahead of and 13 commits behind current `main`. Therefore the historical tree is not rebased, merged, retargeted, or copied wholesale.

## Integration decision

Only the frozen, secret-free final G18 closure record is imported as content-addressed archival evidence:

1. the complete G18 host-only closure terminal;
2. the D2-17 final closure decision;
3. the final closure contract.

The imported files are byte-identical to the corresponding files at historical closure HEAD `570279e5df22c9092dad670dc9a6bf762589471c`, as identified by their source Git blob SHA-1 values in the integration inventory.

## Excluded history

The G13 through G18 development chain contains physical authorization records, one-shot drivers, host-only forensic exporters, compatibility repairs, static-check workflows, and tests tied to retired or consumed generations. Those files remain available through their exact PRs, HEADs, CI runs, and Artifacts, but are not copied into this main integration PR.

This exclusion prevents:

- revival of retired G13–G18 executors;
- accidental replay or authorization reuse;
- importing private-package assumptions into `main`;
- replacing current-main files with the historical branch tree;
- silently carrying the 1063-commit predecessor stack into the final closure record.

## Verification contract

The consolidated CI must verify:

- the G18 terminal canonical semantic self-binding;
- exact cross-document terminal, authorization, lineage, and closure hashes;
- `PASS / CONSUMED_PASS / CLOSED` terminal state;
- all physical-operation flags remain false for the host-only closure reconstruction;
- replay, retry, and physical rerun remain forbidden;
- the integration inventory is based on exact current-main SHA;
- only the three final closure source documents are classified as imported;
- no private paths, raw logs, command material, or secret values are included;
- the review Artifact contains all integration files, `SOURCE_SHA`, and `SHA256SUMS`.

## Remaining gate

The resulting pull request must remain Draft. Ready and merge require a separate exact authorization after CI and Artifact review. Release, tag, deployment, ACTIVATE, CLEANUP, physical rerun, and any G13–G18 replay remain forbidden.
