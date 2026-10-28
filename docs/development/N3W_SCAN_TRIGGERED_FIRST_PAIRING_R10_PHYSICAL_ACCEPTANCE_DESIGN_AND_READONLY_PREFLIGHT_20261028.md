# N3W Scan-Triggered First Pairing R10 — Physical Acceptance Design and Read-Only Preflight

Date: 2026-10-28

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_DESIGN_AND_READONLY_PREFLIGHT_20261028_01`

## 1. Scope and stop boundary

This gate designs the real-board/T1 acceptance procedure and rechecks all repository/artifact inputs needed to make that later physical run safe.

This gate does not:
- access T1;
- access any ESP32-C6 board;
- open a serial port;
- flash a board;
- erase or modify NVS;
- open a live pairing window;
- mutate Broker, Manager or Home Assistant;
- rebuild the R9 artifact;
- execute the flat release ZIP `flash_args`;
- merge any pull request.

The physical run remains separately authorized. Passing this document means only that the procedure and immutable inputs are ready for that later authorization.

## 2. Fresh repository rebind

Fresh GitHub inspection confirmed:
- repository main is still `2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`;
- PR #705 through #709 remain open Draft PRs and unmerged;
- R9 product/test source remains `e299c937a7b89bb8a7b9a7432186ba46a416cd44`;
- R9 build workflow head remains `d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303`;
- the R9-to-R10 docs alignment is now PR #710, still open Draft and unmerged;
- this design is therefore stacked on the PR #710 head rather than pretending the alignment already exists on main.

No source drift was found that invalidates the R9 artifact authority.

## 3. Exact R9 artifact revalidation

GitHub artifact 12783234959 is still available and not expired.

Frozen identity:
- artifact name: `n3w-scan-first-pair-r9-e299c937-exact-source`;
- GitHub artifact digest: `sha256:6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995`;
- workflow run: 40612774339;
- workflow head: `d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303`;
- inner release bundle SHA-256: `b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1`;
- manifest SHA-256: `8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05`;
- `firmware.factory.bin` SHA-256: `b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf`.

The artifact was downloaded again during this gate and independently rehashed. The outer artifact, inner deterministic ZIP, sidecar and member hashes still match the R9 closure.

The flat `flash_args` remains non-executable authority because it contains build-tree-relative names absent from the flat release bundle.

## 4. Factory-image composition review

A fresh byte-level inspection of the downloaded R9 artifact confirmed that `firmware.factory.bin` is a merged image beginning at flash offset `0x0`.

Its embedded regions exactly match the separately archived R9 members:
- bootloader at `0x000000`;
- partition table at `0x008000`;
- initial OTA data at `0x009000`;
- application image at `0x010000`.

The factory image size is 1,525,680 bytes (`0x1747b0`).

The exact partition table in the R9 artifact defines:
- OTA data: `0x009000 + 0x002000`;
- PHY init: `0x00b000 + 0x001000`;
- app0: `0x010000 + 0x3c0000`;
- app1: `0x3d0000 + 0x3c0000`;
- NVS: `0x790000 + 0x070000`.

Therefore the reviewed factory image does **not** reach the NVS partition.

This produces an important R10 rule:

> Flashing the exact factory image is not a factory reset and must never be treated as proof that a board is unregistered.

R10 must not silently erase all flash or erase NVS to manufacture a clean test state.

## 5. Product starting-state contract

The R4-R8 product contract requires the registration QR only when:
1. Wi-Fi is connected; and
2. the node is not already product-provisioned.

The node-local registration page is served on TCP/47113 and the QR is of the form:

`http://<current-node-ip>:47113/register#t=<RAM-only scan token>`

The QR does not contain the Setup Secret, hardware ID, pairing ID, Manager locator or long-lived credential.

The physical acceptance therefore requires a target board that can freshly demonstrate:
- expected ESP32-C6/8 MB hardware identity;
- usable power;
- Wi-Fi connectivity to the intended product LAN;
- unregistered product state;
- no pending final-ACK recovery that would take precedence over a fresh registration;
- registration QR visible after the R9 image boots.

If the board instead presents the network-provisioning QR or an already-provisioned state, R10 stops as a **board precondition mismatch**. It does not erase NVS inside this acceptance gate.

Any required Wi-Fi reprovisioning or pairing-state reset must be handled as a separate, explicitly bounded preparation action.

## 6. T1 live read-only preflight to run after physical authorization

The later physical gate must begin with read-only T1 verification. It must not restart, recreate, redeploy or repair any production service during preflight.

