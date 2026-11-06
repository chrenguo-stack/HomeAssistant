#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-core-updater-ha-template-convergence/1"
DEFAULT_COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
DEFAULT_ENV = Path("/etc/n3wfc4/docker-compose.env")
PROJECT = "n3wfc4"
DYNAMIC_HA_BINDING = (
    '"${GH_HOMEASSISTANT_IMAGE:?GH_HOMEASSISTANT_IMAGE required}"'
)


class ConvergenceError(RuntimeError):
    pass


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha(document: Any) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ConvergenceError(f"file_invalid:{path.name}")
    return path.read_bytes()


def candidate_env(payload: bytes, expected_image: str) -> bytes:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConvergenceError("compose_env_encoding_invalid") from error
    key = "GH_HOMEASSISTANT_IMAGE="
    lines = text.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.startswith(key)]
    if len(matches) > 1:
        raise ConvergenceError("homeassistant_env_line_count_invalid")
    if matches:
        observed = lines[matches[0]].rstrip("\r\n").split("=", 1)[1]
        if observed != expected_image:
            raise ConvergenceError("homeassistant_env_predecessor_drift")
        return payload
    ending = "" if not text or text.endswith(("\n", "\r")) else "\n"
    return payload + ending.encode() + f"{key}{expected_image}\n".encode()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def candidate_compose(payload: bytes, expected_image: str) -> bytes:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConvergenceError("compose_encoding_invalid") from error
    lines = text.splitlines(keepends=True)
    service_starts = [
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"  [A-Za-z0-9_.-]+:\s*(?:#.*)?\r?\n?", line)
    ]
    ha_starts = [
        index
        for index in service_starts
        if re.match(r"^  homeassistant:", lines[index])
    ]
    if len(ha_starts) != 1:
        raise ConvergenceError("homeassistant_service_block_invalid")
    start = ha_starts[0]
    end = len(lines)
    for index in service_starts:
        if index > start:
            end = index
            break
    for index in range(start + 1, len(lines)):
        if re.match(r"^[A-Za-z0-9_.-]+:\s*(?:#.*)?\r?\n?$", lines[index]):
            end = min(end, index)
            break

    image_indexes = [
        index
        for index in range(start + 1, end)
        if re.match(r"^    image:\s*", lines[index])
    ]
    if len(image_indexes) != 1:
        raise ConvergenceError("homeassistant_image_line_count_invalid")
    index = image_indexes[0]
    raw = lines[index]
    ending = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")
    observed = _unquote(raw.split(":", 1)[1].rstrip("\r\n"))
    if observed != expected_image:
        raise ConvergenceError("homeassistant_compose_predecessor_drift")
    lines[index] = f"    image: {DYNAMIC_HA_BINDING}{ending}"
    return "".join(lines).encode("utf-8")


def _render(compose: Path, env: Path) -> dict[str, Any]:
    result = subprocess.run(
        (
            "docker",
            "compose",
            "--project-name",
            PROJECT,
            "--env-file",
            str(env),
            "-f",
            str(compose),
            "--profile",
            "application",
            "config",
            "--format",
            "json",
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=120,
    )
    if result.returncode:
        raise ConvergenceError("compose_render_failed")
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ConvergenceError("compose_render_invalid") from error
    if not isinstance(document, dict):
        raise ConvergenceError("compose_render_shape_invalid")
    return document


def inspect(
    *,
    compose: Path,
    env: Path,
    expected_image: str,
) -> dict[str, Any]:
    if not expected_image.startswith("local/n3w-homeassistant:"):
        raise ConvergenceError("homeassistant_image_namespace_invalid")
    original_compose = _read_regular(compose)
    original_env = _read_regular(env)
    proposed_compose = candidate_compose(original_compose, expected_image)
    proposed_env = candidate_env(original_env, expected_image)

    current_render = _render(compose, env)
    with tempfile.TemporaryDirectory(prefix="n3w-ha-template-readonly-") as raw:
        root = Path(raw)
        candidate_compose_path = root / "docker-compose.yml"
        candidate_env_path = root / "docker-compose.env"
        candidate_compose_path.write_bytes(proposed_compose)
        candidate_env_path.write_bytes(proposed_env)
        candidate_render = _render(candidate_compose_path, candidate_env_path)

    if current_render != candidate_render:
        raise ConvergenceError("candidate_render_semantic_drift")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "inspect",
        "mutation": False,
        "expected_homeassistant_image": expected_image,
        "current_binding_mode": "legacy_static",
        "candidate_binding_mode": "dynamic",
        "current_compose_sha256": _sha256_bytes(original_compose),
        "current_env_sha256": _sha256_bytes(original_env),
        "candidate_compose_sha256": _sha256_bytes(proposed_compose),
        "candidate_env_sha256": _sha256_bytes(proposed_env),
        "current_render_sha256": _canonical_sha(current_render),
        "candidate_render_sha256": _canonical_sha(candidate_render),
        "render_semantically_equal": True,
        "product_path_write": False,
        "service_restart": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="n3w-t1-core-updater-ha-template-convergence"
    )
    parser.add_argument("inspect", nargs="?")
    parser.add_argument(
        "--compose",
        type=Path,
        default=DEFAULT_COMPOSE,
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=DEFAULT_ENV,
    )
    parser.add_argument("--expected-homeassistant-image", required=True)
    args = parser.parse_args()
    try:
        result = inspect(
            compose=args.compose,
            env=args.env,
            expected_image=args.expected_homeassistant_image,
        )
    except Exception as error:
        reason = str(error)
        if not reason or len(reason) > 200 or "/" in reason or "\\" in reason:
            reason = type(error).__name__
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "operation": "inspect",
                    "mutation": False,
                    "reason": reason,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
