#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

export GH_DYNSEC_ADMIN_PASSWORD="$(openssl rand -hex 32)"

compose() {
  docker compose -f docker-compose.yml "$@"
}

cleanup() {
  local status=$?
  if (( status != 0 )); then
    echo "M2 Dynamic Security verification failed; redacted service status follows:" >&2
    compose ps >&2 || true
    compose logs --no-color broker >&2 || true
  fi
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  unset GH_DYNSEC_ADMIN_PASSWORD
  exit "${status}"
}
trap cleanup EXIT

compose down --volumes --remove-orphans >/dev/null 2>&1 || true
compose up --detach --build
compose exec -T tester python /verify.py

echo "M2 Dynamic Security verified: identity binding, least privilege, isolation and revocation."
