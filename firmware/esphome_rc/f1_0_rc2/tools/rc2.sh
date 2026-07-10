#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

required_fonts=(
  "fonts/fusion-pixel-10px-monospaced-zh_hans.bdf"
  "fonts/fusion-pixel-12px-monospaced-zh_hans.bdf"
  "fonts/ark-pixel-16px-monospaced-zh_cn.bdf"
)

missing_fonts=()
for font_file in "${required_fonts[@]}"; do
  if [[ ! -f "${font_file}" ]]; then
    missing_fonts+=("${font_file}")
  fi
done

if (( ${#missing_fonts[@]} > 0 )); then
  echo "RC2 font preflight: ${#missing_fonts[@]} required font file(s) are missing."
  printf '  - %s\n' "${missing_fonts[@]}"
  echo "Downloading the pinned 2026.07.01 font release..."
  bash tools/fetch_fonts.sh
fi

for font_file in "${required_fonts[@]}"; do
  if [[ ! -s "${font_file}" ]]; then
    echo "Font preparation failed: ${font_file} is missing or empty." >&2
    exit 1
  fi
done

if ! command -v esphome >/dev/null 2>&1; then
  echo "ESPHome is not available in PATH." >&2
  exit 1
fi

action="${1:-compile}"
if (( $# > 0 )); then
  shift
fi

case "${action}" in
  config|compile|run|logs|clean)
    exec esphome "${action}" f1_0_rc2.yml "$@"
    ;;
  *)
    echo "Usage: bash tools/rc2.sh {config|compile|run|logs|clean} [ESPHome arguments...]" >&2
    exit 2
    ;;
esac
