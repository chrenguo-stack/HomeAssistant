#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

PER_LISTENER_PREFIX = "per_listener_settings"
LEGACY_PLUGIN = "plugin /usr/lib/mosquitto_dynamic_security.so"
GLOBAL_PLUGIN = "global_plugin /usr/lib/mosquitto_dynamic_security.so"


class RepairError(ValueError):
    pass


def transform_config(text: str) -> str:
    lines = text.splitlines(keepends=True)
    per_listener = [line for line in lines if line.strip().startswith(PER_LISTENER_PREFIX)]
    legacy_plugin = [line for line in lines if line.strip() == LEGACY_PLUGIN]
    global_plugin = [line for line in lines if line.strip() == GLOBAL_PLUGIN]

    if len(per_listener) != 1 or per_listener[0].strip() != "per_listener_settings false":
        raise RepairError("expected exactly one 'per_listener_settings false'")
    if len(legacy_plugin) != 1:
        raise RepairError("expected exactly one legacy Dynamic Security plugin line")
    if global_plugin:
        raise RepairError("global Dynamic Security plugin is already present")

    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "per_listener_settings false":
            continue
        if stripped == LEGACY_PLUGIN:
            indent = line[: len(line) - len(line.lstrip())]
            newline = "\n" if line.endswith("\n") else ""
            out.append(f"{indent}{GLOBAL_PLUGIN}{newline}")
            continue
        out.append(line)
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.input)
    target = Path(args.output)
    if target.exists():
        raise RepairError("output already exists")

    original = source.read_text(encoding="utf-8")
    repaired = transform_config(original)
    target.write_text(repaired, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
