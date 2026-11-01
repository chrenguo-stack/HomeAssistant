# N3-W F350 Codex Development / RCA / Test Archive — 2026-08-23 to 2026-08-24

## 1. Scope and safety boundary

This archive records the work performed after
`温室环境监测系统_F350_BSR-R2_Epoch3_Helper_RCA_Codex交接文档_V1.0_20260823.md`
through the successful F3:50 Epoch7 Final Physical Acceptance.

The work included host-only artifact RCA, temporary offline Control builds and,
only under separately granted physical authorizations, app0-only writes,
external hard resets, read-only flash/NVS forensics, exact-Manager recovery,
0600 private handoff delivery, pairing approval and final acceptance. This
archive pass itself performed no board, USB, serial, flash, NVS, Manager,
Broker or Home Assistant operation.

No Setup Secret, raw pairing ID, hardware MAC, USB serial, credential, private
key, raw NVS, raw serial capture, private handoff body, host address or private
MQTT payload is tracked by this PR.

## 2. Exact starting baseline

| Item | Bound value at handoff |
|---|---|
| Repository authority | `chrenguo-stack/HomeAssistant` |
| Authority commit | `4f39013222e53ac353846d5b2c5528c9c3be0ed3` |
| Authority tree | `3bf9e5364fe09e60a0de277bd0e160c2975b8c4b` |
| Exact Manager source revision | `1e47c58addb4a41207d1c29fa0749b3de9679e4e` |
| Helper source | `firmware/esphome_rc/board_lab/n3w_boot_session_recovery/pairing_epoch_successor_helper.yml` |
| Helper source blob | `d18c5095038a8df9fbd4b526c003503e9287aaf6` |
| Epoch3 target helper app SHA-256 | `aff3d0d281461031d0f4c956ce0e1cf8e055296c3e3ee068ff706eda322c43c4` |
| Pairing epoch on board | `2` |
| Epoch3 durable | `false` |
| BSR-R2 executed | `false` |
| Product app restored | `false` |
| Last proven physical state | `ROM_DOWNLOAD_MODE` |
| FC4 Final Physical Acceptance | `NOT_PASS_YET` |

Selected R2 helper-specific offline-bundle binding:

- `dependencies.lock` SHA-256:
  `d3edfd47d6c9992e576ddfa42fa3d3935b4fc4546d531e7865ce82b88a5fdee4`
- generated `src/idf_component.yml` SHA-256:
  `7f89ed0deb6b575bc33901bbb1ae43a8616fca1ecad63241f8e8ba5ad6423c18`
- direct dependency: `bblanchon/arduinojson@7.4.2`
- framework/target: ESP-IDF `5.5.4`, ESP32-C6

## 3. Work inventory and timeline

1. Replaced the failed macOS awk executor with a Python, scope-limited,
   unique-value extraction of `esphome.name`. The exact helper name was
   `gh-n3w-repair-epoch-successor`.
2. Read-only searched surviving same-name `.esphome/build` directories. No
   complete exact-compatible same-name successor bundle survived.
3. Generated the current helper manifest and exact-compared dependency names,
   versions, framework target, lock and managed-component tree with the
   selected helper bundle.
4. Corrected two broad failure classifications: the first real failures were
   Python dependency installation and IDF Component Manager registry
   resolution, not esptool or C++ compilation.
5. Materialized a temporary network-fail-closed offline helper Control-A.
   Generated code proved the Control build's `2 -> 3` constants and guarded
   control flow. Its whole image did not reproduce the historical target image.
6. Under separate authorizations, exact-wrote/read back the target helper in
   app0 and investigated direct-ROM, attach+run and `FLASH_END(0)` handoffs.
   Those paths did not prove application execution or durable transition.
7. An external hard reset with capture already active produced exactly one
   helper success marker. Read-only NVS semantics then proved valid, monotonic
   epoch `2 -> 3`; partition and active app0 bindings were unchanged.
8. Generated the current product manifest. The helper-only component bundle
   correctly failed compatibility because current product also required mDNS
   and multipart-parser. A complete three-component local bundle passed.
9. Completed a temporary offline product Control-A build from exact authority.
   Bound firmware, ELF, partition binary/CSV and the app0 capacity boundary.
