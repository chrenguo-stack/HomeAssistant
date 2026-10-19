# N3-W / T1 F5 — KF-123 UNKNOWN-run controlled recovery exact artifact and read-only preauthorization preexecution

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_ARTIFACT_AND_READONLY_PREAUTH_20261019_01
STATE=READY_FOR_REAL_T1_READONLY_PREAUTH

PR=620
SOURCE_REVIEW_RESULT=CLOSED_PASS
SOURCE_REVIEW_DOC=docs/development/N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REVIEW_R4_20261019.md
EXECUTABLE_SOURCE_HEAD=4ab28033a6153cbe047849c8655d6a0ce06b667a
EXECUTABLE_SOURCE_TREE=dfa57d24f98c6db2cbd719073c894e8898d7fd3e
PR_HEAD_AT_PREEXECUTION=61d2f809add1175b5add1998cc63167679e6af19
SOURCE_DRIFT_AFTER_REVIEW=NONE

ARTIFACT_RUN_ID=39242546870
ARTIFACT_JOB_ID=118026591337
ARTIFACT_ID=12181787912
ARTIFACT_NAME=n3w-t1-f5-kf123-unknown-run-adjudicator-4ab28033a6153cbe047849c8655d6a0ce06b667a
ARTIFACT_SIZE_BYTES=99411
ARTIFACT_ZIP_SHA256=e79645082567b71a63046c4857a91a2f8c13982e492a4fccd43a5d317b519725
ARTIFACT_EXPIRES_AT=2026-11-18T11:09:17Z

MANIFEST_SHA256=63b947e94d885aff6a64c1214a1470a16cded76dd7ef0fb982ec410e1aafb035
ADJUDICATOR_SHA256=440a4b35c8e6c2eae1ad502802dc33358775772efcdfcc163cca4f3a7bfa7145
PRODUCTION_AUTHORITY_SHA256=5c9483571a6502483e44152c789cf2045d3aea84f4c384f65143d48f85434f44
PRODUCTION_CONTRACT_SHA256=492325b0a549e94806318d76303bc1d37e34bf263d978be2692b9ff05a846964

HISTORICAL_RUN_ID=3e37993537f9317dfb8070fd53fa20384de86cbd7c2a234857b55602c1280799
PHASE=F3_DEPLOY
EXPECTED_RUN_STATE=TERMINAL
EXPECTED_TERMINAL_STATE=FAIL
EXPECTED_FAILURE_CLASS=UNKNOWN
EXPECTED_LAST_COMPLETED_PHASE=HOST_BASELINE
EXPECTED_LAST_CLAIMED_PHASE=F3_DEPLOY
EXPECTED_F3_EXECUTION_RECORD_COUNT=0
EXPECTED_RECOVERY_ROOT=ABSENT

T1_ACCESS_REQUIRED=true
T1_MUTATION=false
LIVE_ADJUDICATION_EXECUTED=false
PRODUCT_SERVICE_START=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

## Exact artifact binding

GitHub Actions run `39242546870`, job `118026591337`, produced artifact `12181787912` from exact source head
`4ab28033a6153cbe047849c8655d6a0ce06b667a`.

The artifact metadata reports digest:

~~~text
sha256:e79645082567b71a63046c4857a91a2f8c13982e492a4fccd43a5d317b519725
~~~

An independent local download matched that digest exactly. The ZIP contains exactly four files:

~~~text
manifest.json
n3w_t1_f5_unknown_run_adjudicator.py
n3w_t1_production_authority.py
n3w_t1_production_contract.py
~~~

The package manifest is source-bound to `4ab28033...`, the historical KF-123 run, F3_DEPLOY, and
`f5_production_authority_and_adjudication_ledger_only`. It declares `live_runtime_mutation=false` and
`board_access=false`.

## Read-only preauthorization objective

The real T1-B probe must execute the exact packaged inspector without writing the recovery package or recovery ledger
to the target filesystem.

A PASS must freshly prove:

1. the target identity and SSH host-key binding still match the historical run plan;
2. the exact run remains consumed/no-replay `TERMINAL/FAIL/UNKNOWN`;
3. `last_completed_phase=HOST_BASELINE` and `last_claimed_phase=F3_DEPLOY`;
4. HOST_BASELINE remains exact `SUCCEEDED`;
5. F3 remains exact `UNKNOWN` with the historical failure code and null result;
6. the strict F3 production execution ledger count is zero;
7. product paths, containers, images, volumes, product networks and product units remain absent;
8. remote F3 staging residue remains absent;
9. Docker remains active;
10. the KF-123 recovery root remains absent;
11. no same-target later production run exists;
12. no target mutation, service start, reboot or board access occurs.

The probe must capture the fresh values:

~~~text
CURRENT_RUN_RECORD_SHA256=<fresh>
CURRENT_F3_PHASE_RECORD_SHA256=<fresh>
TARGET_BINDING_SHA256=<fresh verified>
RECOVERY_ROOT_ABSENT=true
~~~

Those hashes may only be used by a later separate one-shot live recovery authorization.

## macOS Terminal execution

The private T1 SSH locator stays outside GitHub. `T1_SSH` must already contain the private SSH target.

Run exactly:

