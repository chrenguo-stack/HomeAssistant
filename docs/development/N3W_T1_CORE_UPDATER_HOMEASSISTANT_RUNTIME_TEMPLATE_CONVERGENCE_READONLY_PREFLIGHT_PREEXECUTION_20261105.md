# N3-W T1 Core Updater — Home Assistant runtime-template convergence read-only preflight

Date: 2026-11-05

## Gate

```text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_RUNTIME_TEMPLATE_CONVERGENCE_READONLY_PREFLIGHT_20261105_01
STATE=PREEXECUTION_SOURCE_CLOSURE

AUTHORITY_PARENT_HEAD=9aa8c9b42f32d94804decdb6b360ade58e4d728d
BASE_MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774

T1_ACCESS=READONLY
T1_MUTATION=false
PERSISTENT_T1_FILE_WRITE=false
TEMPORARY_SCRATCH_WRITE=true
SERVICE_RESTART=false
IMAGE_LOAD=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
CREDENTIAL_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This gate is the first real-T1 check after the Home Assistant product-grade updater source
preparation. It does not convert the runtime template and does not authorize an HA image upgrade.

## Fresh authority

Repository authority at gate entry:

```text
MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER=local/n3w-mosquitto:2.1.2-3184566d

MANAGER_BINDING_MODE=dynamic
HOMEASSISTANT_BINDING_MODE=legacy_static
BROKER_BINDING_MODE=legacy_static
```

Canonical authority blob:

```text
infra/n3w-t1/production/t1-core-stack-current.json
blob=07ceb3b352f21d925127caa71304cc3b29827fdb
```

The inspected source is bound to:

```text
tools/n3w_t1_core_updater_ha_template_convergence.py
blob=9e8ad6ced381e6b4fa9ec146b4f143769c316ceb
schema=gh.n3w-t1-core-updater-ha-template-convergence/1
```

## Execution package

Versioned execution package:

```text
tools/execution_packages/n3w/u2/ha_template_convergence_readonly_preflight/executor.py
tools/execution_packages/n3w/u2/ha_template_convergence_readonly_preflight/manifest.json
```

The package validates the exact local Git head, exact inspector blob, exact current-authority blob,
clean tracked worktree and authority-parent ancestry before any SSH access.

No script is staged persistently onto T1. The exact reviewed inspector source is streamed over SSH
stdin to:

```text
sudo -n python3 -B -
```

The inspector reads only:

```text
/etc/n3wfc4/docker-compose.yml
/etc/n3wfc4/docker-compose.env
```

It constructs the candidate HA binding in a temporary directory only, renders current and candidate
Compose with `docker compose config --format json`, compares the complete rendered documents, and
removes the temporary directory automatically.

Temporary scratch files are explicitly permitted by this read-only gate; product-path writes and
persistent T1 writes are not.

## Double-read requirement

The executor runs the inspector twice.

Both runs must independently report:

```text
status=PASS
mutation=false
expected_homeassistant_image=local/n3w-homeassistant:2026.10.0-0c73235a
current_binding_mode=legacy_static
candidate_binding_mode=dynamic
render_semantically_equal=true
product_path_write=false
service_restart=false
```

The following values must be byte-stable across both runs:

```text
current_compose_sha256
current_env_sha256
candidate_compose_sha256
candidate_env_sha256
current_render_sha256
candidate_render_sha256
```

Any drift is STOP, not PASS.

## Evidence

Raw inspection reports are local private evidence only:

```text
inspection-1.json
inspection-2.json
result.json
```

The evidence directory must be mode 0700 and each file mode 0600. Raw T1 SSH target is not included
in the public result.

## Pass meaning

A PASS proves only:

1. the current real-T1 HA Compose source is the expected legacy-static predecessor;
2. adding exactly the current HA image to `GH_HOMEASSISTANT_IMAGE` and replacing the HA image
   literal with the dynamic variable renders to the same effective Compose model;
3. the proof is stable over two consecutive read-only inspections;
4. no product path, service, image, credential, updater transaction or board state is mutated.

It does not prove the future HA 2026.10.4 artifact, apply, rollback, or final product acceptance.

## Next gate after PASS

```text
NEXT_ONE_GATE=EXACT_HA_2026_10_4_UPDATER_ARTIFACT_AND_COMPONENT_TARGET
NEXT_GATE_LIVE_MUTATION=false
STACK_1_1_0_BUILD=false
```

The next work remains inside the T1_Core_Updater validation program: build and bind the exact
Home Assistant 2026.10.4 ARM64 artifact and component target before any live mutation.