10. Under a new authorization, restored only app0 with the exact product
    image, independently read it back, proved partition/otadata/NVS unchanged
    before application boot, then captured a clean product hard-reset boot.
11. The initial BSR-R2 preclaim correctly stopped because the current Epoch3
    Manager session had expired; no handoff, credential or key mutation
    occurred in that attempt.
12. A later pairing attempt took an avoidable detour: missing discovery was
    treated as possible Wi-Fi absence before the operator-provided network
    topology was obtained. Both T1 and F3:50 had remained associated with the
    same Wi-Fi node and visible in the router. The network hypothesis was
    superseded.
13. Epoch4 did not reach atomic delivery before its fixed pending window was
    usable. Recovery remained fail-closed and the private handoff was not
    delivered.
14. Epoch5 passed pretransfer and predelivery gates with 117/115 seconds
    remaining; the 0600 handoff was atomically delivered and consumed. Manager
    approval then hit a DynSec target-identity collision. The business
    transaction failed closed and committed no valid credential, but its DynSec
    rollback was not proven state-preserving.
15. Read-only postfailure evidence showed no accepted Epoch5 credential. The
    expired session was preserved rather than forced through.
16. Epoch6 helper execution and product restoration passed, but its pending
    TTL expired while a new explicit authorization for sensitive transfer was
    awaited. The pretransfer gate failed closed and no Epoch6 handoff was sent.
17. Before Epoch7, the exact Manager was stopped and the DynSec state was
    privately backed up. Recovery used the production provisioner's exact-target
    `deprovision` semantics to remove only the stale target client/role; no
    global DynSec clearing or unrelated identity mutation was used.
18. Epoch7 pre-armed the full chain before creating the pending identity:
    capture, exact session observation, pretransfer, SSH 0600 staging,
    predelivery and atomic inbox delivery.
19. Epoch7 passed the two delivery gates with 100/98 seconds remaining; the
    inbox consumed the handoff and ended empty. Manager registration became
    approved, credential generation 7 active, relay key epoch 7 active, and
    the inherited node lease remained active.
20. Final read-only board forensics proved valid epoch7, peer and broker
    records present, pending ACK absent and Setup Secret absent. Exact product
    app0, partition table and otadata bindings passed. A final hard reset had
    no panic or Guru Meditation marker, and the board passed 5/5 LAN probes at
    the operator-confirmed address.

## 4. Problems, RCA and regression guards

### 4.1 Portable parsing and shell execution

- **Observed:** macOS awk parsing failed after exact source binding and before
  any materialization.
- **Cause:** non-portable, multiply quoted awk state logic.
- **Resolution:** Python extraction with exact blob, YAML scope and uniqueness
  checks.
- **Guard:** KF-055. The old executor must not be replayed.

### 4.2 Offline failure-stage and bundle-scope classification

- **Observed:** early helper attempts were broadly labelled as esptool/C++
  failures; product probing also exposed dependencies absent from helper scope.
- **Cause:** classification occurred before identifying the first actual failing
  subprocess, and component compatibility was inferred from common target/IDF.
- **Resolution:** bind the generated manifest first and classify the first real
  failure. Helper and product bundles are separate authorities.
- **Guard:** KF-056.

### 4.3 Control-build provenance boundary

- **Observed:** helper Control-A SHA-256
  `2ad1038b8d921e3e480d72e302645b2603b22e946469307d1189c96fda84efcb`
  differed from the Epoch3 target.
- **Resolution:** generated Control-A source proves only Control-A parameters.
  The target helper's runtime semantics are proved separately by exact app0
  binding, active-slot evidence, the hard-reset marker and durable NVS
  transition.
- **Residual:** target binary whole-image provenance was not bit-for-bit
  reproduced.

### 4.4 ROM/stub handoff is not an application-boot oracle

- **Observed:** direct-ROM, attach+run and `FLASH_END(0)` returned without an
  acceptable application marker or durable epoch change.
- **Cause:** those paths did not establish an externally reset application boot
  plus continuous observation. Their lower-level non-equivalence remains
  unknown.
- **Resolution:** treat write/readback, reset, serial observation and NVS
  semantics as independent oracles.
- **Guard:** KF-057.

