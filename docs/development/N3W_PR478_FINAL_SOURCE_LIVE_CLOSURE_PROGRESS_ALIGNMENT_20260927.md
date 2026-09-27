# N3-W PR #478 Final Source/Live Closure Progress Alignment

Updated: 2026-09-27  
Status: `CURRENT_PROGRESS_ALIGNMENT`

This document captures the public-safe durable state reached in the PR #478 source/live closure conversation. It supersedes older PR #478 live-pending snapshots where they conflict.

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant

PR474_STATE=OPEN_DRAFT
PR474_MERGED=false

PR475_STATE=OPEN_DRAFT
PR475_HEAD=c070cc50c72cbbd261e8e8ba6e70d00aa4ef5fd6
PR475_MERGED=false

PR478_STATE=OPEN_DRAFT
PR478_BASE=fix/n3w-t1-broker-lan-ip-independent-binding-20260925
PR478_BASE_SHA=c070cc50c72cbbd261e8e8ba6e70d00aa4ef5fd6
PR478_FINAL_REVIEW_HEAD=7cd007c99677a772cf2874b4a776fcc34f2d24d6
PR478_CLOSURE_DOCS_HEAD=c5f1051ee2f344798351dc692442a24b60439ba9
PR478_MERGED=false
PR478_MERGEABLE=true
PR478_FINAL_REVIEW_HEAD_CI=13_OF_13_PASS
PR478_CLOSURE_DOCS_HEAD_CI=13_OF_13_PASS
MERGE_AUTHORIZED=false
```

PR #478 is stacked on the current PR #475 head. The closure review does not authorize merging PR #474, #475, or #478.

## Exact R5 runtime/source authority

```text
LIVE_GUARD_BLOB=795903b06c7ee93a0602649e478bc070723ab8c0
LIVE_GUARD_UNIT_BLOB=b68d7d71ee43b26cb0481f0b278cf5739f3a2911
LIVE_ACTIVATION_UNIT_BLOB=c170c87d035b5c0d28c440514d40b5df360328d2
LIVE_DISPATCHER_BLOB=f733f5a1cfc936f77d1fabc383ccf262264e33d2

R5_R2_SOURCE_REVIEW=PASS
R5_SOURCE_BLOCKER_COUNT=0
```

The live T1 files used by final acceptance matched these repository blobs.

## Live R5 acceptance closure

```text
R5_LIVE_FIREWALL_ACCEPTANCE=PASS
R5_RELOAD_IDEMPOTENCE=PASS
R5_REAL_NM_REAPPLY_ACCEPTANCE=PASS
R5_REAL_LINK_DOWN_UP_ACCEPTANCE=PASS
R5_FAIL_CLOSED_ON_LINK_LOSS=PASS
R5_TRUSTED_POLICY_RESTORE_ON_LINK_RECOVERY=PASS
R5_SYSTEMD_PERSISTENCE_INSTALL_CONTRACT=PASS
R5_REBOOT_PERSISTENCE_ACCEPTANCE=PASS

PR478_FINAL_SOURCE_LIVE_CLOSURE=PASS
FINAL_SOURCE_LIVE_BLOCKER_COUNT=0
```

The accepted live route proved both first-position R5 anchors, exact shared policy, trusted ingress, host-local Docker non-trusted rejection, reload idempotence with foreign firewall preservation, real NetworkManager reapply, real Ethernet link-down fail-closed behavior, link-up trusted-policy restoration, and real host reboot persistence.

## Systemd persistence defect and repair

Reboot preparation found a real deployment-contract defect: both R5-owned systemd services were active but disabled.

The live T1 was repaired with bounded `systemctl enable` operations only. There was no service restart, NetworkManager reload, or reboot as part of that repair.

Repository repair added:

```text
infra/n3w-t1/install-systemd-persistence.sh
```

Required post-install evidence is:

```text
GUARD_ENABLED=enabled
ACTIVATION_ENABLED=enabled
SYSTEMD_PERSISTENCE_INSTALL=PASS
```

The lifecycle regression explicitly forbids `enable --now` and start/stop/restart side effects for this persistence-only operation.

## Reboot acceptance evidence

A real T1 host reboot was executed after the persistence contract was repaired.

```text
BOOT_ID_CHANGED=true
NETWORKMANAGER_ACTIVE=active
DOCKER_ACTIVE=active
GUARD_ACTIVE=active
ACTIVATION_ACTIVE=active

