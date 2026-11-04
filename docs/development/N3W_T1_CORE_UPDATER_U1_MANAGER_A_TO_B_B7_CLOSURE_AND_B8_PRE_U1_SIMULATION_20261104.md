# N3-W T1 Core Updater U1 — B7 closure and B8 Pre-U1 simulation

Date: 2026-11-04

## B7 closure

```text
B7_RUN_ID=41829022162
B7_RUN_NUMBER=169
B7_RESULT=SUCCESS
SOURCE_JOB=SUCCESS
SOURCE_SIMULATION=128_PASSED
EXACT_MANAGER_SLICE=SUCCESS

MANAGER_PACKAGE_ARTIFACT_ID=13322275752
MANAGER_PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-5b32e1ae8210
MANAGER_PACKAGE_ARTIFACT_DIGEST_SHA256=720611993fa80c1f29a39399183a2adee790a497292ca07c99bc270524d30366
UPDATER_PYZ_SHA256=0287d7e7d9c27cf50b842d2c39511cae773ed90526527c4c46a4bff6c368c2b
MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
MANAGER_IMAGE_ID=sha256:80d34358094638ce9c8ce5fb2635fe0a5c75ee7cc5e8c628b38ab223134e585f

UPSTREAM_GITHUB_ARTIFACT_IDENTITY=PASS
T1_CORE_UPDATER_MANAGER_PACKAGE_BINDING=PASS
T1_CORE_UPDATER_PYZ_EXECUTION=PASS
MANAGER_REBUILT=false
T1_MUTATION=false
B7=CLOSED_PASS
```

## B8 purpose

B8 binds the exact B7 package to the frozen real Pre-U1 business reference rather than relying only
on generic updater unit tests.

Inputs:

- `infra/n3w-t1/clean-reference/pre-u1-business-runtime-reference-20261104.json`;
- `infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json`;
- `infra/n3w-t1/production/t1-core-stack-current.json`;
- `infra/n3w-t1/upgrades/manager-5b32e1ae8210.json`;
- exact Manager-only package artifact `13322275752`.

The dedicated simulation executes the real `CoreUpdater.inspect()`, `CoreUpdater.plan()`,
`CoreUpdater.apply()` and `CoreUpdater.rollback()` against an in-memory host initialized from the
frozen Pre-U1/current-stack authority. The Manager tar is the exact tar from the B7 package.

The simulated apply/rollback mutates only the in-memory host and pytest temporary state.

```text
REAL_T1_ACCESS=false
REAL_T1_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
LIVE_AUTHORIZATION_CONSUMED=false
B8_STATUS=IMPLEMENTED_PENDING_CI
B9_NOT_ENTERED=true
```

PASS requires the frozen Pre-U1 reference to remain CLOSED_PASS, the fresh baseline to remain equal
to U0, target predecessor to equal the real Manager A image, exact tar verification to pass, plan to
remain mutation=false, the simulated apply to commit B only, and explicit simulated rollback to
restore A while preserving Home Assistant and Broker identity.
