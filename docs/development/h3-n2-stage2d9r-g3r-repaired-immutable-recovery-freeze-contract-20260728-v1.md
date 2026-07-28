# H3/N2 Stage 2D-9R G3R repaired immutable / recovery freeze contract V1

## 1. Frozen base

This layer continues the accepted repaired-successor chain without modifying any
upstream Draft PR.

- base PR: `#187`;
- exact base HEAD: `922374a46b5ad6198623ab177efc5c313d4edff4`;
- material source: `2ed70e3292e5b6522ac3a5bc279c94535cd7b784`;
- current main: `c16da1a2d4d8300198b0603359eea349a034e2ea`;
- run suffix: `tlsvalid03`;
- repair source binding: `0a2c96b7615d9f222cf72fcf899b6caf3a7c875f`.

PR `#176` mergeability remains a dynamic, non-executional field. Its immutable
boundary remains HEAD `cf841f3e5a8cf04c5df9875c499b91ad4e4289cb`,
open, Draft, unmerged and unmodified.

## 2. Accepted U1 public input

The private-material U1 is permanently consumed and non-replayable. Only the
following redacted public evidence is admitted:

- public acceptance TAR SHA-256:
  `fe08ecca58f3742e3a126af9e62897d2d8cdff1e1e7187290e5c89ca1815cc59`;
- U1 public acceptance SHA-256:
  `c335c96c2546bececb2f362f6e03d116f52102fbc29095219d00fe5e2a824b4a`;
- public descriptor SHA-256:
  `4c72e3cd57cd16f0ed48793f7f1e106c6d56a6795324abaa09b9451eb843413e`;
- U1 result SHA-256:
  `d1541e391f1d583ca36dbbafce96a4af328f46196f455d2bad01399b36adde12`;
- private package public digest:
  `d2749c4a173876282275e476a577a7e4a27440429b31592c379bdedd1d3bfa0f`;
- candidate digest:
  `73b58ea30e4355d90afa4a9bc9331968537d6318db046f562212c5b836670b15`.

No authorization record, consumed-marker content, private descriptor, private
key, password preimage, persistence key, unlock token or private command is
included.

## 3. Immutable firmware input

The public immutable build binding is:

- short binding: `4051f5d541898cef742f35aeec757e7fc479f383`;
- full SHA-256: `4051f5d541898cef742f35aeec757e7fc479f383ae094c43939060b8069f4a55`;
- ESPHome: `2026.4.3`;
- fixed build epoch: `1785196800` (`2026-07-28 00:00:00 UTC`);
- test partition: `gh2d8_p2d9`, address `0x400000`, size `0x10000`;
- namespace: `gh2d8_s2d9`.

The firmware compiles the exact public unlock digest and CA certificate digest
from U1. The repaired ready repeater remains installed. The frozen V1 executor
remains the sole command parser and NVS writer.

## 4. Independent immutable builds

Two separate clean GitHub-hosted runners must compile the same final source SHA.
Each runner must:

1. install pinned ESPHome `2026.4.3`;
2. bind the ESPHome build timestamp to the fixed epoch;
3. remove the complete target `.esphome` build directory;
4. compile the repaired immutable target;
5. package bootloader, partition table, application and merged image;
6. record Python, OpenSSL, ESPHome and workflow environment digests.

The two deterministic payload TAR files must be byte-identical. Application,
bootloader, partition table, merged image, environment and public input bindings
must all match. The old repair-review merged image is explicitly rejected as the
final immutable image.

## 5. Locked recovery

Locked recovery is review input only and is limited to the test partition.

The only permitted future sequence, after a separately claimed physical D2 has
crossed its destructive boundary and only for a contract-named failure, is:

1. one pre-read of `0x400000` / `0x10000`;
2. one region erase of `0x400000` / `0x10000`;
3. one post-read of `0x400000` / `0x10000`;
4. verification that all bytes are `0xFF` and SHA-256 equals
   `71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063`.

Whole-chip erase, firmware write, NVS write, PREPARE, VERIFY, ACTIVATE,
CLEANUP, manual BOOT and additional reset are forbidden. Recovery success still
terminates as consumed failure and cannot return to normal execution.

Two independent recovery-package builds must also be byte-identical.

## 6. Final execution binding

After both immutable and recovery freezes pass, the workflow derives a new final
execution binding from:

- final source SHA;
- private-package and public-descriptor digests;
- candidate, CA and private command digests;
- repaired host-controller digest;
- immutable archive, payload, merged image and partition-table digests;
- recovery archive, payload and descriptor digests;
- Python, OpenSSL and ESPHome environment digests.

Deriving this binding does not authorize its use. The next gate is a separate
baseline read-only gate.

## 7. Explicit exclusions

This layer neither authorizes nor performs:

- board connection;
- USB or serial enumeration/open;
- esptool;
- Flash or physical NVS operation;
- network or Broker operation;
- PREPARE, VERIFY, ACTIVATE or CLEANUP;
- Ready, merge, release, tag or deployment.

Any frozen SHA, PR state, CI input, Artifact or main drift fails closed.