### 4.5 Network-environment assumption

- **Observed:** discovery absence led to Wi-Fi/relay hypotheses even though the
  operator's router continuously showed T1 and F3:50 on the same Wi-Fi node.
- **Cause:** local discovery evidence was allowed to stand in for absent
  operator/router topology facts.
- **Resolution:** collect the authoritative network facts first, then test STA,
  listener, unicast and broadcast layers independently.
- **Guard:** KF-058.

### 4.6 Fixed pending TTL and authorization sequencing

- **Observed:** Epoch6's private handoff was ready but its pending session
  expired while waiting for explicit sensitive-transfer authorization.
- **Cause:** a new identity was activated before every later authority and
  delivery step was pre-armed.
- **Resolution:** pre-authorize and stage the complete secret-safe executor
  before helper execution. Epoch7 proved the sequence with large TTL margin.
- **Guard:** updated KF-044.

### 4.7 DynSec asymmetric target identity recovery

- **Observed:** Epoch5 atomic delivery succeeded, but automatic approval hit a
  target identity collision. No credential was accepted, while the target
  client was present and target role absent afterward.
- **Cause boundary:** the asymmetric field state is proven; whether both target
  objects existed immediately before approval is not. Exact source review in
  section 4.8 identifies a rollback path highly consistent with the result.
- **Resolution:** private backup, stopped exact Manager, exact-target recovery
  through the production provisioner, then verify both objects and restart the
  same image.
- **Guard:** KF-059 records the completed field recovery; it is `RESOLVED`, not
  evidence that the source rollback defect is guarded.

### 4.8 DynSec provisioning rollback ownership

- **Observed source semantics:** exact Manager revision sets `role_started` and
  `client_started` before the corresponding create call succeeds. The exception
  path deletes a target whenever its attempt flag is set.
- **Risk:** a collision on a pre-existing role/client can cause rollback to
  delete an object not created by the current transaction. Thus Epoch5 was
  business-layer fail-closed but cannot be described as a state-preserving
  DynSec rollback.
- **Required source fix:** track `role_created`/`client_created` only after a
  successful create response. If the Broker result is uncertain, inventory and
  reconcile instead of unconditionally deleting the target.
- **Required regression matrix:** preserve pre-existing role+client; preserve a
  pre-existing client while deleting only a newly created role; never delete a
  pre-existing role after createRole collision; allow clean-target provision.
- **Guard:** KF-060 remains `OPEN`; this docs-only PR does not modify Manager
  source or tests.

## 5. Superseded hypotheses and paths

- No helper marker meant helper source, tuple or app image was defective.
- A successful ROM/stub return was sufficient proof of application boot.
- The helper might have been written to a non-active OTA slot.
- Early build failures occurred in esptool or the C++ compiler.
- One ESP32-C6/ESP-IDF component bundle could serve helper and product.
- The stale historical product artifact was current-authority compatible.
- Missing Manager discovery meant F3:50 was not associated with Wi-Fi.
- Relay or alternate broadcast plumbing was needed before obtaining the real
  LAN topology.
- Repeating delivery after a DynSec collision would succeed without recovering
  the exact stale target identity.
- Epoch5 DynSec rollback was state-preserving merely because the credential
  transaction failed closed.
- Starting a new pairing identity before sensitive-transfer authorization could
  still reliably fit the non-renewing pending TTL.

## 6. Repository changes

No firmware, Manager, Broker, Home Assistant or automated-test source was
changed after the handoff. Temporary Python executors, build trees, logs,
readbacks and private evidence remain outside Git and are not public artifacts.

This Draft PR changes only:

