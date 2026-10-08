# N3-W Clean Product First-Pair — P4 Private Identity / Setup Secret Handoff Prestage — 2026-10-08

```text
STATUS=READONLY_SOURCE_REVIEW_COMPLETE_LIVE_IPC_PRESTAGE_PENDING
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_IDENTITY_AND_SETUP_SECRET_HANDOFF_PRESTAGE_20261008_01

P3_EXACT_FLASH_AND_FOUR_READBACK=CLOSED_PASS
P4_PREBOOT_T1_MANAGER_BROKER_CONTINUITY=CLOSED_PASS

P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_FIRST_NORMAL_BOOT_EXECUTED=false
P4_OPTICAL_QR_CAPTURE=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORTED=false
P4_MANAGER_COMMIT=false
P4_KF050_INTERRUPTION=false

BOARD_ACCESS=false
BOARD_WRITE=false
T1_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_CLEAR=false
MANAGER_HIGH_WATER_CLEAR=false
AUTO_P4=false
STOP=true
```

## 1. Frozen product/physical authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_REQUIRED_STATE=OPEN_DRAFT_UNMERGED
PRODUCT_SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
PRODUCT_SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
ARTIFACT_ID=11469977052
CURRENT_P3_CLOSURE=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_OFFLINE_ARTIFACT_R2_CLOSURE_20261008.md
CURRENT_P4_PREBOOT_CLOSURE=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_CLOSURE_20261008.md
CURRENT_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
CURRENT_BOARD_STATE=FOUR_REGIONS_WRITTEN_AND_EXACT_READBACK_PASS_NO_PRODUCT_BOOT
FROZEN_MANAGER_PREBOOT_IDENTITY_COUNT=5
FROZEN_MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
```

P3 remains consumed and non-replayable. The P4 preboot read-only gate has also been consumed. P4 first normal product boot is neither authorized nor executed. Real runtime product identity is not inferred from the ROM/eFuse silicon binding.

## 2. Exact source interface rebind

Read from frozen source head `629f096a...`, not an inferred product API:

| Source | Exact Git blob SHA | Contract verified |
| --- | --- | --- |
| `host/greenhouse-manager/src/greenhouse_manager/ops/n3w_pairing_cli.py` | `1dc70189873f4d33f3de1e5bb6524c434d73b5ef` | `greenhouse-manager-pairing import-payload --payload-stdin` parses the full one-line `GHN3W2` payload and calls the Manager-owned local IPC |
| `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_pairing_local_ipc.py` | `ca709cbe7d86b70055f88800de2b4d6751fd95ff` | Local Unix-domain socket is the product secret intake, not lab filesystem handoff or SQLite |
| `host/greenhouse-manager/src/greenhouse_manager/runtime/registration.py` | `230eeb45ce4aa2cf0a084d89eef901676500114d` | `registrations`, `pairing_sessions`, history, leases, retirement; default pending TTL 120 s |
| `host/greenhouse-manager/src/greenhouse_manager/runtime/credential_lifecycle.py` | `e0499805e8f2d59a41d5b017e7ed35fb849686fd` | Credential assignments are in their **own** database and preserve historical assignments, including revoked |
| `host/greenhouse-manager/src/greenhouse_manager/runtime/replay_registry.py` | `babc2ee6898572cdbc68ba2c32ee90e060548f14` | Replay registry is keyed by **node_id**, not ROM silicon hash or a raw product hardware_id |
| `host/greenhouse-manager/pyproject.toml` | source-derived | `greenhouse-manager-pairing` entry point is installed by product package |
| `infra/compose/t1/docker-compose.manager.yml` | source-derived | Product Compose uses `GH_N3W_PAIRING_SOCKET_PATH=/tmp/greenhouse-manager/pairing.sock`, with private tmpfs and Manager read-only rootfs |

### Real QR contract

The frozen CLI source requires exactly one `GHN3W2:` payload with a `ghw-c6-` hardware identity, UUID-format pairing transaction ID, and 43-character base64url-encoded 32-byte Setup Secret. The actual raw QR is **never** printed to stdout/stderr, pasted into ChatGPT, stored in public GitHub, placed in shell argv or copied into public logs. The operator must optically scan the real product LCD page 5.

Only private code derives and compares:

```text
PRODUCT_HARDWARE_ID_SHA256
PAIRING_ID_SHA256
```

The final imported payload must reach the Manager-owned `pairing.sock` using the existing product CLI and **stdin**, not custom HTTP/SQLite writes, serial dumps, test QR synthesis or lab handoff.

## 3. Pending TTL is an operational prerequisite

The source `RegistrationRegistry(..., pending_ttl_s=120)` and `Settings.pairing_pending_ttl_s` establish a **default**, not the current actual runtime value. The current Manager container must read-only prove its effective `GH_PAIRING_PENDING_TTL_S`, or the documented default when unset. The staged read-only gate rejects a configuration outside the bounded 90–600 s readiness policy.

The pending transaction may start during initial hello after normal boot. It is unsafe to spend that interval fetching code, compiling a new helper, asking for an unplanned authorization, reconfiguring a T1 service or repeating a QR capture. All postboot executable logic, evidence dirs, private optical scan method and secret-import authorization **must be ready before P4 boot**.

## 4. Strict P4-C identity oracle to implement and validate before boot

When the real QR eventually exists, a private, no-echo Mac QR intake must check exact `GHN3W2` format and decode a 32-byte secret without writing it to the terminal or disk. It must then fetch a fresh **read-only** Manager registration/credential history view (exact Manager container → configured SQLite mounts, mode=ro, `PRAGMA query_only=ON`).

The oracle must require all of:

1. The operator's original five-hardware-ID preboot hash set matches its immutable private snapshot file; all preexisting records are preserved and no unexpected new identity exists.
2. Exactly **one** newly observed Manager pending hardware identity exists relative to the frozen set, and its SHA256 matches the optically scanned product hardware identity.
3. The new identity's live `registrations.current_pairing_id` and current pending `pairing_sessions.pairing_id` agree; pairing-ID SHA256 equals the QR pairing-ID hash; pending record is still active and has sufficient expiry margin.
4. The new hardware identity has no prior assigned node ID, credential assignment (including revoked history), retirement ownership, NODE_ID lease, unexpected registration history or incompatible pairing sessions. A fresh pending hello/event by itself is not prohibited.
5. Replay is keyed to a NODE_ID: the new pending identity must not be assigned a NODE_ID, and no older NODE_ID / replay binding may be assumed absent merely by querying the hardware hash. Any uncertain cross-database linkage must STOP.
6. The current Manager/Broker instances, T1-A, TLS identity, socket owner/mode and immutable preboot snapshot still agree with the frozen authority.

If identity, uniqueness, history, time margin, or current runtime provenance is not provable, return `INVALID/STOP` *before* any secret import. The preboot silicon binding must never substitute for the product hardware ID.

## 5. P4-D exact import contract (separate physical/security authorization)

After P4-C PASS and before expiry, the pre-approved one-shot importer may supply the *complete*, valid optically captured `GHN3W2` line only over process stdin, e.g. the product entry point in its exact Manager container. The import must require the exact running Manager owner/socket, `gh.pair.setup-secret-import/1` acceptance, and return only secret-free accepted/rejected result metadata.

No pending side effects, network onboarding, Manager import, credential COMMIT, telemetry, power interruption, repair, recovery or replay clearing are part of this current source-read-only preparation.

To honor human STOP at P4-C→P4-D without exhausting TTL, obtain the independent sensitive-import consent **in advance** and require an on-the-spot explicit operator continuation after identity-binder PASS. Do not automatically cross that STOP even if consent was pre-granted.

A CLI result `accepted=true` proves Setup Secret intake only. It does not prove final approved credential COMMIT, firmware persistent receipt, a canonical telemetry count of zero, or KF-050 recovery. Those require further evidence and explicit gated actions.

## 6. Host-only private snapshot / Manager IPC readiness executor

A versioned read-only gate has been prepared from the previously accepted P4 preboot continuity executor:

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_PAIRING_IPC_AND_SNAPSHOT_READONLY_PRESTAGE_20261008_01
EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p4_private_pairing_prestage_readonly/executor.py
EXECUTOR_BLOB_SHA=95b95d1586adb856415dd23565f345ed9753acc4
EXECUTOR_STATIC_SCOPE_CHECK=PASS
EXECUTOR_MAC_PYTHON_COMPILE=REQUIRED
EXECUTOR_LIVE_HOST_RESULT=PENDING

ALLOWED=verify_private_P4_preboot_snapshot_mode_owner_exact_SHA256
ALLOWED=one_unchanged_T1_SSH_readonly_baseline
ALLOWED=docker_exec_python_stat_of_running_Manager_private_pairing_socket
ALLOWED=verify_installed_pairing_CLI_without_invocation
ALLOWED=verify_Manager_pending_TTL
ALLOWED=one_synthetic_non_pairing_UDP_47111_discovery

BOARD_ACCESS=false
BOARD_WRITE=false
MANAGER_PAIRING_CLI_INVOKED=false
P4_SECRET_CAPTURE=false
SETUP_SECRET_IMPORT=false
T1_CONFIG_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_RESTART=false
BROKER_RESTART=false
AUTO_P4=false
```

