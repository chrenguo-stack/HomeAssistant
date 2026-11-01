# N3W T1 per-device fresh Armbian automated deployment — F2 read-only preflight preparation

Date: 2026-10-14

TASK=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F2_FRESH_T1_READONLY_PREFLIGHT_PREPARATION_20261014_01
BASE_MAIN=3e05e82a7d7e871d2966e78e8cb5caff601a0152
PREDECESSOR_PR=541
PREDECESSOR_PR_STATE=MERGED
F1B=CLOSED_PASS
CI_CONVERGENCE_V1=CLOSED_PASS
F2_BRANCH=exec/n3w-t1-f2-fresh-readonly-preflight-20261014
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
AUTHORIZATION_CLAIM=false
F3_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false

## 1. Fresh rebind

PR #541 is merged. The F2 branch starts directly from merged main at
3e05e82a7d7e871d2966e78e8cb5caff601a0152. No F2 source is stacked on the retired umbrella branch.

The product route remains ADR-0010:

official Armbian per device
→ first boot
→ F2 read-only preflight
→ separately authorized F3 automated deployment
→ separately authorized F4 activation/acceptance

F2 does not authorize either later mutation gate.

## 2. Exact target release

The exact target release is inherited from the completed P2B target-Armbian read-only evidence:

OS_ID=ubuntu
OS_PRETTY_NAME=Armbian OS 26.05.0 resolute
OS_VERSION_ID=26.04
OS_VERSION_CODENAME=resolute
ARMBIAN_ARCH=arm64
ARMBIAN_BOARD=S912-Phicomm-T1
ARMBIAN_BOARD_NAME=Aml.S912
ARMBIAN_BRANCH=current
ARMBIAN_IMAGE_TYPE=rebuild
ARMBIAN_VERSION=26.05.0

F2 treats drift from these fields as STOP.

## 3. Reused source

F2 reuses the existing OS-identity read-only probe, minimal-baseline read-only inventory,
F1B fresh-product staging host and fresh-host baseline contract. The new package adds only
the F2 orchestration and missing checks for route/DNS/time, package availability and old
transaction/authorization/staging residue.

## 4. Docker-not-yet-installed case

F2 supports two valid fresh-host states.

If Docker is already present, Docker state must be empty/default and the exact F1B
storage/capacity probe must PASS.

If Docker is absent, no /var/lib/docker or /var/lib/containerd residue may exist and the
prebaseline root-free capacity model must PASS. If local APT indexes already exist,
docker.io and docker-compose-v2 must have visible candidates. A newly installed Armbian
host is also valid when /var/lib/apt/lists has no package-index files yet and the configured
Ubuntu ports source explicitly binds resolute plus universe; F2 must not run apt update merely
to manufacture a candidate. Candidate resolution and any APT metadata refresh then remain
inside the separately authorized F3 baseline-install step.

Package-index refresh and package installation remain F3 mutation and are not executed here.

## 5. Main post-merge CI / artifact authority

The merge-to-main push started 20 workflows. At the third and final status check in this
preparation cycle:

SUCCESS=16
IN_PROGRESS=4
FAILURE=0

The four still running were:

- N3W T1 fresh bootstrap deployable payload CI — run 38536117520
- N3W T1 fresh install exact ARM64 CI — run 38536117298
- N3W T1 production stack staging payload CI — run 38536117386
- greenhouse-manager CI — run 38536117493

No further polling is performed in this preparation cycle. The F2 executor does not
hard-code a main artifact ID. At execution time it binds the exact artifact by
run/name/id/ZIP digest and proves the payload manifest source head equals the declared
expected artifact source head.

## 6. STOP boundary

Before any T1 SSH:

1. this new F2 source PR must pass its focused source CI;
2. the merged-main deployable artifact must be complete and exactly bound;
3. the execution command must bind the exact F2 source head and artifact metadata;
4. the operator must provide the exact read-only confirmation.

F2_SOURCE_STATUS=PENDING_CI
F2_TARGET_EXECUTION=NOT_STARTED
F3_AUTHORIZATION=NOT_GRANTED
AUTO_EXECUTE_F3=false
STOP_BEFORE_T1_ACCESS_UNTIL_SOURCE_CI=true