- `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
- this development/RCA/test archive

The underlying epoch-successor firmware and Manager recovery source/tests were
already present in the exact authority lineage before this work began.

## 7. Tests and gates executed

### 7.1 Host-only unit/static validation

- `tests/n3w_boot_recovery`: PASS, 10 tests.
- `test_n3w_epoch3_expired_recovery.py`: PASS, 4 tests.
- FC4 archive-manifest regression: PASS, 1 test.
- Public-repository safety scan: PASS at the prior PR head; rerun for the final
  archive head is recorded in the submission handoff.
- Initial system-Python pytest attempts without pytest installed:
  `NOT_EXECUTED_ENVIRONMENT_MISSING`; they are not test failures.

### 7.2 Offline generation/build validation

- Helper exact-source/name/manifest binding: PASS.
- Surviving same-name complete helper bundle search: PASS, zero found.
- Selected helper-bundle compatibility: PASS.
- Helper temporary offline Control-A build: PASS.
- Product/helper-bundle compatibility: expected FAIL, missing two direct
  product dependencies; stopped before full build.
- Product complete local-bundle compatibility: PASS.
- Product `--only-generate`: PASS.
- Product temporary full offline Control-A build: PASS.
- Product artifact classification: exact-source/private-evidence-bound accepted
  artifact; it is not a publicly reproducible build artifact.
- Product firmware SHA-256:
  `a7ffbe05e85e8e11bb1063ff549f034518fded8eef4165c1b5fc4751f2525a16`
- Product size: `1109232` bytes; app0 range `0x10000..0x3D0000`;
  end `0x11ECF0`; remaining `0x2B1310`; fit PASS.
- Partition binary SHA-256:
  `6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca`.

### 7.3 Previously authorized physical/runtime gates

These results are evidence records, not permission to replay them:

- Epoch3 helper app0 write/readback and hard-reset durable transition: PASS.
- Product app0-only restore/readback and static boot acceptance: PASS.
- Initial expired Epoch3 BSR preclaim: expected fail-closed; no delivery or
  credential/key mutation.
- Epoch4 delivery: FAIL/expired; no private transfer.
- Epoch5 helper/restore and atomic delivery: PASS; approval then failed at
  DynSec collision. No credential was accepted, but DynSec rollback was not
  state-preserving-proven and left an asymmetric target state.
- Epoch6 helper/restore: PASS; transfer gate expired before authorization; no
  private transfer.
- Exact-target DynSec recovery with backup: PASS.
- Epoch7 helper/restore, TTL gates, atomic delivery, pairing approval, ACK and
  final read-only acceptance: PASS.

### 7.4 Exact-head CI interpretation

- CI exact-head binding: PASS.
- GitHub correctly classified this as a docs-only change. Ten workflow `scope`
  jobs and Public repository safety's `tracked-content-safety` succeeded.
- Thirteen substantive Manager/board/DynSec/runtime jobs were skipped by scope;
  their skipped state must not be reported as a fresh full regression run.

### 7.5 Not executed during this archive pass

- Any new build or dependency installation.
- Any board, USB, serial, reset, flash or live NVS operation.
- Any Manager, Broker, Home Assistant, credential or DynSec mutation.
- Any replay of BSR-R2 or prior physical authorization.

## 8. Safe evidence bindings

Only hashes and sanitized references are public here.

| Sanitized reference | Safe binding/result |
|---|---|
| `N3W_FC4_F350_CONTROL_A_OFFLINE_SUCCESSOR_20260823_R3` | helper Control-A firmware `2ad1038b...4efcb`; generated-source semantics `2 -> 3` |
| `N3W_FC4_F350_HARD_RESET_EPOCH3_DURABLE_20260823_R1` | Epoch3 target app0 `aff3d0d2...43c4`; hard-reset capture `eb646ed2...f285`; post NVS `c732d998...9acd` |
| Product Control-A | firmware `a7ffbe05e85e8e11bb1063ff549f034518fded8eef4165c1b5fc4751f2525a16`; partition payload `6664b08a...3dca` |
| `N3W_FC4_F350_EPOCH7_FINAL_ACCEPTANCE_20260824_R1` | private `SHA256SUMS` SHA-256 `3f7a8a60fe340fd60ebf568a07d199bf5d5b75829ba88aaa31dd5061ed9dcc94`; directory `0700`, files `0600` |

Epoch7 final secret-safe bindings:

- pairing ID SHA-256:
  `1c8bdea6621696f993023a2a46ceabc800a8bf3f735dd6bff84b7594eafdca1e`
- private handoff SHA-256:
  `4d06d3311f57d91fd4c0ce2d0e047644985a08a3aa3dbca5166e23115d201408`
- helper firmware SHA-256:
  `1f4fd549b88da86a6ede7e3bf241b3fa0bb27c8465d207a6bb0e361ff5bd1dfe`
- final NVS SHA-256:
  `0616bc47e5a9215fd94be7660cba18445af65342b6688eaeb3de55d80a4a12f1`
- final partition-region SHA-256:
  `b5497613a534fc7dc709dc8c1f8e15f56ed6dd6cb34ad22909e70cd53a33bbfa`
- final otadata SHA-256:
  `8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3`
- helper hard-reset capture SHA-256:
  `43699831b4d913191a76372ac99fb663bcbc2e85fdcb00ee5acdb934801b5d1e`
- product pairing boot capture SHA-256:
  `14a3c865c54cc9b12f781747e44343f9ca69e384a4d2368f3cd2c71416d5d9ad`
- final product hard-reset capture SHA-256:
  `c3c7f94b18be8640595a948fa2839e52b184aebcde1649e8feaa1b02814630dd`
- DynSec pre-recovery backup SHA-256:
  `019b5db9ad9d0c6c298aa7a679429021cabf267c5e27a84990abcdd5b86a1842`
- final DynSec SHA-256:
  `fcedb42c9fa504347447c682abaa2f95ccfca0efb987d5f5420b6b6d8a65a0ad`
- exact Manager image:
  `sha256:da4c4a957bb1064c7fc1aa42af76f1f7ee639b60cd379a9d5ddf185e8f1f90a1`

## 9. Current frozen project state

| Item | Frozen value |
|---|---|
| `PAIRING_EPOCH_CURRENT` | `7` |
| `PAIRING_EPOCH_3_DURABLE` | `true` (historical durable transition; monotonically advanced to 7) |
| `BSR_R2_EXECUTED` | `true` |
| `PRODUCT_APP_RESTORED` | `true` |
| `F350_LAST_PROVEN_PHYSICAL_STATE` | `EXACT_PRODUCT_APP_RUNNING_AFTER_FINAL_HARD_RESET_AND_LAN_PROBE` |
| `FC4_FINAL_PHYSICAL_ACCEPTANCE` | `PASS` |

`BSR_R2_EXECUTED=true` means the BSR-R2 recovery objective reached and froze
its accepted terminal state through the successor Epoch3-to-Epoch7 recovery
chain. It does not retroactively convert the earlier Epoch3, Epoch4 or Epoch6
fail-closed attempts into PASS.

Final Manager state: Epoch7 approved; credential generation 7 active with no
pending generation; relay key epoch 7 ACTIVE and epoch 1 GRACE; retained node
lease active; target DynSec client/role present; inbox empty. Final board state:
valid epoch7, peer and broker records present, pending ACK absent, Setup Secret
absent, exact product app0 bound, partition and otadata unchanged.

## 10. Remaining risks and unknowns

1. Epoch3 target helper was not reproduced bit-for-bit by Control-A; its runtime
   semantics are proven, while its exact historical whole-image build variance
   remains unknown.
2. The lower-level reason direct-ROM, attach+run and `FLASH_END(0)` differed from
   external hard reset remains unknown. The accepted process no longer depends
   on those handoffs.
3. Temporary host executors and private evidence are not maintained public
   product tooling. Reuse requires a new exact-source and safety review.
4. Relay key epoch 1 remains in intentional GRACE state and should be reviewed
   under the normal key-lifecycle policy, not changed by this archive.
5. This docs-only PR still requires independent review of scope, evidence
   interpretation and exact-head CI before merge.

## 11. ChatGPT independent-audit focus

1. Verify the distinction between source correctness, build provenance,
   readback, reset/serial observation and durable NVS semantics.
2. Verify that Epoch4–6 failures are not presented as PASS and that their
   authorizations are not reusable.
3. Verify the DynSec exact-target recovery and rollback interpretation.
4. Verify product firmware, partition and app0 boundary bindings.
5. Verify all final acceptance claims against the secret-safe Epoch7 summary.
6. Verify this PR still changes only the two documentation files.
7. Verify KF-044/KF-055..KF-060 completeness and status choices, especially
   KF-059 `RESOLVED` versus KF-060 `OPEN`.
8. Verify public-repository safety and all checks bind the final PR head.

DO NOT MERGE BEFORE CHATGPT INDEPENDENT AUDIT.
