# P2B Target-Armbian Read-only Evidence Execution Package

Gate:

`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION`

This package prepares a versioned Mac-side executor for the next read-only T1 evidence gate.

It does not authorize execution by itself.

The executor streams the exact bound probe over SSH stdin into:

`sudo -n python3 - --root /`

No probe file is copied to T1.

Execution requires the exact confirmation:

`READONLY TARGET ARMBIAN EVIDENCE: YES`

Private evidence is written only to an operator-selected local 0700 directory outside the repository.

Current boundary:

```text
T1_ACCESS=false
T1_READONLY_AUTHORIZATION_GRANTED=false
T1_MUTATION=false
T1_FILE_WRITE=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
ACTIVATION_TOPOLOGY_LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```