The runtime probe is only a preparedness check; it does not authorize normal boot, collect a private QR, perform full postboot identity binding, or import any Setup Secret. A `P4_PRIVATE_PRESTAGE_PASS=true` means the **host/secret intake entry point is prepared**, not that the whole P4-C/P4-D live executor is yet ready.

The future QR/unique-new-pending binder and one-shot import executor must be separately implemented and validated before first product boot. This split avoids falsely declaring that the presence of the socket alone makes the short pending-window workflow ready.

## 7. Current STOP and next engineering acceptance

```text
CURRENT_STAGE=P4_PRIVATE_PAIRING_IPC_AND_SNAPSHOT_READONLY_PRESTAGE
CURRENT_STATUS=PREPARED_AWAITING_MAC_HOST_ONLY_RESULT
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_PRIVATE_IDENTITY_BINDER_READY=false
P4_SECRET_IMPORT_EXECUTOR_READY=false
P4_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
BOARD_NORMAL_BOOT=false

NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_PAIRING_IPC_AND_SNAPSHOT_READONLY_PRESTAGE_20261008_01
STOP=true
```

Run the exact host-only readiness gate once on the Mac. After its evidence is reviewed, implement/verify the postboot private QR↔pending-ID binder and one-shot Manager-owned import in a separate design/source gate, **without booting the board**. Then seek explicitly bounded P4 first-normal-boot plus sensitive-import permissions before generating any live pending pairing record.
