# N3W Scan-Triggered First Pairing R6 -> Physical Validation Preflight

Date: 2026-10-27

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_PHYSICAL_VALIDATION_PREFLIGHT_20261027_01`

## 1. Scope

This gate is read-only prephysical planning.

Allowed:
- fresh repository / PR rebind;
- source and design review;
- prerequisite classification;
- physical acceptance plan freezing;
- GitHub documentation.

Not allowed:
- T1 access or mutation;
- board access or flashing;
- NVS / otadata / firmware mutation;
- production service start/restart;
- sensitive Setup Secret transport;
- merge;
- physical authorization claim.

## 2. Fresh authority rebind

Repository: `chrenguo-stack/HomeAssistant`

Current repository main remains exactly:

`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`

Fresh compare against main:
- status: identical
- ahead: 0
- behind: 0

R6 source implementation PR #698:
- state: open
- draft: true
- merged: false
- base: `docs/n3w-r6-tls-bootstrap-design-preflight-20261027`
- exact source head: `6283cff57bcd0576968df9fd2440f3aae27331a5`

R6 source closure PR #699:
- state: open
- draft: true
- merged: false
- base: `feat/n3w-r6-tls-bootstrap-source-implementation-20261027`
- docs-only head: `f6bfbb31916ea0a1bdcebe439a22ec349642f1aa`

The physical-product source authority remains the R6 exact source head `6283cff...`; later documentation commits do not redefine product source authority.

## 3. R6 source status

R6 source closure is valid:

- exact-head CI: 18 SUCCESS / 0 FAILURE / 1 conditional SKIPPED;
- no unresolved PR review thread;
- no new source false-PASS blocker found;
- selected-candidate TLS pinning, 47110 confirm/status, 47112 handoff, final-ACK proof, durable ACK recovery, relocation binding and crash-safe terminal cleanup passed source review.

This gate does not reopen R6 source implementation merely because physical work is not yet eligible.

## 4. Frozen implementation order controls physical eligibility

The frozen source design explicitly defines:

```text
R1  trusted-product-LAN authority + passive discovery/bootstrap skeleton
R2  durable first-registration journal + cross-store restart/deadline reconciliation + peer-trust baseline
R3  identity-bound 47112 window + unified 1800 s deadline
R4  node local registration portal + QR
R5  scan-triggered discovery + multi-T1 selection
R6  node->T1 TLS bootstrap + terminal-bootstrap renewal + SimplePairingClient refactor
R7  LCD state/error integration
R8  full simulated end-to-end + regression / safety
R9  exact artifact build and independent source review
R10 separately authorized physical acceptance
```

The same design states that physical mutation must not be combined with R1-R8.

Therefore R6 source closure alone is not sufficient authority to flash a board or run live T1 acceptance.

## 5. R7 prerequisite classification

`R7_LCD_STATE_ERROR_INTEGRATION=NOT_DONE`

This is proven from the exact R6 source, not inferred from missing logs.

ADR-0011 freezes the fifth LCD page state model:

```text
IDLE_UNREGISTERED
DISCOVERING
WAIT_CONFIRM
REGISTERING
SUCCESS
ERROR
```

Initial user error classes:

```text
E01 = 未找到主机
E02 = 主机不可用
E03 = 主机忙
E04 = 网络中断
E05 = 注册超时
E06 = 注册失败
E07 = 二维码失效
```

Additional frozen UI semantics:
- product-facing term is “联机注册”;
- idle unregistered node shows the registration QR and does not discover T1;
- multiple candidates show a short “请在手机选择” state, not an error;
- success may show “注册成功” only after Manager COMMIT;
- the old idle “正在查找主机” behavior is explicitly superseded.

Exact R6 source still has only coarse display booleans:
- `n3w_product_provisioned`;
- `n3w_pairing_display_ready`;
- registration QR payload ready/not-ready.

Exact R6 `display.yml` still renders:
- registration QR + “扫码添加节点 / 等待添加” when QR is ready;
- “正在查找主机” when QR display is not ready.

It does not expose the frozen six-state model or E01-E07 mapping.

Therefore physical acceptance must not proceed before R7 source implementation and tests close.

## 6. R8 prerequisite classification

`R8_SIMULATED_E2E_AND_SAFETY=NOT_DONE`

The frozen design requires a phone-like end-to-end simulated browser proof:

1. open node page;
2. start scan session;
3. receive one or multiple T1 candidates;
4. explicitly confirm;
5. prove 47112 closed -> open -> closed;
6. prove Manager COMMIT;
7. prove the browser never handles Setup Secret.

The exact R6 CI workflow currently contains focused R4, R5 and R6 source-contract tests, but no full simulated product browser transaction covering the complete node -> discovery -> browser -> 47110 -> 47112 -> Manager COMMIT sequence.

Therefore successful R6 unit/source contracts are not a substitute for R8.

R8 must also exercise key negative/safety cases at simulation level before physical work, including at minimum:
- idle node performs no active T1 discovery;
- zero-candidate return to same registration identity/QR;
- multi-candidate explicit choice with no automatic selection;
- TLS pin mismatch sends zero Setup Secret bytes;
- busy/unavailable bootstrap;
- malformed/oversized/redirect 47110 response;
- ambiguous confirm response loss preserving the same transaction identity;
- final ACK 200 with invalid schema/session/state/node binding remains pending;
- 47110 status WAIT/UNKNOWN never marks provisioned;
- terminal status enters durable cleanup and renewal;
- reboot during ACK_PENDING and TERMINAL_CLEANUP;
- T1 relocation accepted only with exact manager/system/original TLS fingerprint;
- browser/public test output contains no Setup Secret or private credential material.

## 7. R9 prerequisite classification

`R9_EXACT_ARTIFACT_AND_INDEPENDENT_REVIEW=NOT_DONE`

R6 compile CI proves the source can build in CI. It does not establish a physical candidate artifact.

Before any board flash, R9 must freeze:
- product source SHA;
- source tree / relevant manifest authority;
- exact toolchain/provenance;
- exact application image;
- bootloader / partition / otadata artifacts when used;
- artifact archive identity;
- sizes;
- SHA-256 hashes;
- workflow/run provenance;
- independent source-to-artifact binding review.

The known regression guard requires:
- historical physical artifacts and source rebuilds remain separate authorities;
- “same source” does not mean byte-identical;
- when a reproducible artifact is required, freeze toolchain/provenance;
- perform at least two clean builds and compare bytes;
- if the two clean builds differ, remain OPEN/TBD and do not nominate either rebuild as the R10 physical candidate.

No R9 artifact set meeting those conditions is currently bound to `6283cff...`.

## 8. R10 physical acceptance entry conditions

R10 may start only after all of the following are true:

```text
R7_LCD_STATE_ERROR_INTEGRATION=PASS
R8_SIMULATED_E2E_AND_SAFETY=PASS
R9_EXACT_ARTIFACT_BUILD=PASS
R9_INDEPENDENT_SOURCE_ARTIFACT_REVIEW=PASS
EXACT_PHYSICAL_CANDIDATE_BOUND=true
```

Then a separately authorized physical gate must still stop before board mutation at:

`STOP_PENDING_OPERATOR`

The operator must explicitly confirm the intended physical board/connection.

After that confirmation and before any write:
- read fresh ROM/silicon identity;
- prove the identity matches the intended target;
- treat USB device path only as a locator, never as identity authority;
- fresh-bind exact HEAD/tree/artifact hash;
- record repository main and frozen product-source authority separately.

## 9. Physical harness / executor prerequisites

Known project guards remain mandatory.

Before claiming a physical authorization:
- formal executor path must prove snapshot transport;
- bounded observation;
- exact serial capture/import path;
- product restore/write/readback fallback;
- required ownership/permission contract;
- host-only failures must stop before claim/mutation.

For a physical gate that can create a new pairing identity, pending-window readiness must be established before the gate starts:
- sensitive transport authorization ready;
- TTL dual gate ready;
- remote staging mode 0600;
- atomic consume executor prepared.

No Setup Secret, raw pairing payload, MQTT password or equivalent private credential may enter chat, GitHub comments, normal terminal transcript or public evidence.

## 10. ESP32-C6 boot evidence contract

A successful flash command alone is not boot proof.

Physical boot acceptance must keep these oracles separate:
- flash readback;
- ROM/stub handoff;
- serial application marker;
- durable NVS semantic evidence.

Application boot is proven only by a defined boot action, bounded observation window and subsequent read-only semantic evidence.

Readback length must bind the exact application image size; erased tail padding is only a separate oracle.

## 11. T1 prephysical baseline required at R10

Before the user performs phone scan/confirm, read-only live evidence must establish:
- exact running Manager authority;
- exact Broker authority;
- Home Assistant continuity baseline if included in the acceptance claim;
- trusted product LAN authority is current NetworkManager `eth0` unique IPv4 subnet;
- 47110/tcp low-privilege bootstrap is available on the product LAN;
- 47111/udp discovery is available on the product LAN;
- 47112/tcp is closed while idle;
- no predecessor active first-registration transaction is allowed to contaminate the test;
- Manager/Broker registration databases are interpreted through their correct lifecycle owner;
- absence of a log line is never treated as proof of absence.

Live evidence must not expose private identity or credential material when a public-safe hash/state oracle is sufficient.

## 12. Mandatory R10 normal-product flow

The final normal UX acceptance is:

```text
node boots clean/unregistered
-> Wi-Fi connected
-> LCD shows 联机注册 QR
-> bounded idle interval proves no automatic T1 discovery / no 47112 pairing window
-> phone system camera scans QR
-> node-local browser opens
-> scan session triggers T1 discovery
-> one/multiple candidate behavior is correct
-> user explicitly selects/accepts T1
-> user presses 确认联机注册
-> node pins exact selected T1 TLS identity
-> node performs 47110 confirm
-> T1 opens exact identity/source-bound 47112 transaction
-> existing HMAC/HKDF/encrypted credential flow completes
-> Manager durable COMMIT is proven
-> 47112 closes
-> LCD briefly shows 注册成功
-> node enters provisioned runtime
-> MQTT/Manager/HA runtime evidence advances as required by the acceptance scope
```

No terminal secret paste is permitted.

The engineering onboarding flow:

```text
scan raw GHN3W2
-> copy
-> paste into Terminal
```

is explicitly not valid final-product acceptance evidence.

## 13. R10 negative / recovery evidence set

R10 planning should reserve separate bounded cases rather than overloading the normal-flow run.

Priority physical cases after normal flow:
1. no T1 available -> LCD E01 -> same registration identity/QR;
2. multiple T1 -> explicit phone selection, no auto-selection;
3. Manager busy -> E03 without consuming pairing identity;
4. network interruption -> E04 and fail-closed recovery;
5. canonical transaction timeout -> E05 + terminal old-ID behavior + fresh durable pairing ID before later transaction;
6. stale/invalid browser QR/session -> E07 without creating a transaction;
7. confirm-response loss/ambiguity -> same pairing ID, no fresh 1800-second window;
8. final-ACK response loss -> durable 47110 status recovery to committed;
9. reboot during ACK_PENDING -> recovery precedes ordinary registration;
10. reboot during TERMINAL_CLEANUP -> cleanup resumes idempotently;
11. T1 address change during pending recovery -> relocation only with exact original TLS identity;
12. TLS fingerprint mismatch fault injection -> zero Setup Secret bytes transmitted on the mismatched connection.

Fault injection that would require unsafe or unjustified production mutation must remain simulation-only unless an explicit safe harness is frozen first.

## 14. Preflight result

```text
GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_PHYSICAL_VALIDATION_PREFLIGHT_20261027_01

