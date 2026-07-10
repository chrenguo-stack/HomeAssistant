#!/usr/bin/env bash
set -euo pipefail

# Pin font sources for reproducible builds. Do not use a floating "latest" URL.
VERSION="2026.07.01"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FONT_DIR="${ROOT_DIR}/fonts"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd unzip
require_cmd find

mkdir -p "${FONT_DIR}"

fetch_and_extract() {
  local repo="$1"
  local archive="$2"
  local pattern_primary="$3"
  local pattern_fallback="$4"
  local output_name="$5"
  local url="https://github.com/TakWolf/${repo}/releases/download/${VERSION}/${archive}"
  local zip_path="${TMP_DIR}/${archive}"
  local extract_dir="${TMP_DIR}/${output_name%.bdf}"

  echo "Downloading ${url}"
  curl --fail --location --retry 3 --connect-timeout 20 \
    --output "${zip_path}" "${url}"

  mkdir -p "${extract_dir}"
  unzip -q "${zip_path}" -d "${extract_dir}"

  local source_file
  source_file="$(find "${extract_dir}" -type f -iname "${pattern_primary}" -print -quit)"
  if [[ -z "${source_file}" ]]; then
    source_file="$(find "${extract_dir}" -type f -iname "${pattern_fallback}" -print -quit)"
  fi

  if [[ -z "${source_file}" ]]; then
    echo "Unable to find the expected BDF file in ${archive}" >&2
    echo "Available BDF files:" >&2
    find "${extract_dir}" -type f -iname '*.bdf' -print >&2
    exit 1
  fi

  cp "${source_file}" "${FONT_DIR}/${output_name}"
  echo "Installed ${FONT_DIR}/${output_name}"
}

# 14.8 display baseline:
# - Fusion Pixel Font at 10 px and 12 px
# - Ark Pixel Font at 16 px for large numeric values
fetch_and_extract \
  "fusion-pixel-font" \
  "fusion-pixel-font-10px-monospaced-bdf-v${VERSION}.zip" \
  "*10px*monospaced*zh_hans*.bdf" \
  "*10px*monospaced*zh_cn*.bdf" \
  "fusion-pixel-10px-monospaced-zh_hans.bdf"

fetch_and_extract \
  "fusion-pixel-font" \
  "fusion-pixel-font-12px-monospaced-bdf-v${VERSION}.zip" \
  "*12px*monospaced*zh_hans*.bdf" \
  "*12px*monospaced*zh_cn*.bdf" \
  "fusion-pixel-12px-monospaced-zh_hans.bdf"

fetch_and_extract \
  "ark-pixel-font" \
  "ark-pixel-font-16px-monospaced-bdf-v${VERSION}.zip" \
  "*16px*monospaced*zh_cn*.bdf" \
  "*16px*monospaced*zh_hans*.bdf" \
  "ark-pixel-16px-monospaced-zh_cn.bdf"

cat > "${FONT_DIR}/SOURCE.txt" <<EOF
Font release version: ${VERSION}
Fusion Pixel Font: https://github.com/TakWolf/fusion-pixel-font/releases/tag/${VERSION}
Ark Pixel Font: https://github.com/TakWolf/ark-pixel-font/releases/tag/${VERSION}
Downloaded by: tools/fetch_fonts.sh
EOF

echo "Font preparation complete."
