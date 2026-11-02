# N3-W T1 Core Stack Clean Reference — R2 controlled start and reboot closure

Date: 2026-11-01

## 0. Final closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2_CONTROLLED_START_AND_REBOOT_20261101
RESULT=CLOSED_PASS

R2A=CLOSED_PASS
R2B=CLOSED_PASS

PRODUCT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R2A_CONTROL_HEAD=abeb6c31147bcf249361dcec7e9536eaed6106a6
R2B_CONTROL_HEAD=e15c64ac8f0f5f482a6c8538072031734002a559

BOARD_ACCESS=false
R3_EXECUTED=false
MERGE=false
```

R2 is closed because both required sub-gates passed:

1. R2A proved the first production start from the accepted R1 stopped Clean Reference.
2. R2B proved that the same production stack restores correctly after one real host reboot.

No board access occurred in R2.

## 1. R2A — first production start

R2A closure authority:

`docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2A_FIRST_PRODUCTION_START_CLOSURE_20261101.md`

Exact authority:

```text
R2A_CONTROL_HEAD=abeb6c31147bcf249361dcec7e9536eaed6106a6
CI_RUN=41307906081
CI_RESULT=SUCCESS
SOURCE_TEST_COUNT=12

ARTIFACT_ID=13084461803
ARTIFACT_DIGEST=sha256:f6acacb0ed92defe4b46a34c27c12c13fe2f4c27cb85f81b88a6fb4d1d728bc0
PACKAGE_MANIFEST_SHA256=a0bb9977314a7e4a3f9d051004c0bdcfe0410f2780f185d8aa68500d8919a76b
```

Accepted live result:

```text
R2A_APPLY_RC=0
R2A_POSTCHECK_RC=0
R2A_FINAL=PASS

TRANSACTION_STAGE=RUNTIME_STARTED
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_ALLOWED=false

RUNTIME_SERVICES=broker,homeassistant,manager
RUNNING_CONTAINER_COUNT=3
CONTAINER_STABILITY_SECONDS=30

BROKER_AUTHENTICATED_READINESS=true
BROKER_PORT_BINDING_EXACT=true
HOMEASSISTANT_HTTP_READY=true
HOMEASSISTANT_HTTP_STATUS=401

PRODUCTION_UNITS_ENABLED=true
PRODUCTION_UNITS_ACTIVE=true
CERTIFICATE_TIMER_ENABLED=true
CERTIFICATE_TIMER_ACTIVE_BEFORE_REBOOT=false

PRODUCTION_SERVICE_START=true
PERSISTENCE_ENABLED=true
PRE_REBOOT_READY=true

SAME_BOOT_AS_R2A_START=true
R2B_REBOOT_EXECUTED=false
```

R2A boot identity before activation and through the accepted same-boot window:

`8e649419-3243-4e23-973d-b53f2a626b82`

## 2. R2B source and exact artifact authority

Initial R2B exact authority:

```text
INITIAL_R2B_HEAD=3e767702cf360d104c7d9f3931448b0383f73505
INITIAL_CI_RUN=41312270219
INITIAL_CI_RESULT=SUCCESS
INITIAL_TEST_COUNT=6
INITIAL_ARTIFACT_ID=13085492792
INITIAL_ARTIFACT_DIGEST=sha256:d3234e7d6f4a4f09eaf4783642974a279e264f82145553c1425c2e9ad43f5ab8
INITIAL_PACKAGE_MANIFEST_SHA256=95d2b17aeb081c49b5a02f73ddd9b77f2e62b5679a65d7215cf7e2b7a158ed49
```

The first live R2B attempt stopped before authorization claim:

```text
STATUS=STOP
REASON=pre_reboot_unit_not_active:n3wfc4-provision-resume.service

R2B_AUTHORIZATION_CLAIMED=false
R2B_AUTHORIZATION_CONSUMED=false
REBOOT_EXECUTED=false
PRODUCTION_RUNTIME_UNCHANGED=true
```

This was a control-plane false STOP. The accepted R2A same-boot contract leaves
`n3wfc4-provision-resume.service` enabled but inactive before the first reboot.
The unit is `Type=oneshot`, `RemainAfterExit=yes`, `WantedBy=multi-user.target`;
after a real reboot it is expected to run automatically and remain active.

Repair:

```text
REPAIR_HEAD=e15c64ac8f0f5f482a6c8538072031734002a559
REPAIR_SCOPE=R2B pre-reboot state predicate + regression test only
R2A_SOURCE_DRIFT=false
R1_SOURCE_DRIFT=false
PRODUCT_SOURCE_DRIFT=false
```

Final R2B exact authority:

```text
R2B_CONTROL_HEAD=e15c64ac8f0f5f482a6c8538072031734002a559
CI_RUN=41313796825
CI_RESULT=SUCCESS
SOURCE_TEST_COUNT=7
R2A_BYTE_CONTINUITY=PASS
CONTROL_PACKAGE_VERIFY=PASS

ARTIFACT_ID=13086354529
ARTIFACT_NAME=n3w-t1-clean-reference-r2b-e15c64ac8f0f5f482a6c8538072031734002a559
ARTIFACT_DIGEST=sha256:b604da84720479d9f844aae49986ccc0b70fd469e25625e26ccd95386e432858
PACKAGE_MANIFEST_SHA256=87a8339ffd523709758ffda3ea64bd15303ca64dbaa0e28386fb3afc63b16eff
```

## 3. Old transport recovery

The transport package from the false STOP was preserved and later exact-verified before removal.

```text
OLD_TRANSPORT=/var/tmp/n3w-clean-reference-r2b.46639.package
VERIFIED_CONTROL_PLANE_HEAD=3e767702cf360d104c7d9f3931448b0383f73505
VERIFIED_MANIFEST_SHA256=95d2b17aeb081c49b5a02f73ddd9b77f2e62b5679a65d7215cf7e2b7a158ed49
OLD_TRANSPORT_RECOVERY=PASS
PRODUCT_MUTATION=false
REBOOT_EXECUTED=false
```

The repaired live route then proved:

```text
R2B_STATE_PRESENT=false
TRANSPORT_RESIDUAL_COUNT=0
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

