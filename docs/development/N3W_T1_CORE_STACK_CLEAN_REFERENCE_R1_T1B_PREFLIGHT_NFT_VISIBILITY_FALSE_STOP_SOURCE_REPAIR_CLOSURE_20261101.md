# N3-W T1_Core_Stack Clean Reference — R1 T1_B preflight nft visibility false-STOP source repair closure

Date: 2026-11-01

## Result

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_PREFLIGHT_NFT_VISIBILITY_FALSE_STOP_SOURCE_REPAIR_20261101_01

ROOT_CAUSE=OPTIONAL_NFT_CLI_ABSENT_WAS_CLASSIFIED_AS_UNKNOWN_FIREWALL_VISIBILITY
T1_B_PRODUCT_RESIDUE_FOUND=false
T1_B_MUTATION=false

READONLY_INVENTORY_REPAIR_HEAD=ca849ed8565504529e2e39c823172ec2070cb5a8
READONLY_INVENTORY_SOURCE_COMMIT=083d3fed78ba2e0bee3a9d22d56838a5762294ae
READONLY_INVENTORY_TEST_COMMIT=ca849ed8565504529e2e39c823172ec2070cb5a8

DEDICATED_CI_RUN_ID=41290538736
DEDICATED_CI_RESULT=SUCCESS

R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
R1_DEPLOYMENT_TOOL_AUTHORITY_CHANGED=false

RESULT=CLOSED_PASS
```

## Observed false STOP

The first T1_B read-only preflight produced:

```text
DELETE_PRODUCT_STATE_CANDIDATE=[]
UNKNOWN_STOP=nft list ruleset / read_failed
NFT_ERROR=sudo: nft: command not found

DOCKER_CONTAINER_COUNT=0
DOCKER_IMAGE_COUNT=0
DOCKER_VOLUME_COUNT=0
DOCKER_NETWORKS=bridge,host,none
PRODUCT_PATHS_PRESENT=[]
PRODUCT_SYSTEMD_UNITS=[]
PRODUCT_LISTENERS=[]
IPTABLES_FILTER_READ=PASS
IPTABLES_NAT_READ=PASS
CLEAN_REFERENCE_CAPACITY_PREFLIGHT=PASS
TRANSPORT_CAPACITY_PASS=true
```

Therefore the STOP was in the observer classification rather than evidence of product residue.

## Bounded repair

The inventory classifier now accepts the missing `nft` CLI only when all of these are true:

1. the command is exactly `nft list ruleset`;
2. the failure says `command not found`;
3. `iptables -S` succeeds;
4. `iptables -t nat -S` succeeds.

In that exact case, the absent nft CLI is classified as:

```text
PRESERVE_HOST_BASELINE
reason=optional_backend_absent_iptables_views_complete
```

Fail-closed behavior remains for:

- any other nft failure;
- permission or execution errors;
- incomplete filter-table iptables visibility;
- incomplete NAT-table iptables visibility.

## Tests

Regression coverage was added for both directions:

- nft absent + both iptables views complete -> no UNKNOWN_STOP;
- nft absent + either iptables view incomplete -> UNKNOWN_STOP retained.

Existing firewall visibility fail-closed tests remain.

Dedicated CI:

```text
N3W T1 minimal baseline read-only inventory CI
RUN_ID=41290538736
STATUS=completed
CONCLUSION=success
```

## Authority boundary

This repair changes only the read-only observer used by the current predeployment gate.

It does not modify or replace the frozen R1 deployment/capacity tool authority:

```text
4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
```

The next action is a T1_B read-only revalidation using:

```text
READONLY_INVENTORY_AUTHORITY=ca849ed8565504529e2e39c823172ec2070cb5a8
R1_DEPLOYMENT_TOOL_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
```

No payload/image transfer, Docker mutation, product service start or board access is authorized.