R6_SOURCE_IMPLEMENTATION=PASS
R6_EXACT_HEAD=6283cff57bcd0576968df9fd2440f3aae27331a5

R7_LCD_STATE_ERROR_INTEGRATION=NOT_DONE
R8_SIMULATED_E2E_AND_SAFETY=NOT_DONE
R9_EXACT_ARTIFACT_AND_REVIEW=NOT_DONE

PHYSICAL_VALIDATION_ELIGIBLE=false
BOARD_ACCESS=false
T1_ACCESS=false
LIVE_MUTATION=false
AUTHORIZATION_CLAIMED=false
MERGE=false

PREFLIGHT_RESULT=PREPHYSICAL_NOT_ELIGIBLE_ORDERED_PREREQUISITES_REQUIRED
```

This is a sequencing result, not a product failure.

## 15. Next executable gate

The next executable source gate is:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R7_LCD_STATE_ERROR_INTEGRATION_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01`

Its immediate responsibilities are:
- define one explicit product registration display state exported by the C++ component;
- map R4/R5/R6 events to ADR-0011 LCD states and E01-E07 without inventing backend dependencies;
- remove the superseded idle “正在查找主机” semantic;
- ensure SUCCESS is emitted only after Manager COMMIT/final recovery success;
- preserve low-battery and Wi-Fi provisioning display priorities;
- add source/golden tests including font glyph coverage;
- compile the production ESP32-C6 target;
- remain source-only: no T1/board mutation.

After R7 PASS, proceed to R8 simulated E2E/safety, then R9 exact artifact, then separately authorize R10 physical acceptance.
