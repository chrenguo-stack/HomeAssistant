#!/bin/sh
set -eu
: "${PR214_ARTIFACT_ZIP:?}" "${SOURCE_SHA:?}"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
OUT=$(mktemp -d "${TMPDIR:-/tmp}/d2 16 shell.XXXXXX")
trap 'rm -rf "$OUT"' EXIT HUP INT TERM
python3 -B "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_packager_20260730_v1.py" \
  --source-root "$ROOT" --pr214-artifact "$PR214_ARTIFACT_ZIP" --source-sha "$SOURCE_SHA" --output "$OUT/review one"
python3 -B "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_packager_20260730_v1.py" \
  --source-root "$ROOT" --pr214-artifact "$PR214_ARTIFACT_ZIP" --source-sha "$SOURCE_SHA" --output "$OUT/review two"
diff -qr "$OUT/review one" "$OUT/review two"
(cd "$OUT/review one" && sha256sum -c SHA256SUMS)
PACKAGE="$OUT/review one/d2-16-full-inherited-authorization-preflight-repaired-physical-d2-execution-package"
PYTHONDONTWRITEBYTECODE=1 PR214_ARTIFACT_ZIP="$PR214_ARTIFACT_ZIP" SOURCE_SHA="$SOURCE_SHA" \
  python3 -B -m unittest tests.h3_n2_stage2d9r_tls_candidate.test_h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_20260730_v1
[ -f "$PACKAGE/h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repaired_physical_d2_wrapper_20260730_v1.py" ]
[ -z "$(find "$OUT/review one" -type f -iname '*physical-authorization*.json' -print -quit)" ]
[ -z "$(find "$OUT/review one" -type l -print -quit)" ]
[ -z "$(find "$OUT/review one" \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -print -quit)" ]
