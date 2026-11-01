# N3-W Board B Real-World Failover — KF-087 / KF-088 / KF-089 Disposition

Date: 2026-09-04  
Repository base: `b683fc62a4126b6f6a0e945db8db68c2584e0e2d`  
Related diagnostic PR: #361 (`a4a8a8784de5f4b99ffd61a2cdf2f40e01ee0a41`, draft/unmerged)

This document reserves and defines the three regression-index entries discovered during the Board B real-world failover diagnostic session. It is intentionally public-safe and contains no raw board identity, credential, Setup Secret, peer key or private T1 material.

The detailed evidence timeline is archived in:

`docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_DEBUG_ARCHIVE_20260904.md`

## KF-087 — physical firmware source→artifact→board binding

```text
ID=KF-087
DOMAIN=INFRASTRUCTURE
STATUS=RESOLVED
```

### Phenomenon

A Board B `esphome upload` completed successfully, but the running diagnostic firmware still emitted the predecessor `N3W_DIAG_STATE` format and lacked the exact fields already present in the bound source HEAD.

### Root cause classification

The physical upload path did not establish an exact source→fresh-build-artifact→flashed-board binding. The observed behavior was consistent with upload from a stale worktree build artifact. The session did not require proving which historical build originally created that stale artifact because a fresh disposable build established the missing authority directly.

### Resolution / guard

Physical firmware gates must not treat `upload PASS` as source-to-device proof.

Required authority chain:

```text
exact SOURCE_SHA
-> fresh disposable build worktree
-> required binary semantic markers
-> firmware ELF/BIN SHA256
-> upload from the same build worktree/artifact
-> post-flash runtime marker
```

The successful recovery build was bound by:

```text
SOURCE_SHA=a4a8a8784de5f4b99ffd61a2cdf2f40e01ee0a41
FIRMWARE_BIN_SHA256=f747dcf1010ac43c3d6ff10e28d9c773881dd3116cf73bab79f08f49e4072b22
FIRMWARE_ELF_SHA256=ac61df4455cd08977039023533dd3ea8155bb4a44e3001ff81d10fc32706b1e8
RUNTIME_NEW_FORMAT_PROVEN=true
```

Authoritative source and disposable build worktrees must remain separate. Scope or dirty-worktree checks must include unstaged, staged and untracked paths; generated build side effects must be provenance-classified rather than silently ignored.

## KF-088 — controlled RESET enters ESP32-C6 ROM Download Mode

```text
ID=KF-088
DOMAIN=PHYSICAL_HARNESS
STATUS=OPEN
```

### Phenomenon

After a diagnostic firmware successfully restored Direct runtime, one controlled RESET/EN action was followed by:

- USB re-enumeration;
- no application telemetry to T1;
- no normal post-reset application log stream;
- successful no-reset/no-stub ESP32-C6 ROM communication.

Read-only strap evidence showed:

```text
GPIO8_STRAP=HIGH
GPIO9_STRAP=LOW
CURRENT_GPIO8_LEVEL=HIGH
CURRENT_GPIO9_LEVEL=HIGH
```

Therefore GPIO9 was sampled low during the reset strap window and was released/high later.

### Root cause

```text
ROOT_CAUSE=TBD
ROOT_CAUSE_CLASS=TRANSIENT_GPIO9_LOW_DURING_RESET
```

The evidence does **not** uniquely attribute the transient to a button, USB host behavior, auto-download circuitry, external GPIO loading, pull-up weakness or firmware.

### Recovery / guard

A normal full power-cycle restored Board B application, Direct telemetry and all frozen identity/lifecycle continuity without reflash or erase.

Until the exact transient source is proven:

- do not use the affected controlled-reset procedure as a generic product reboot oracle;
- distinguish ROM Download Mode from application crash, Wi-Fi failure and MQTT failure;
- no-reset/no-stub ROM read is the preferred discriminator when the state must be preserved;
- GPIO strap latch and current GPIO input are separate oracles;
- a full normal power-cycle is an accepted recovery action for this diagnostic condition when explicitly authorized;
- this harness issue does not, by itself, constitute an N3-W product runtime failure.

## KF-089 — provisioned cold boot cannot acquire Relay while Wi-Fi is unavailable

```text
ID=KF-089
DOMAIN=PRODUCT
STATUS=OPEN
```

### Phenomenon

Board B cold-boots normally and produces Direct telemetry at locations with usable Wi-Fi. At farther real-world positions, after a new cold boot, T1 observes neither new Direct nor Relay telemetry. Continued spatial bracketing did not establish a valid Relay result.

### Proven source root cause

The current product startup path requires Wi-Fi association before N3-W runtime initialization:

```cpp
if (!runtime_state_loaded_ || !mqtt_configured_ || !wifi_connected()) {
  return false;
}
```

ESP-NOW radio initialization, broadcast-peer setup and `runtime_.start(...)` are all downstream of that guard.

Therefore a provisioned node that cold-boots with Direct Wi-Fi unavailable cannot initialize the Relay-capable N3-W runtime. This defect exists independent of the exact RF reachability of the final physical candidate position.

Frozen classification:

```text
COLD_BOOT_RELAY_ACQUISITION_SOURCE_DEFECT=PROVEN
ROOT_CAUSE=PRODUCT_RUNTIME_STARTUP_REQUIRES_WIFI_CONNECTED
FAILURE_CLASS=RUNTIME_BOOTSTRAP_ARCHITECTURE
```

### Repair requirement

The successor product repair must preserve these constraints:

1. provisioned cold boot must not require successful Direct Wi-Fi before the Relay-capable runtime can become usable;
2. Wi-Fi available remains Direct-preferred;
3. Wi-Fi scanning/connecting retains radio ownership and N3-W must not illegally change channel during that state;
4. an explicit ownership handoff must precede ESP-NOW discovery channel control;
5. persisted node identity, MQTT credential generation, application-key epoch and system peer-trust generation remain unchanged by ordinary path recovery;
6. no factory-known peer MAC or pre-bound neighbor identity is introduced;
7. Relay acquisition and later Direct recovery must receive focused source/runtime regression coverage.

### Proof boundary

KF-089 does **not** prove that an already-running Direct node cannot perform live Direct→Relay failover after Wi-Fi loss.

```text
COLD_BOOT_RELAY_ACQUISITION=FAILED_SOURCE_DEFECT
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
```

The live-transition path remains a separate validation target.

## Central index integration

These IDs are reserved by this disposition document and must be folded into `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` before or with the successor product-repair merge. Until that fold-in is merged, this document is the exact public authority for KF-087/KF-088/KF-089 numbering and semantics.