NETWORKMANAGER_ENABLED=enabled
DOCKER_ENABLED=enabled
GUARD_ENABLED=enabled
ACTIVATION_ENABLED=enabled

GUARD_APPLIED_TRUE_COUNT=2
GUARD_PASS_APPLY_COUNT=2
GUARD_ERROR_COUNT=0
NETWORKMANAGER_DISPATCHER_START_COUNT=1
DISPATCHER_OWNERSHIP_UNAMBIGUOUS=PASS
BOOT_ORDER_DOCKER_GUARD_ACTIVATION=PASS

BROKER_STATE=running
BROKER_RESTART_POLICY=no
MANAGER_STATE=running
TCP_8883_LISTEN_COUNT=1
RECIPES_BROKER_RUNNING_COUNT=0

POSTBOOT_REBOOT_PERSISTENCE=PASS
COLLECTION_RESULT=PASS
COLLECT_EXIT_CODE=0
```

The Manager restart counter changed across the host reboot and is not used as a cross-reboot continuity oracle. The accepted evidence is the changed host boot identity, preserved runtime identity, running postboot state, TLS client reconnection, and correct service ordering.

## Explicit non-claims / remaining scope

```text
EXTERNAL_UNTRUSTED_ETH0_PHYSICAL_NEGATIVE=NOT_PROVEN

B2_STABLE_T1_HOSTNAME_TLS_IDENTITY=OPEN_OUT_OF_SCOPE
B3_ALREADY_PROVISIONED_NODE_LITERAL_BROKER_IP_MIGRATION=OPEN_OUT_OF_SCOPE

PR474_MERGED=false
PR475_MERGED=false
PR478_MERGED=false
```

The host-local Docker non-trusted negative probe must not be represented as an external-untrusted physical eth0 test.

## Follow-up maintenance discovered during reboot

Two non-blocking maintenance items were observed and remain outside R5 closure:

```text
COMPOSE_FC4_HOMEASSISTANT_ORPHAN_WARNING=OPEN_MAINTENANCE
MOSQUITTO_PER_LISTENER_SETTINGS_DEPRECATION=OPEN_MAINTENANCE
R5_ACCEPTANCE_BLOCKER=false
```

For the Compose orphan warning, do not use `--remove-orphans` blindly. First classify the current Home Assistant container ownership and the exact Compose authority used by Broker activation.

For the Mosquitto warning, first bind the production T1 effective Broker configuration and running Mosquitto version. Do not perform repository-wide replacement based only on the warning.

Candidate future maintenance gates:

```text
N3W_T1_COMPOSE_ORPHAN_HOMEASSISTANT_OWNERSHIP_FORENSIC_20260927_01
N3W_T1_MOSQUITTO_PER_LISTENER_SETTINGS_DEPRECATION_FORENSIC_20260927_01
```

Neither maintenance gate is authorized by this alignment document.

## Public/private evidence boundary

No raw customer LAN address, SSH locator, credential, TLS private material, or raw private runtime log is stored here. Public evidence is restricted to source hashes, public-safe state, counts, and sanitized acceptance conclusions.

## Conversation-to-GitHub synchronization

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

The raw reboot collection remains outside the public repository because it contains live runtime/network evidence. Its SHA-256 is recorded above so the private artifact can be integrity-bound without publishing the raw log. All public-safe conclusions from that evidence are durably recorded in GitHub.

The durable repository authorities for this closure are this alignment document together with:

```text
docs/development/N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_REPAIR_20260926.md
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```
