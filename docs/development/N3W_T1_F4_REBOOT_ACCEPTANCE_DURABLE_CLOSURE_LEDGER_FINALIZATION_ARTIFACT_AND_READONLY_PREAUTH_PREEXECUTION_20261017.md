# N3-W T1 F4 durable reboot ledger finalization — exact artifact and read-only preauthorization preexecution

Date: 2026-10-17

```text
TASK=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_LEDGER_FINALIZATION_ARTIFACT_AND_READONLY_PREAUTH_20261017_01
STATUS=READY_FOR_LOCAL_READONLY_PREAUTH_EXECUTION

PR=605
PR_STATE=OPEN_DRAFT_NOT_MERGED
PRODUCT_SOURCE_REVIEW_HEAD=19bd98386c4828c0768f2f3936429db8c7a59adf
PRODUCT_SOURCE_REVIEW_TREE=f5b66faf690c88d655e01ffc0a5d5ef122b589af
PRODUCT_SOURCE_REVIEW_RESULT=CLOSED_PASS
PRODUCT_SOURCE_REVIEW_CI=PASS:13/13

CANDIDATE_HEAD_BEFORE_THIS_DOC=215f9efb893744231a888ff6d5d600c14731f313
PRODUCT_SOURCE_DRIFT_AFTER_REVIEW=NONE
POST_REVIEW_BRANCH_DELTA=DOCS_ONLY

ARTIFACT_RUN_ID=38924889363
ARTIFACT_JOB_ID=117053791078
ARTIFACT_ID=12056436272
ARTIFACT_NAME=n3w-t1-f4-reboot-successor-control-19bd98386c4828c0768f2f3936429db8c7a59adf
ARTIFACT_EXPIRES_AT=2026-10-30T15:33:27Z
ARTIFACT_ZIP_SHA256=ff2b35a7b7a3384ac2a1ee290c93ccdb7130de4166b2385aa60e3ca36a2bf764
TRANSPORT_TAR_SHA256=ade461a836d1a118291c5e7d2e3bfcb7e990ead41c2832c31f84705e578a50ba
MANIFEST_SHA256=bab1f7f1a4834d4f85bd01ae05d4569d32798e6661c72caf0d2636cfbaecbe70
FINALIZER_EXECUTOR_SHA256=c4a738656e98b5f8bae27a34aba845c002287b253f99f54cf459f8d292f7d9ec
PACKAGE_FILE_COUNT=4
PACKAGE_SECRET_VALUES_INCLUDED=false
PACKAGE_LIVE_RUNTIME_MUTATION=false
PACKAGE_REBOOT_EXECUTED=false
PACKAGE_BOARD_ACCESS=false

EXPECTED_INSTALLED_SOURCE_HEAD=66788b22fc55f7bf1c003e0b97bc7e75ce859e35
EXPECTED_INSTALLED_MANIFEST_SHA256=f970a4e49730f0f653e52508ef13bec2f018d8c47ea589ff295cfe398529f9a7
EXPECTED_F4_TRANSACTION_SHA256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
EXPECTED_PENDING_REBOOT_CLAIM_SHA256=61429105bc05f135f3d0b8be338d74899b2466cb65fa896be4254d37a54c5028
EXPECTED_POST_BOOT_ID_SHA256=e04f445426ee875b1c429a33c6b1e6893175727118fc8ad28e24c431c1fa66c7
LAST_PROVEN_CERTIFICATE_STATUS_SHA256=446404d0e3725bf0e8fa9b6bd11bd67c83f16871a6e196b1cc950043ad229af4

REAL_T1_DURABLE_REBOOT_CLAIM_LAST_PROVEN=REBOOT_PENDING
REBOOT_AUTHORIZATION=CONSUMED_NO_REPLAY
FINALIZER_LIVE_AUTHORIZATION_GRANTED=false
FINALIZER_EXECUTED_ON_REAL_T1=false

T1_ACCESS_REQUIRED_FOR_NEXT_STEP=true
T1_PRODUCTION_STATE_MUTATION=false
T1_RUNTIME_MUTATION=false
T1_BOUNDED_TMP_STAGING_ALLOWED=true
BOARD_ACCESS=false
MERGE=false
```

## 1. Frozen route

The source-review gate is closed. The next route is not another source repair and not a second reboot. It is only:

```text
exact reviewed finalizer artifact
-> bounded temporary staging
-> fresh read-only preauthorization on the real T1
-> STOP
-> separate live ledger-finalization authorization decision
```

The already consumed reboot authorization must never be replayed. The existing
`REBOOT_PENDING` record must not be manually edited or deleted.

## 2. Exact artifact binding

GitHub Actions run `38924889363`, job `117053791078`, produced artifact
`12056436272` from exact source head
`19bd98386c4828c0768f2f3936429db8c7a59adf`.

