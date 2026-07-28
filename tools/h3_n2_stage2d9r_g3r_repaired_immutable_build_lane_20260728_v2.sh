#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: $0 <a|b> <source-sha> <output-dir> <workflow-path>" >&2
  exit 2
fi

LANE="$1"
SOURCE_SHA="$2"
OUTPUT_DIR="$3"
WORKFLOW_PATH="$4"
case "$LANE" in
  a|b) ;;
  *) echo "invalid lane" >&2; exit 2 ;;
esac

EMPTY_SHA256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
SOURCE_DATE_EPOCH=1785196800
export SOURCE_DATE_EPOCH TZ=UTC LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONHASHSEED=0

PUBLIC_DIR=tests/h3_n2_stage2d9r_tls_candidate/public_repaired_tlsvalid03
BINDING_FILE=tests/h3_n2_stage2d9r_tls_candidate/stage2d9r_g3r_repaired_immutable_build_binding_20260728_v1.json
PIPELINE=tools/h3_n2_stage2d9r_g3r_repaired_immutable_recovery_pipeline_20260728_v1.py
HOST_CONTROLLER=tools/h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py
TARGET_DIR=firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3r_tls_prepare
TARGET_CONFIG=greenhouse_profile_isolated_device_g3r_repaired_immutable_20260728_v1.yml
PARTITION_CSV=firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3_prepare/stage2d9_g3_partitions_20260722_v65.csv

python - <<'PY' > /tmp/stage2d9r-repaired-esphome-writer-sha.txt
import hashlib
import os
from pathlib import Path
import esphome.writer

path = Path(esphome.writer.__file__).resolve(strict=True)
text = path.read_text(encoding="utf-8")
old = (
    '    build_time = int(time.time())\n'
    '    build_time_str = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(build_time))\n'
)
new = (
    '    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")\n'
    '    build_time = int(source_date_epoch) if source_date_epoch is not None else int(time.time())\n'
    '    build_time_str = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(build_time))\n'
)
if text.count(old) != 1:
    raise RuntimeError("unexpected ESPHome 2026.4.3 writer source")
path.write_text(text.replace(old, new), encoding="utf-8")
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY

WRITER_SHA="$(cat /tmp/stage2d9r-repaired-esphome-writer-sha.txt)"
test "${#WRITER_SHA}" = 64

{
  python --version
  python -m pip freeze --all
} | LC_ALL=C sort > /tmp/stage2d9r-repaired-python-environment.txt
LC_ALL=C openssl version -a > /tmp/stage2d9r-repaired-openssl-environment.txt
printf '%s\n' \
  'esphome==2026.4.3' \
  "esphome-writer-sha256=$WRITER_SHA" \
  "source-date-epoch=$SOURCE_DATE_EPOCH" \
  > /tmp/stage2d9r-repaired-esphome-environment.txt

test -s /tmp/stage2d9r-repaired-python-environment.txt
test -s /tmp/stage2d9r-repaired-openssl-environment.txt
test -s /tmp/stage2d9r-repaired-esphome-environment.txt
grep -F 'OpenSSL' /tmp/stage2d9r-repaired-openssl-environment.txt

PYTHON_ENV_SHA="$(sha256sum /tmp/stage2d9r-repaired-python-environment.txt | awk '{print $1}')"
OPENSSL_ENV_SHA="$(sha256sum /tmp/stage2d9r-repaired-openssl-environment.txt | awk '{print $1}')"
ESPHOME_ENV_SHA="$(sha256sum /tmp/stage2d9r-repaired-esphome-environment.txt | awk '{print $1}')"
WORKFLOW_FILE_SHA="$(sha256sum "$WORKFLOW_PATH" | awk '{print $1}')"
HELPER_SHA="$(sha256sum "$0" | awk '{print $1}')"
COMPILE_WORKFLOW_SHA="$(printf '%s\n%s\n' "$WORKFLOW_FILE_SHA" "$HELPER_SHA" | sha256sum | awk '{print $1}')"

test "$PYTHON_ENV_SHA" != "$EMPTY_SHA256"
test "$OPENSSL_ENV_SHA" != "$EMPTY_SHA256"
test "$ESPHOME_ENV_SHA" != "$EMPTY_SHA256"

rm -rf "$TARGET_DIR/.esphome"
(
  cd "$TARGET_DIR"
  esphome config "$TARGET_CONFIG" 2>&1 | tee "/tmp/stage2d9r-repaired-config-$LANE.log"
  esphome compile "$TARGET_CONFIG" 2>&1 | tee "/tmp/stage2d9r-repaired-compile-$LANE.log"
)
grep -F 'INFO Successfully compiled program.' "/tmp/stage2d9r-repaired-compile-$LANE.log"
APP="$TARGET_DIR/.esphome/build/gh-2d9r-g3r-r3/.pioenvs/gh-2d9r-g3r-r3/firmware.bin"
test -f "$APP"
strings "$APP" | grep -Fx '2026-07-28 00:00:00 +0000'

python "$PIPELINE" build-immutable \
  --build-root "$TARGET_DIR/.esphome/build/gh-2d9r-g3r-r3" \
  --output-dir "$OUTPUT_DIR" \
  --lane "$LANE" \
  --source-sha "$SOURCE_SHA" \
  --python-environment-sha256 "$PYTHON_ENV_SHA" \
  --openssl-environment-sha256 "$OPENSSL_ENV_SHA" \
  --esphome-environment-sha256 "$ESPHOME_ENV_SHA" \
  --workflow-sha256 "$COMPILE_WORKFLOW_SHA" \
  --public-dir "$PUBLIC_DIR" \
  --binding "$BINDING_FILE" \
  --partition-csv "$PARTITION_CSV" \
  --host-controller "$HOST_CONTROLLER" \
  | tee "/tmp/stage2d9r-repaired-package-$LANE.log"

grep -Fx 'STAGE2D9R_REPAIRED_IMMUTABLE_BUILD=PASS' "/tmp/stage2d9r-repaired-package-$LANE.log"

OUTPUT_DIR="$OUTPUT_DIR" EMPTY_SHA256="$EMPTY_SHA256" python - <<'PY'
import json
import os
from pathlib import Path
value = json.loads((Path(os.environ["OUTPUT_DIR"]) / "build-record.json").read_text())
assert value["openssl_environment_sha256"] != os.environ["EMPTY_SHA256"]
assert value["execution_authorized"] is False
assert value["board_operation_authorized"] is False
PY

printf '%s\n' \
  'STAGE2D9R_REPAIRED_IMMUTABLE_BUILD_LANE_V2=PASS' \
  "LANE=$LANE" \
  "OPENSSL_ENVIRONMENT_SHA256=$OPENSSL_ENV_SHA" \
  'OPENSSL_ENVIRONMENT_NONEMPTY=true' \
  'BOARD_OPERATION=false' \
  'NETWORK_OPERATION=false'