Required observations are:
1. the production Broker, Manager and Home Assistant stack is healthy and stable;
2. the running Manager is the reviewed R1-R3-capable first-registration runtime, not a predecessor image;
3. the trusted-product-LAN authority is healthy and resolves one valid product LAN;
4. the Manager local pairing control socket is healthy;
5. production pairing is disabled while idle;
6. TCP/47112 is closed while idle;
7. no current-process first-registration intent is active;
8. no predecessor first-registration transaction blocks the new target;
9. Manager/Broker/Home Assistant container identity and restart counters are captured before the test so continuity can be checked afterward;
10. no normal path uses Manager `--force-recreate` or an out-of-band Compose override.

The repository-owned read-only `inspect`/pairing-window status paths are preferred over ad-hoc log interpretation.

Absence of a log line is not a failure oracle. Current socket/runtime/database state is the authority.

## 7. KF-129 guard

KF-129 remains a mandatory R10 regression guard.

The real first-pair flow must use the Manager-owned in-process first-registration window. It must not:
- recreate the Manager container;
- start a second Manager;
- replace the production Compose lifecycle;
- stop or restart Home Assistant as part of pairing;
- manually open the old engineering pairing window as a substitute for the product 47110-triggered transaction.

The expected production behavior is:
- 47112 closed while idle;
- accepted 47110 first-registration request creates the durable attempt before 47112 becomes available;
- 47112 is bound to the accepted identity/source;
- Manager durable COMMIT happens before the close callback;
- 47112 closes again after successful commit;
- normal Manager/Broker/Home Assistant runtime remains continuous.

## 8. Board write-route design

The only accepted firmware input for the first physical run is the exact reviewed R9 `firmware.factory.bin`.

Immediately before board mutation, the operator/executor must recheck:
- artifact ID and download availability;
- outer artifact digest;
- inner bundle digest;
- factory image size and SHA-256;
- target chip is ESP32-C6;
- flash size is 8 MB;
- Secure Boot is disabled;
- Flash Encryption is disabled;
- exactly one serial target is selected.

Before the first write, private rollback evidence must be captured:
- a readback backup of exactly the flash range that the factory image will overwrite;
- a full readback backup of NVS at `0x790000 + 0x070000`;
- SHA-256 and byte count for both backups.

Raw backups are private material and must never be committed to GitHub.

The write route is one merged-image write beginning at `0x0`. It must:
- use the exact reviewed factory image;
- not run `erase-flash`;
- not run `erase-region` on NVS;
- not use the release ZIP `flash_args`;
- keep the target from booting the application until post-write readback is complete.

The exact esptool command line will be generated in the physical gate from the installed esptool v5 help and the already proven no-reset pattern; this design freezes the semantics rather than guessing a version-specific CLI spelling.

## 9. Post-write preboot proof

Before allowing the application to boot:
1. read back exactly the factory-image-covered range;
2. require its SHA-256 to equal the exact factory-image SHA-256;
3. read NVS again;
4. require the NVS SHA-256 to equal the prewrite NVS SHA-256;
5. require chip identity/security state to remain unchanged.

A factory-range hash mismatch is a hard flash failure.

An NVS hash change before application boot is also a hard failure because the reviewed factory image does not overlap NVS.

If either occurs, do not continue into pairing. Restore the overwritten range from the private prewrite backup, verify the restoration, and stop for diagnosis.

## 10. First boot baseline

Only after the post-write proof passes may the target application boot.

The first application baseline must establish:
- board boots normally;
- LCD is readable;
- Wi-Fi reconnects;
- no automatic Manager discovery/registration occurs while the QR page has not been scanned;
- the node remains unregistered;
- registration page is forced on the LCD and the registration QR is visible;
- T1 still shows no new transaction and 47112 remains closed.

If the board shows the Wi-Fi setup QR instead, stop as Wi-Fi-precondition mismatch.

If the board shows `已联网` immediately, stop as already-provisioned/precondition mismatch.

Neither condition is evidence of an R9 product defect by itself.

## 11. Real first-registration sequence

The accepted physical sequence is:

1. Scan the node LCD registration QR with the phone camera.
2. Confirm that the page is served by the node itself and can open without exposing protocol secrets.
3. Trigger the page's explicit search action.
4. Observe product-safe T1 candidate label(s).
5. Require an explicit candidate click. Candidate display alone must not start registration.
6. If one legitimate T1 is present, select it. If multiple legitimate T1s are naturally present, verify there is still no auto-selection; do not deploy a fake second T1 merely to force this branch.
7. Observe the node enter `正在搜索` / `等待确认` / `联机注册中` as appropriate.
8. Confirm on T1 that the accepted 47110 request created a durable first-registration attempt before privileged 47112 exposure.
9. Confirm 47112 becomes available only for that accepted transaction.
10. Let the real ESP32-C6 perform TLS leaf-fingerprint verification and the Setup-Secret bootstrap.
11. Let the real pairing exchange persist the broker/peer state and final delivery acknowledgement.
12. Require durable Manager COMMIT.
13. Require 47112 to close after COMMIT.
14. Require the node to reach provisioned state and show `注册成功`, then return to normal `已联网` behavior.
15. Require post-pair MQTT/Manager state to advance using the new node identity without Manager/Broker/Home Assistant restart or replacement.