Independent download verification matched GitHub's artifact digest exactly:

```text
ZIP_SHA256=ff2b35a7b7a3384ac2a1ee290c93ccdb7130de4166b2385aa60e3ca36a2bf764
TAR_SHA256=ade461a836d1a118291c5e7d2e3bfcb7e990ead41c2832c31f84705e578a50ba
MANIFEST_SHA256=bab1f7f1a4834d4f85bd01ae05d4569d32798e6661c72caf0d2636cfbaecbe70
FINALIZER_EXECUTOR_SHA256=c4a738656e98b5f8bae27a34aba845c002287b253f99f54cf459f8d292f7d9ec
```

The package contains exactly the four files required by the frozen reboot-successor package contract.

## 3. Read-only preauthorization purpose

The preauthorization must freshly prove all of the following without changing production state:

1. the staged artifact is the exact reviewed package;
2. the executing finalizer file self-binds to that package;
3. the durable reboot claim is still the exact historical `REBOOT_PENDING` record;
4. the installed `CONTROL_READY` control remains exact;
5. the F4 transaction remains exact;
6. the install/recovery linkage remains exact;
7. a fresh post-reboot acceptance report still passes;
8. the current boot is still the already accepted post-reboot boot;
9. the consumed reboot authorization remains non-replayable;
10. no finalization write occurs.

A changed certificate lifecycle status is not automatically a failure. The fresh reboot verifier and installed
runtime guard are the authority for current certificate state. The last-proven certificate-status SHA-256 above is
historical evidence, not a requirement that the mutable status file never change.

## 4. Local execution package

Run from macOS Terminal. The user's private T1 SSH locator stays outside GitHub.

The command requires `T1_SSH` to already contain the private SSH target, for example an existing SSH alias or
`user@host`. It downloads the exact GitHub artifact, verifies the ZIP and TAR, stages only under `/tmp` on T1,
executes the staged repository-owned finalizer code in a read-only probe, and prints one JSON result.