before the repaired package was transferred.

## 4. R2B repaired live preflight

Accepted repaired preflight:

```text
STATUS=PASS

PRODUCT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R2A_CONTROL_HEAD=abeb6c31147bcf249361dcec7e9536eaed6106a6
R2B_CONTROL_HEAD=e15c64ac8f0f5f482a6c8538072031734002a559

R2A_TRANSACTION_SHA256=659c1ae76c6b73244d8de712b57e2183e9e4b22af3a1203269182af7e25a8fd9

PRE_BOOT_ID=8e649419-3243-4e23-973d-b53f2a626b82

RUNTIME_SERVICES=broker,homeassistant,manager
CONTAINER_COUNT=3
CERTIFICATE_FILE_COUNT=5

PROVISION_RESUME_PRE_REBOOT_STATE=inactive

BROKER_AUTHENTICATED_READINESS=true
HOMEASSISTANT_HTTP_READY=true
HOMEASSISTANT_HTTP_STATUS=401

REBOOT_EXECUTED=false
BOARD_ACCESS=false
```

## 5. R2B one-shot reboot claim

Authorization:

`N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2B_CONTROLLED_REBOOT_20261101_01`

Claim result:

```text
STATUS=PASS
STATE=REBOOT_PENDING

AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_ALLOWED=false

R2A_TRANSACTION_UNCHANGED=true
REBOOT_ACTUATION_REQUIRED=true
REBOOT_EXECUTED=false

RUNTIME_SERVICES=broker,homeassistant,manager
BROKER_AUTHENTICATED_READINESS=true
HOMEASSISTANT_HTTP_READY=true
```

The claim was persisted before reboot actuation and was not replayed.

## 6. Real host reboot evidence

```text
R2B_REBOOT_SSH_RC=0
R2B_SSH_DOWN_OBSERVED=true

PRE_BOOT_ID=8e649419-3243-4e23-973d-b53f2a626b82
POST_BOOT_ID=dc0f29fd-59f9-4f4c-ae79-206db2b22002

BOOT_ID_CHANGED=true
REBOOT_OBSERVED=true
```

The changed boot ID is the primary reboot proof.

## 7. Post-reboot persistence acceptance

R2B verifier returned:

```text
STATUS=PASS
STATE=REBOOT_ACCEPTED

AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_ALLOWED=false

R2A_TRANSACTION_UNCHANGED=true

RUNTIME_SERVICES=broker,homeassistant,manager

PRODUCTION_UNITS_ENABLED=true
PRODUCTION_UNITS_ACTIVE=true

CERTIFICATE_TIMER_ENABLED=true
CERTIFICATE_TIMER_ACTIVE=true
CERTIFICATE_SERVICE_QUIESCENT=true
CERTIFICATE_IDENTITY_UNCHANGED=true

BROKER_AUTHENTICATED_READINESS=true

HOMEASSISTANT_HTTP_READY=true
HOMEASSISTANT_HTTP_STATUS=401

CONTAINER_STABILITY_SECONDS=30
SAME_BOOT_DURING_POSTCHECK=true

REBOOT_ACCEPTANCE_PASSED=true
BOARD_ACCESS=false
```

Final independent postcheck:

```text
STATUS=PASS
TRANSACTION_STAGE=REBOOT_ACCEPTED

AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_ALLOWED=false
REBOOT_ACCEPTANCE_PASSED=true

R2A_TRANSACTION_UNCHANGED=true
FAILED_UNIT_COUNT=0

PRODUCTION_UNITS_ENABLED=true
PRODUCTION_UNITS_ACTIVE=true

CERTIFICATE_TIMER_ACTIVE=true
CERTIFICATE_SERVICE_QUIESCENT=true

RUNTIME_SERVICES=broker,homeassistant,manager
RUNNING_CONTAINER_COUNT=3

TRANSPORT_RESIDUAL_COUNT=0
BOARD_ACCESS=false
```

Final command summary:

```text
R2B_CLAIM_RC=0
R2B_VERIFY_RC=0
R2B_FINAL=PASS
R3_EXECUTED=false
```

## 8. R2 stable invariants established

R2 establishes the following Clean Reference invariants for the current T1_B baseline:

1. The exact R1 stopped image/runtime authority can be activated without image rebuild or registry pull.
2. Broker starts before Manager/Home Assistant and passes authenticated readiness before application services are accepted.
3. The production units are enabled for persistence.
4. The certificate timer is enabled and becomes active after a real reboot.
5. The certificate one-shot service returns to a quiescent inactive state.
6. Broker certificate identity remains unchanged across reboot.
7. The R2A transaction remains byte-identical across reboot.
8. The same three production services restore after reboot.
9. Home Assistant HTTP service is restored and enforces authentication.
10. No failed systemd units remain after acceptance.
11. R2 transport residue is zero after closure.
12. No board access is required for the R2 host persistence proof.

## 9. Final state and next boundary

```text
R0=CLOSED_PASS
R0H=CLOSED_PASS
S0=CLOSED_PASS
S1=CLOSED_PASS
R1=CLOSED_PASS
R2A=CLOSED_PASS
R2B=CLOSED_PASS
R2=CLOSED_PASS

R3=NOT_EXECUTED
A1=NOT_EXECUTED
MERGE=false
AUTO_EXECUTE_NEXT_GATE=false
```

R3 remains a separate gate and is not entered by this closure.
