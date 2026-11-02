# N3-W T1_Core_Stack Clean Reference — R0H T1_B cache-only install APT sandbox path repair closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_T1B_CACHE_ONLY_INSTALL_APT_SANDBOX_PATH_REPAIR_20261101_01

PREVIOUS_INSTALL_SOURCE_AUTHORITY=c4984baf274d74d1459175153b62bed9a2b7626e
CURRENT_INSTALL_SOURCE_AUTHORITY=2b87ae05f8f0ddca0c57195495432692adcef7c1

BUNDLE_ID=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
BUNDLE_CONTENT_CHANGED=false
BUNDLE_REDOWNLOAD_REQUIRED=false

LIVE_FAILURE_ROOT_CAUSE=APT_SANDBOX_CANNOT_TRAVERSE_ROOT_CACHE_PATH
DEPENDENCY_CLOSURE_COMPLETE=true
PARTIAL_INSTALL_OCCURRED=false

SOURCE_REPAIR=PASS
SOURCE_REVIEW=PASS
SOURCE_CI=PASS
SOURCE_CLOSURE=CLOSED_PASS

T1_A_MUTATION=false
BOARD_ACCESS=false
T1_CORE_STACK_DEPLOYMENT=false
```

## 1. Live failure evidence

The first physical cache-only install attempt failed after both Mac and T1 bundle verification
had already passed.

APT returned exit code 100 with an archive-fetch failure.

Read-only forensic evidence then established:

```text
docker.io=NOT_INSTALLED
docker-compose-v2=NOT_INSTALLED
containerd=NOT_INSTALLED
runc=NOT_INSTALLED
libnftables1=NOT_INSTALLED

DOCKER_COMMAND_PRESENT=false
DOCKER_SERVICE_ACTIVE=inactive
DOCKER_SERVICE_ENABLED=not-found
```

Therefore no partial host-runtime installation occurred.

The exact cache files were mode 0644 and their cache directories were 0755, but the parent
directory was:

```text
/root mode=0700
```

All five cache files were therefore unreadable to the APT sandbox user through that path:

```text
APT_READABLE=false
```

for every bundle member.

## 2. Dependency closure was proven complete

APT simulation with the same five exact local .deb files returned:

```text
APT_SIMULATION_RC=0
```

and proposed exactly these five new packages:

```text
containerd
docker-compose-v2
docker.io
libnftables1
runc
```

No additional package download was required by the simulated dependency solution.

Therefore:

```text
DEPENDENCY_CLOSURE_COMPLETE=true
BUNDLE_CONTENT_REPAIR_REQUIRED=false
BUNDLE_REDOWNLOAD_REQUIRED=false
```

## 3. Source repair

The repaired install path preserves the original verified bundle under its existing cache
location.

Before invoking APT, the installer now:

1. creates an installation-only temporary directory below `/var/tmp`;
2. sets the staging directory mode to 0755;
3. copies the already verified .deb members into that staging directory;
4. sets each staged .deb mode to 0644;
5. rechecks staged file size and SHA-256 against the source copy;
6. invokes the unchanged cache-only APT transaction from the staging paths;
7. removes the staging directory on both success and failure.

The APT command remains:

```text
apt-get --no-download --no-remove install -y <exact staged .deb members>
```

No APT update, download fallback, fix-missing behavior, third-party package source, or product
activation authority was added.

The repair does not change `/root` permissions.

## 4. Regression coverage

Tests now require:

- install package arguments originate from the temporary staging directory;
- staging directory mode is 0755;
- staged .deb mode is 0644;
- no `apt-get update` occurs in install;
- no download-only operation occurs in install;
- temporary staging is removed after successful install;
- temporary staging is also removed when APT fails;
- cache-only and product-activation self-checks continue to pass.

## 5. CI closure

Exact source head:

```text
2b87ae05f8f0ddca0c57195495432692adcef7c1
```

Observed required CI:

```text
N3W T1 fresh install host-only CI=SUCCESS
run=41274081543

Public repository safety CI=SUCCESS
run=41274081561

greenhouse-manager CI=SUCCESS
run=41274081563

N3W T1 fresh install exact ARM64 CI=SUCCESS
run=41274081692
```

## 6. Physical retry boundary

The previously verified bundle remains authoritative:

```text
BUNDLE_ID=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
PACKAGE_COUNT=5
TOTAL_BYTES=79391752
docker.io=29.1.3-0ubuntu4.1
docker-compose-v2=2.40.3+ds1-0ubuntu1
```

The retry must replace only the repository tool with the exact repaired source, verify tool
byte identity, re-verify the existing bundle, run cache-only install, and then perform the
R0H post-install acceptance.

No bundle reacquisition is required.
