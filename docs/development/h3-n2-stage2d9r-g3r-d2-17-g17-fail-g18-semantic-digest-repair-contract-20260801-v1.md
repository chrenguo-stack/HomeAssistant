# H3/N2 Stage2D-9R G3R D2-17 G17 failure and G18 semantic digest repair contract

## Frozen G17 disposition

G17 returned a complete self-bound terminal with `FAIL / D2_17_TARGET_MAC_HOST_ONLY_CLOSURE_BLOCKED` and `failure_code=G16_TERMINAL_FILE_DIGEST_DRIFT`. No G17 authorization was created, claimed, or consumed. G16 was not semantically loaded, G16 was not mutated, G14/G15 runtime was not accessed, and all physical-operation flags remained false. G17 is permanently retired and cannot be replayed.

The G17 terminal record SHA-256 is:

`8825449a87b36a606be635fff12518f47744324c6dcb36ae28f939128e7baa42`

The safe failure-acceptance subset binding is:

`ba8815349a7c7f76398618f59dd6f68ff4439607f1ac2da43a58e5cbe5cc858d`

## Deterministic root cause

The private G17 driver computed SHA-256 over the raw bytes of `G16_FORENSIC_TERMINAL.json` and required that value to equal the frozen `terminal_record_sha256`.

Those values bind different domains:

- raw file digest: exact bytes on disk, including whitespace and trailing newline;
- semantic record digest: canonical compact sorted JSON after removing the `terminal_record_sha256` self-binding field.

A valid terminal file is not required to have identical raw and semantic digests. The public G17 reconstruction tool already verified the semantic self-binding correctly; the mismatch was introduced only by the private launcher preauthorization check.

## G18 repair

G18 must use this order:

1. locate exactly one retired G16 runtime and require a regular non-symlink `0600` terminal file;
2. capture raw SHA-256, size, mode, and modification time for later immutability verification;
3. load the JSON object;
4. require its `terminal_record_sha256` field to equal the frozen G16 semantic digest;
5. remove that field, canonicalize with sorted keys and compact separators, and verify the semantic digest;
6. only after semantic verification succeeds, create and claim a fresh one-shot G18 host-only authorization;
7. reconstruct the authenticated physical result from the existing G16 evidence;
8. verify that the raw file digest and metadata are unchanged before consuming the authorization.

The raw digest is never compared to the semantic record digest. It is used only for pre/post immutability and concurrent-drift detection.

## Safety boundary

G18 is host-only. It may read only `G16_FORENSIC_TERMINAL.json` from the unique retired G16 runtime. It may not modify G16 or access G14/G15 runtime. It may not enumerate USB or serial devices, invoke esptool, perform Flash/NVS, access the network, start a Broker, execute PREPARE or VERIFY, perform recovery, ACTIVATE or CLEANUP, or perform Ready, merge, release, tag, or deployment operations.

No physical replay is required or authorized. G17 remains retired regardless of G18 outcome. G18 is also one-shot: any output, PASS, FAIL, nonzero exit, or interruption retires the G18 package.

## Public/private separation

The public source is inert and secret-free. It contains semantic verification, reconstruction, bindings, tests, and safety declarations only. The separately authorized private package binds the exact Draft PR HEAD, load-bearing review Artifact, Target Mac Python executable, package manifest, and one-shot host-only authorization lifecycle.

Approved package-creation decision:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G18-G17-RAW-FILE-VS-SEMANTIC-DIGEST-TYPE-MISMATCH-REPAIR-AND-TARGET-MAC-HOST-ONLY-SUCCESSOR-PACKAGE-CREATION-20260801-01`

This decision authorizes public repair development, Draft PR creation, CI, review Artifact generation, and creation/delivery of the private G18 package. It does not authorize executing G18.
