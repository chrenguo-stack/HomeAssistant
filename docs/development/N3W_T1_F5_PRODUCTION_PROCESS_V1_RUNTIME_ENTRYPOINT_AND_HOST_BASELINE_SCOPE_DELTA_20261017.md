# N3W T1 F5 V1 Runtime Entrypoint / HOST_BASELINE Scope Delta

Date: 2026-10-17

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_RUNTIME_ENTRYPOINT_AND_HOST_BASELINE_SOURCE_REPAIR_20261017_01
SCOPE_DELTA=APPROVED
PARENT_REVIEW_HEAD=f36e0d6842ce5a0e421e31141fc75019ded822a3

ADD_NEW_PATH=tools/n3w_t1_production_runtime.py
ADD_NEW_TEST=tests/tools/test_n3w_t1_production_runtime.py

EXISTING_ALLOWED_BOUNDARIES=
tools/n3w_t1_production.py;
tools/n3w_t1_ssh_transport.py;
tools/n3w_t1_fresh_product_staging_host.py;
tools/n3w_t1_fresh_host_baseline.py;
tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py;
tools/n3w_t1_production_contract.py;
associated tests/workflow

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

The scope delta is limited to assembling the already-frozen F5 normal route. It does not add a new product business state machine.

The runtime composition module may:
- construct the concrete ProductionBackend used by the normal CLI;
- own release-local artifact resolution and validation;
- use the existing SSHTransport connection epochs;
- invoke target production authority and existing F3/provision/F4/reboot primitives;
- stage run-owned temporary control material;
- issue only the fixed one-shot reboot action after the durable reboot-actuation marker.

HOST_BASELINE may gain a production mode that:
- validates exact target phase context;
- validates the exact approved release environment;
- writes a durable non-replayable local execution claim before APT/systemd mutation;
- installs only the approved Docker/Compose package versions;
- refuses an unavailable approved version rather than selecting a newer APT candidate.

The existing engineering/recovery routes remain preserved.