~~~bash
set -euo pipefail
: "${T1_SSH:?set T1_SSH to the private T1 SSH target}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
gh api /repos/chrenguo-stack/HomeAssistant/actions/artifacts/12181787912/zip > "$ROOT/artifact.zip"
test "$(shasum -a 256 "$ROOT/artifact.zip" | awk '{print $1}')" = e79645082567b71a63046c4857a91a2f8c13982e492a4fccd43a5d317b519725
mkdir "$ROOT/artifact"
unzip -q "$ROOT/artifact.zip" -d "$ROOT/artifact"
python3 - "$ROOT/artifact" > "$ROOT/preauth.py" <<'PY'
import base64
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest_raw = (root / "manifest.json").read_bytes()
if hashlib.sha256(manifest_raw).hexdigest() != "63b947e94d885aff6a64c1214a1470a16cded76dd7ef0fb982ec410e1aafb035":
    raise SystemExit("LOCAL_BIND_FAIL:manifest_sha256")
manifest = json.loads(manifest_raw)
expected = {
    "schema": "gh.n3w-t1-f5-kf123-unknown-run-adjudication-package/1",
    "source_head": "4ab28033a6153cbe047849c8655d6a0ce06b667a",
    "historical_run_id": "3e37993537f9317dfb8070fd53fa20384de86cbd7c2a234857b55602c1280799",
    "phase": "F3_DEPLOY",
    "failing_source_head": "9048dd7c6b48c0620471919c0cf96c96bdab71f1",
    "failing_release_id": "31c8a8cd2d8424f93aaa7b4d0b78cfe2b73f1b035f4bdbce08a181ac56619420",
    "mutation_scope": "f5_production_authority_and_adjudication_ledger_only",
    "t1_access": False,
    "live_runtime_mutation": False,
    "board_access": False,
}
for key, value in expected.items():
    if manifest.get(key) != value:
        raise SystemExit(f"LOCAL_BIND_FAIL:manifest_{key}")
records = {item["path"]: item for item in manifest.get("files", [])}
expected_files = {
    "n3w_t1_f5_unknown_run_adjudicator.py": (44844, "440a4b35c8e6c2eae1ad502802dc33358775772efcdfcc163cca4f3a7bfa7145"),
    "n3w_t1_production_authority.py": (35569, "5c9483571a6502483e44152c789cf2045d3aea84f4c384f65143d48f85434f44"),
    "n3w_t1_production_contract.py": (17459, "492325b0a549e94806318d76303bc1d37e34bf263d978be2692b9ff05a846964"),
}
if set(records) != set(expected_files):
    raise SystemExit("LOCAL_BIND_FAIL:file_set")
payloads = {}
for name, (size, digest) in expected_files.items():
    raw = (root / name).read_bytes()
    record = records[name]
    if len(raw) != size or len(raw) != record.get("size"):
        raise SystemExit(f"LOCAL_BIND_FAIL:{name}:size")
    if hashlib.sha256(raw).hexdigest() != digest or digest != record.get("sha256"):
        raise SystemExit(f"LOCAL_BIND_FAIL:{name}:sha256")
    payloads[name] = base64.b64encode(raw).decode("ascii")
wrapper = f'''import base64,json,sys,types
payloads={payloads!r}
def load(name,filename):
    module=types.ModuleType(name)
    module.__file__=filename
    sys.modules[name]=module
    exec(compile(base64.b64decode(payloads[filename]),filename,"exec"),module.__dict__)
    return module
contract=load("n3w_t1_production_contract","n3w_t1_production_contract.py")
authority=load("n3w_t1_production_authority","n3w_t1_production_authority.py")
adjudicator=load("n3w_t1_f5_unknown_run_adjudicator","n3w_t1_f5_unknown_run_adjudicator.py")
if adjudicator.RUN_ID!="3e37993537f9317dfb8070fd53fa20384de86cbd7c2a234857b55602c1280799" or adjudicator.PHASE!="F3_DEPLOY":
    raise SystemExit("PREAUTH_FAIL:package_identity")
report=adjudicator.inspect_unknown_run()
print(json.dumps(report,sort_keys=True,separators=(",",":")))
'''
print(wrapper, end="")
PY
ssh "$T1_SSH" 'sudo -n python3 -' < "$ROOT/preauth.py"
~~~

This command downloads and verifies the exact GitHub artifact on the Mac, then streams the exact source bytes over
SSH into a single in-memory Python process. It does not copy the package to a T1 path and it does not call the
`adjudicate` command.

## Expected PASS

A successful final line is one JSON object containing at least:

~~~text
status=PASS
state=ELIGIBLE_FOR_ADJUDICATION
run_id=3e37993537f9317dfb8070fd53fa20384de86cbd7c2a234857b55602c1280799
phase=F3_DEPLOY
f3_production_execution_record_count=0
recovery_root_absent=true
authorization_consumed=true
replay_allowed=false
mutation_performed=false
mutation_state=NONE
product_service_start=false
reboot_executed=false
board_access=false
~~~

The actual `run_record_sha256`, `phase_record_sha256` and `target_binding_sha256` must be captured from the fresh
output.

## STOP rule

A PASS does not authorize live adjudication.

After the exact output is durably recorded, the next gate may only be a separate explicit one-shot live authorization
decision bound to the fresh run/phase hashes.

Any mismatch is a STOP condition. Do not create or edit the recovery ledger, do not change the production authority
records, do not replay F3, do not start product services and do not reboot.

~~~text
AUTO_EXECUTE_AFTER_PASS=false
LIVE_ADJUDICATION_AUTHORIZATION_GRANTED=false
STOP=true
~~~
