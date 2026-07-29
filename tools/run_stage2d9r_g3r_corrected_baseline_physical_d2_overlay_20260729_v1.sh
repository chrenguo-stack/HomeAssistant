#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 4 ]; then
  echo "usage: $0 <contract-check|execute> <physical-request.json> <authorization.json> <result.json>" >&2
  exit 2
fi
MODE="$1"
REQUEST="$2"
AUTH="$3"
RESULT="$4"
case "$MODE" in
  contract-check|execute) ;;
  *) echo "invalid mode: $MODE" >&2; exit 2 ;;
esac
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/stage2d9r-corrected-overlay.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
PKG="$WORK/package"
IMM="$WORK/immutable-extracted"
REC="$WORK/recovery-extracted"
mkdir -m 700 "$PKG" "$IMM" "$REC"
find "$ROOT" -maxdepth 1 -type f -exec cp {} "$PKG/" \;
chmod 600 "$PKG"/*
WRAPPER="$PKG/h3_n2_stage2d9r_g3r_corrected_baseline_physical_d2_overlay_wrapper_20260729_v1.py"
if [ "$MODE" = "contract-check" ]; then
  exec python3 "$WRAPPER" contract-check \
    --package-root "$PKG" \
    --physical-request "$REQUEST" \
    --authorization-record "$AUTH" \
    --result-output "$RESULT"
fi
exec python3 "$WRAPPER" execute \
  --package-root "$PKG" \
  --physical-request "$REQUEST" \
  --authorization-record "$AUTH" \
  --immutable-payload-tar "$PKG/stage2d9r-g3r-repaired-immutable-payload-v1.tar" \
  --immutable-root "$IMM" \
  --recovery-payload-tar "$PKG/stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar" \
  --recovery-root "$REC" \
  --result-output "$RESULT"
