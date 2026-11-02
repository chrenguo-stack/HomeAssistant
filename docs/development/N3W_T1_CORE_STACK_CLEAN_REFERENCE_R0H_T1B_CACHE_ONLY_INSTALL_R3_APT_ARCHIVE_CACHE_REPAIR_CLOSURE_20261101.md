# N3-W T1_Core_Stack Clean Reference — R0H T1_B cache-only install R3 APT archive-cache repair closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_T1B_CACHE_ONLY_INSTALL_R3_APT_ARCHIVE_CACHE_REPAIR_20261101_01

PREVIOUS_INSTALL_SOURCE_AUTHORITY=2b87ae05f8f0ddca0c57195495432692adcef7c1
CURRENT_INSTALL_SOURCE_AUTHORITY=24382caae4a1f5d459297f86e8d18f10a848ca64

BUNDLE_ID=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
BUNDLE_CONTENT_CHANGED=false
BUNDLE_REDOWNLOAD_REQUIRED=false

SECOND_LIVE_RETRY_RESULT=STOP
SECOND_LIVE_RETRY_REASON=APT_NO_DOWNLOAD_LOCAL_PATH_SEMANTICS

SOURCE_REPAIR=PASS
SOURCE_REVIEW=PASS
SOURCE_CI=PASS
SOURCE_CLOSURE=CLOSED_PASS

T1_A_MUTATION=false
BOARD_ACCESS=false
T1_CORE_STACK_DEPLOYMENT=false
```

## 1. Why the R2 repair was insufficient

The R2 repair moved verified .deb files out of /root into an APT-readable temporary directory,
but still passed those ordinary local .deb paths directly to `apt-get --no-download`.

The second physical retry passed all pre-install bundle and source checks but again stopped at
APT with exit code 100 and:

```text
Unable to fetch some archives
```

This showed that ordinary filesystem readability alone was not sufficient for the
`--no-download` transaction.

## 2. Corrected install model

R3 uses APT archive-cache semantics directly.

The installer now:

1. verifies the original bundle exactly as before;
2. copies the exact verified .deb members into a temporary archive directory under
   `/var/tmp`;
3. creates the archive `partial` directory;
4. uses `Dir::Cache::archives=<temporary archive>`;
5. requests every manifest member as `package=exact_version`;
6. keeps `apt-get --no-download --no-remove`;
7. removes the temporary archive on success or failure.

The exact bundle remains unchanged.

## 3. Network and product boundaries

The R3 install path does not add:

- `apt-get update`;
- download-only acquisition;
- `--fix-missing`;
- online dependency repair;
- third-party package sources;
- Docker image pull/load;
- T1_Core_Stack deployment;
- product service activation.

The bundle therefore remains the only package payload authority for this installation gate.

## 4. Exact source and CI

```text
CURRENT_INSTALL_SOURCE_AUTHORITY=24382caae4a1f5d459297f86e8d18f10a848ca64

N3W_T1_FRESH_INSTALL_HOST_ONLY_CI=SUCCESS
run=41275979166

PUBLIC_REPOSITORY_SAFETY_CI=SUCCESS
run=41275979204

GREENHOUSE_MANAGER_CI=SUCCESS
run=41275979255

N3W_T1_FRESH_INSTALL_EXACT_ARM64_CI=SUCCESS
run=41275979177
```

## 5. Physical retry boundary

The physical retry must:

- retain the existing exact bundle;
- transfer only the exact R3 install tool source;
- verify source SHA-256 after transfer;
- verify the Mac archive;
- verify T1 bundle identity and T1-side bundle integrity;
- prove no partial package installation before retry;
- run the R3 cache-only install;
- stop after R0H post-install acceptance.

No bundle reacquisition is authorized or required.