No Setup Secret is manually copied to the phone or T1 during this path.

## 12. Physical evidence and privacy boundary

Public GitHub evidence may contain:
- exact public commit/artifact hashes;
- PASS/FAIL classifications;
- public-safe counts;
- hashed board identity;
- hashed pairing/session identifiers when needed;
- listener state;
- container continuity booleans;
- timing measurements that do not reveal secrets.

Do not publish:
- raw hardware ID;
- raw pairing ID;
- Setup Secret;
- scan-token URL;
- MQTT password;
- application key;
- system peer key;
- raw NVS image;
- private board backup;
- unredacted Manager/Broker logs containing credentials or locators.

Phone screenshots are evidence only if they do not expose the QR payload or sensitive URL.

## 13. One-shot and retry boundary

The future physical authorization must bind:
- one exact R9 artifact;
- one exact target board;
- one first-registration acceptance run.

The authorization is consumed when the first board write begins.

Purely observational rescanning of the same QR before a Manager transaction exists is not a second registration attempt.

Once 47110 has accepted a transaction and the Manager durable attempt exists:
- do not manufacture a second pairing ID;
- do not clear Manager state;
- do not erase NVS;
- do not reopen 47112 manually;
- do not replay the run after terminal failure.

A terminal failure is frozen and triaged before any successor attempt.

## 14. PASS criteria

R10 physical acceptance can close only if all of the following are observed in one controlled run:
- exact R9 factory image is written and exact readback matches;
- NVS is unchanged by the flash step;
- target boots and reconnects to Wi-Fi;
- target is genuinely unregistered before scan;
- idle node does not start Manager registration by itself;
- registration QR and node-local phone page work on real hardware;
- candidate selection requires explicit user action;
- real ESP32-C6 TLS/pinning/bootstrap succeeds;
- durable Manager attempt precedes 47112 exposure;
- identity/source binding rejects unintended access;
- Manager COMMIT completes;
- node durable provisioned state is reached;
- LCD shows commit-bound registration success;
- 47112 returns to closed;
- normal MQTT/Manager data path resumes/advances;
- Broker, Manager and Home Assistant remain continuous with no pairing-induced recreate/restart.

## 15. STOP classifications

Stop before board write when:
- artifact identity/availability drifts;
- T1 runtime is not the reviewed capable runtime;
- T1 health/trusted-LAN/pairing-idle baseline is not clean;
- an unresolved predecessor transaction exists;
- target chip, flash size or security state is unexpected.

Stop after write but before pairing when:
- readback differs from the reviewed factory bytes;
- NVS changed during the write phase;
- board cannot boot normally;
- Wi-Fi is not already provisioned;
- board is already product-provisioned;
- registration QR is not available in the required starting state.

Stop during/after pairing when:
- 47112 opens before a durable attempt;
- user selection is bypassed;
- TLS pinning/bootstrap fails;
- wrong identity/source reaches durable mutation;
- Manager COMMIT is not proven;
- LCD reports success before provisioned state;
- 47112 remains open after terminal success;
- Manager/Broker/Home Assistant continuity is broken.

No STOP condition authorizes automatic repair, NVS erase, T1 redeploy or a second physical attempt.

## 16. Rollback authority

Rollback is deliberately narrow.

If the flash operation or immediate preboot readback fails:
- restore only the exact range overwritten by the factory image from the private prewrite backup;
- verify the restored bytes;
- leave NVS untouched;
- stop.

If the R9 image boots successfully but first-registration acceptance later fails, do not automatically roll back firmware or clear pairing state. Preserve the failure state and evidence for root-cause review.

## 17. Result of this design/preflight gate

Repository, source and artifact rebind: PASS.

Independent local rehash of the exact R9 artifact: PASS.

Factory-image composition and NVS non-overlap review: PASS.

R10 write route, T1 read-only preflight, physical sequence, PASS/STOP rules, privacy boundary and rollback contract: frozen.

No new source blocker was found.

No T1 or board was accessed, and no live/flash/NVS mutation occurred.

The next physical gate is ready to be requested, but is **not authorized by this document**.

Recommended next gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_EXECUTION_20261028_01`

That gate must begin with the read-only T1/board prechecks above and may cross into flashing only after all prechecks pass under a new explicit user authorization.
