# N3-W B1 Astra Independent Review Closure

Updated: 2026-09-27  
Status: `INDEPENDENT_REVIEW_PASS`

## Scope

This record archives an independent Astra review of the already completed B1 route.

B1 is limited to:

`T1 Broker TLS 8883 publication depended on a concrete T1 LAN IPv4, causing Broker startup failure after customer-LAN/DHCP address changes.`

This review does not include B2, B3, PR #474, or current Board B pairing/provisioning state.

## Review authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REVIEW_MAIN=7720431d8fe62d7dd6db57570f1dcd1cdb109b38

B1_REVIEW_RESULT=PASS
B1_BLOCKER_COUNT=0
B1_DEFINED_SCOPE_CLOSED=true
KF097_GUARDED_JUSTIFIED=true

PR475_SOURCE_CLOSURE=PASS
PR478_SOURCE_CLOSURE=PASS
PR478_LIVE_CLOSURE=PASS

POST_FINAL_REVIEW_BEHAVIOR_DRIFT=NONE
```

The review re-read the source, pull requests, acceptance records, and execution scripts. It reviewed archived live evidence rather than reconnecting to T1. The private raw reboot log was not re-read; the repository summary and its SHA-256 binding were checked.

## Independent findings

The review confirmed:

- PR #475 closes the concrete-LAN-IPv4 Broker publication defect by requiring one explicit IPv4 wildcard TCP/8883 publication and rejecting invalid or overlapping forms.
- PR #478 closes the wildcard-ingress coverage gap with the combined `DOCKER-USER` and `INPUT` hooks feeding the same fail-closed project-owned policy chain.
- missing, disconnected, invalid, or ambiguous trusted-subnet state fails closed while preserving loopback.
- the Compose project-identity defect discovered during live activation was repaired by explicit `n3wfc4` project binding.
- apply/reload behavior is covered for idempotence, foreign-firewall preservation, anchor uniqueness, and first-position ownership.
- NetworkManager reapply, real link down/up, systemd persistence, and real reboot evidence support the defined B1 lifecycle closure.
- no post-final-review behavior drift was found between final review and merged PR #478 behavior.
- later maintenance changes do not invalidate B1.

## Explicit non-claims

```text
EXTERNAL_UNTRUSTED_ETH0_PHYSICAL_NEGATIVE=NOT_PROVEN
B2_STABLE_T1_HOSTNAME_TLS_IDENTITY=OPEN_OUT_OF_SCOPE
B3_ALREADY_PROVISIONED_NODE_LITERAL_BROKER_IP_MIGRATION=OPEN_OUT_OF_SCOPE
```

The host-local Docker negative probe must not be represented as an external-untrusted physical eth0 negative.

NetworkManager event handling is asynchronous. Existing evidence proves fail-closed/restoration behavior after the relevant events; it does not prove a zero-time transition window.

B1 closure does not imply that already-provisioned nodes automatically discover a new Broker address after T1 changes networks.

## Closure

```text
B1_INDEPENDENT_REVIEW_CLOSURE=PASS
B1_REOPEN_REQUIRED=false
KF097_STATUS=GUARDED
SOURCE_MUTATION=false
T1_MUTATION=false
BOARD_ACCESS=false
```
