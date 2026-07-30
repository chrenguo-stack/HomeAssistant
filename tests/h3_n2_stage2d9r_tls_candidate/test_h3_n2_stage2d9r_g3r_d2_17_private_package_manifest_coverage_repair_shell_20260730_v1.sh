#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/d2 17 g02 shell.XXXXXX")
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
mkdir -p "$TMP/private lane/payload/deep"
printf 'a\n' > "$TMP/private lane/a.txt"
printf 'nested one\n' > "$TMP/private lane/payload/SHA256SUMS"
printf 'nested two\n' > "$TMP/private lane/payload/deep/SHA256SUMS"
PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" "$TMP/private lane" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1]); target = Path(sys.argv[2])
sys.path.insert(0, str(root / 'tools'))
import h3_n2_stage2d9r_g3r_d2_17_private_package_manifest_coverage_contract_20260730_v1 as c
c.write_root_sha256sums(target)
result = c.verify_root_sha256sums(target)
assert result['status'] == 'PASS'
assert result['nested_sha256sums_count'] == 2
assert result['expected_count'] == result['observed_count'] == 3
PY
[ -z "$(find "$TMP" -type l -print -quit)" ]
[ -z "$(find "$TMP" \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -print -quit)" ]