```bash
set -euo pipefail
: "${T1_SSH:?set T1_SSH to the private T1 SSH target}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
gh api /repos/chrenguo-stack/HomeAssistant/actions/artifacts/12056436272/zip > "$ROOT/artifact.zip"
test "$(shasum -a 256 "$ROOT/artifact.zip" | awk '{print $1}')" = ff2b35a7b7a3384ac2a1ee290c93ccdb7130de4166b2385aa60e3ca36a2bf764
mkdir "$ROOT/artifact"
unzip -q "$ROOT/artifact.zip" -d "$ROOT/artifact"
test "$(shasum -a 256 "$ROOT/artifact/n3w-t1-f4-reboot-successor-control.tar" | awk '{print $1}')" = ade461a836d1a118291c5e7d2e3bfcb7e990ead41c2832c31f84705e578a50ba
mkdir "$ROOT/package"
tar -xf "$ROOT/artifact/n3w-t1-f4-reboot-successor-control.tar" -C "$ROOT/package"
test "$(shasum -a 256 "$ROOT/package/reboot-successor-control/reboot-successor-manifest.json" | awk '{print $1}')" = bab1f7f1a4834d4f85bd01ae05d4569d32798e6661c72caf0d2636cfbaecbe70
test "$(shasum -a 256 "$ROOT/package/reboot-successor-control/tools/n3w_t1_f4_reboot_authority.py" | awk '{print $1}')" = c4a738656e98b5f8bae27a34aba845c002287b253f99f54cf459f8d292f7d9ec
cat > "$ROOT/preauth.py" <<'PY'
import importlib.util
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
authority = root / "tools/n3w_t1_f4_reboot_authority.py"
spec = importlib.util.spec_from_file_location("n3w_f4_ledger_finalizer_preauth", authority)
if spec is None or spec.loader is None:
    raise SystemExit("PREAUTH_FAIL:import_spec")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

source_head = "19bd98386c4828c0768f2f3936429db8c7a59adf"
manifest_sha256 = "bab1f7f1a4834d4f85bd01ae05d4569d32798e6661c72caf0d2636cfbaecbe70"
installed_source_head = "66788b22fc55f7bf1c003e0b97bc7e75ce859e35"
installed_manifest_sha256 = "f970a4e49730f0f653e52508ef13bec2f018d8c47ea589ff295cfe398529f9a7"
transaction_sha256 = "49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b"
pending_sha256 = "61429105bc05f135f3d0b8be338d74899b2466cb65fa896be4254d37a54c5028"
expected_post_boot = "e04f445426ee875b1c429a33c6b1e6893175727118fc8ad28e24c431c1fa66c7"

package = module._package(root, source_head=source_head, manifest_sha256=manifest_sha256)
module._validate_recovery_entrypoint(package)
if module._sha256(module.REBOOT_CLAIM_PATH) != pending_sha256:
    raise SystemExit("PREAUTH_FAIL:pending_claim_sha256")
claim = module._record(module.REBOOT_CLAIM_PATH, 0o600)
module._verify_installed_control_material_binding(
    source_head=installed_source_head,
    manifest_sha256=installed_manifest_sha256,
    expected_transaction_sha256=transaction_sha256,
    allowed_stages=frozenset({"CONTROL_READY"}),
)
if (
    claim.get("schema") != module.SCHEMA_REBOOT
    or claim.get("stage") != "REBOOT_PENDING"
    or claim.get("source_head") != installed_source_head
    or claim.get("control_manifest_sha256") != installed_manifest_sha256
    or claim.get("f4_transaction_sha256") != transaction_sha256
    or claim.get("reboot_authorization_claimed") is not True
    or claim.get("reboot_authorization_consumed") is not True
    or claim.get("reboot_authorization_replay_allowed") is not False
    or claim.get("reboot_acceptance_passed") is not False
    or claim.get("board_access") is not False
):
    raise SystemExit("PREAUTH_FAIL:pending_claim_contract")
report = module._post_reboot_acceptance_report()
module._validate_reboot_acceptance_report(report, claim)
if report.get("post_boot_id_sha256") != expected_post_boot:
    raise SystemExit("PREAUTH_FAIL:post_boot_id_drift")
executor = package["files"].get("tools/n3w_t1_f4_reboot_authority.py")
result = {
    "status": "PASS",
    "state": "LEDGER_FINALIZATION_PREAUTHORIZED_READONLY",
    "source_head": source_head,
    "manifest_sha256": manifest_sha256,
    "executor_sha256": executor.get("sha256") if isinstance(executor, dict) else None,
    "installed_source_head": installed_source_head,
    "installed_manifest_sha256": installed_manifest_sha256,
    "f4_transaction_sha256": transaction_sha256,
    "pending_claim_sha256": pending_sha256,
    "post_boot_id_sha256": report["post_boot_id_sha256"],
    "certificate_status_sha256": report["certificate_status_sha256"],
    "acceptance_report_sha256": module._canonical_sha(report),
    "reboot_authorization_consumed": True,
    "reboot_authorization_replay_allowed": False,
    "production_state_mutation": False,
    "board_access": False,
}
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
PY
tar -C "$ROOT/package" -cf "$ROOT/preauth-package.tar" reboot-successor-control
scp "$ROOT/preauth-package.tar" "$ROOT/preauth.py" "$T1_SSH:/tmp/"
ssh "$T1_SSH" 'set -euo pipefail; D=/tmp/n3w-f4-ledger-finalizer-preauth; rm -rf "$D"; mkdir -m 700 "$D"; tar -xf /tmp/preauth-package.tar -C "$D"; sudo python3 /tmp/preauth.py "$D/reboot-successor-control"'
```

## 5. Expected result and STOP boundary

PASS requires one JSON object with:

```text
status=PASS
state=LEDGER_FINALIZATION_PREAUTHORIZED_READONLY
source_head=19bd98386c4828c0768f2f3936429db8c7a59adf
manifest_sha256=bab1f7f1a4834d4f85bd01ae05d4569d32798e6661c72caf0d2636cfbaecbe70
executor_sha256=c4a738656e98b5f8bae27a34aba845c002287b253f99f54cf459f8d292f7d9ec
installed_source_head=66788b22fc55f7bf1c003e0b97bc7e75ce859e35
installed_manifest_sha256=f970a4e49730f0f653e52508ef13bec2f018d8c47ea589ff295cfe398529f9a7
f4_transaction_sha256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
pending_claim_sha256=61429105bc05f135f3d0b8be338d74899b2466cb65fa896be4254d37a54c5028
post_boot_id_sha256=e04f445426ee875b1c429a33c6b1e6893175727118fc8ad28e24c431c1fa66c7
reboot_authorization_consumed=true
reboot_authorization_replay_allowed=false
production_state_mutation=false
board_access=false
```

The current certificate-status SHA-256 and acceptance-report SHA-256 may be fresh values and must be recorded from the
actual output.

After PASS, STOP. Do not call `finalize-reboot-acceptance` yet. The next live gate is a separate target-local ledger
mutation and requires a new explicit authorization decision.

## 6. Failure handling

Any mismatch is a STOP condition. Do not repair target files, do not rewrite the reboot claim, do not re-run reboot
authorization, do not reboot, and do not invoke the certificate lifecycle manually.

A preauth failure is evidence to classify, not permission to mutate.

```text
NEXT_ONE_GATE_AFTER_PASS=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_LEDGER_FINALIZATION_LIVE_20261017_01
AUTO_EXECUTE_AFTER_PASS=false
MERGE=false
```
