from __future__ import annotations

import hashlib
import posixpath
import re
from collections import deque
from typing import Any

from n3w_t1_r2c_readonly_files import inspect_metadata, read_bounded_text

FIRSTRUN_RELATIVE = "usr/lib/armbian/armbian-firstrun"
FIRSTRUN_CONFIG_RELATIVE = "etc/default/armbian-firstrun"
MAX_HELPERS = 16
MAX_HELPER_DEPTH = 4
HELPER_ROOTS = ("usr/lib/armbian/",)
IDENTITY_TOKENS = (
    "hostname",
    "machine-id",
    "machine_id",
    "ssh_host_",
    "ssh-keygen",
    "networkmanager",
    "nmcli",
    "netplan",
    "dhcp",
    "macaddress",
    "mac-address",
)
VARIABLE_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
SOURCE_RE = re.compile(r"^\s*(?:source|\.)\s+([^\s;]+)")
ASSIGNMENT_RE = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$"
)
CONTROL_RE = re.compile(r"^\s*(?:if|elif|case|while|until)\b")
WRITE_MARKERS = (
    "hostnamectl",
    "ssh-keygen",
    "systemd-machine-id-setup",
    "nmcli",
    "netplan",
    ">",
)
DYNAMIC_MARKERS = ("eval ", "eval\t", "`", "$(")
DOWNLOAD_RE = re.compile(r"(^|[;&|\s])(?:curl|wget)(?:[;&|\s]|$)")


class FirstrunAnalysisError(RuntimeError):
    pass


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FirstrunAnalysisError("STOP_SOURCE_NOT_UTF8") from error


def _normalize_reference(current_relative: str, token: str) -> str | None:
    if not token or any(marker in token for marker in ("$", "`", "$(", "~")):
        return None
    if token.startswith("/"):
        normalized = posixpath.normpath(token).lstrip("/")
    else:
        normalized = posixpath.normpath(
            posixpath.join(posixpath.dirname(current_relative), token)
        )
    if normalized in {"", "."} or normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def _identity_categories(line: str) -> list[str]:
    lowered = line.lower()
    return sorted({token for token in IDENTITY_TOKENS if token in lowered})


def _referenced_variables(line: str) -> list[str]:
    result: set[str] = set()
    for match in VARIABLE_RE.finditer(line):
        result.add(match.group(1) or match.group(2))
    return sorted(result)


def _analyze_text(relative: str, text: str) -> dict[str, Any]:
    identity_lines: list[dict[str, Any]] = []
    conditions: list[int] = []
    writes: list[dict[str, Any]] = []
    static_sources: list[dict[str, Any]] = []
    config_source_lines: list[int] = []
    referenced_config_keys: set[str] = set()
    unresolved: set[str] = set()

    for line_number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        categories = _identity_categories(stripped)
        if categories:
            identity_lines.append(
                {"line": line_number, "categories": categories}
            )
            referenced_config_keys.update(_referenced_variables(stripped))
            if CONTROL_RE.match(stripped):
                conditions.append(line_number)
            if any(marker in stripped.lower() for marker in WRITE_MARKERS):
                writes.append(
                    {"line": line_number, "categories": categories}
                )

        source_match = SOURCE_RE.match(stripped)
        if source_match:
            token = source_match.group(1).strip("'\"")
            normalized = _normalize_reference(relative, token)
            if normalized is None:
                unresolved.add("DYNAMIC_SOURCE")
            elif normalized == FIRSTRUN_CONFIG_RELATIVE:
                config_source_lines.append(line_number)
            elif any(normalized.startswith(root) for root in HELPER_ROOTS):
                static_sources.append(
                    {
                        "line": line_number,
                        "relative": normalized,
                    }
                )
            else:
                unresolved.add("STATIC_SOURCE_OUTSIDE_HELPER_ROOT")

        lowered = stripped.lower()
        if any(marker in stripped for marker in DYNAMIC_MARKERS):
            unresolved.add("DYNAMIC_EVALUATION")
        if DOWNLOAD_RE.search(lowered):
            unresolved.add("EXTERNAL_DOWNLOAD")

    return {
        "identity_lines": identity_lines,
        "conditions": sorted(set(conditions)),
        "writes": writes,
        "static_sources": static_sources,
        "config_source_lines": sorted(set(config_source_lines)),
        "referenced_config_keys": sorted(referenced_config_keys),
        "unresolved": sorted(unresolved),
    }


def analyze_firstrun_tree(root: str) -> dict[str, Any]:
    metadata = inspect_metadata(root, FIRSTRUN_RELATIVE)
    if metadata["status"] == "ABSENT":
        return {
            "status": "ABSENT",
            "main_sha256": None,
            "main_complete": False,
            "files": [],
            "identity_lines": [],
            "conditions": [],
            "writes": [],
            "helper_dependencies": [],
            "config_source_lines": [],
            "referenced_config_keys": [],
            "unresolved": ["MAIN_SOURCE_ABSENT"],
        }
    if metadata["kind"] != "regular":
        raise FirstrunAnalysisError("STOP_SOURCE_NOT_REGULAR")

    queue: deque[tuple[str, int, str]] = deque(
        [(FIRSTRUN_RELATIVE, 0, "main")]
    )
    visited: set[str] = set()
    files: list[dict[str, Any]] = []
    identity_lines: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    writes: list[dict[str, Any]] = []
    helper_dependencies: list[dict[str, Any]] = []
    config_source_lines: list[dict[str, Any]] = []
    config_keys: set[str] = set()
    unresolved: set[str] = set()
    main_sha256: str | None = None

    while queue:
        relative, depth, role = queue.popleft()
        if relative in visited:
            continue
        if depth > MAX_HELPER_DEPTH:
            unresolved.add("HELPER_DEPTH_LIMIT")
            continue
        if role == "helper" and len(visited) >= MAX_HELPERS + 1:
            unresolved.add("HELPER_COUNT_LIMIT")
            continue

        metadata = inspect_metadata(root, relative)
        if metadata["status"] == "ABSENT":
            unresolved.add("STATIC_HELPER_ABSENT")
            helper_dependencies.append(
                {
                    "role": role,
                    "path_class": "APPROVED_STATIC",
                    "present": False,
                }
            )
            continue
        if metadata["kind"] != "regular":
            unresolved.add("STATIC_HELPER_NOT_REGULAR")
            continue

        data = read_bounded_text(root, relative)
        digest = hashlib.sha256(data).hexdigest()
        if role == "main":
            main_sha256 = digest
        text = _decode(data)
        analysis = _analyze_text(relative, text)
        visited.add(relative)
        files.append(
            {
                "role": role,
                "sha256": digest,
                "depth": depth,
            }
        )
        unresolved.update(analysis["unresolved"])
        config_keys.update(analysis["referenced_config_keys"])

        for item in analysis["identity_lines"]:
            identity_lines.append(
                {
                    "file_role": role,
                    "line": item["line"],
                    "categories": item["categories"],
                }
            )
        for line_number in analysis["conditions"]:
            conditions.append(
                {"file_role": role, "line": line_number}
            )
        for item in analysis["writes"]:
            writes.append(
                {
                    "file_role": role,
                    "line": item["line"],
                    "categories": item["categories"],
                }
            )
        for line_number in analysis["config_source_lines"]:
            config_source_lines.append(
                {"file_role": role, "line": line_number}
            )
        for source in analysis["static_sources"]:
            helper_dependencies.append(
                {
                    "file_role": role,
                    "line": source["line"],
                    "path_class": "APPROVED_STATIC",
                }
            )
            queue.append((source["relative"], depth + 1, "helper"))

    return {
        "status": "OBSERVED",
        "main_sha256": main_sha256,
        "main_complete": main_sha256 is not None,
        "files": files,
        "identity_lines": identity_lines,
        "conditions": conditions,
        "writes": writes,
        "helper_dependencies": helper_dependencies,
        "config_source_lines": config_source_lines,
        "referenced_config_keys": sorted(config_keys),
        "unresolved": sorted(unresolved),
    }


def classify_config_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    lowered = value.strip().lower()
    if any(marker in value for marker in ("$(", "`")) or "$" in value:
        raise FirstrunAnalysisError("STOP_CONFIG_UNRESOLVED")
    if lowered in {"yes", "no", "true", "false", "0", "1", "on", "off"}:
        return "BOOLEAN"
    if lowered in {"", "auto", "default"}:
        return "DEFAULT"
    return "CUSTOM"


def analyze_firstrun_config(
    root: str,
    referenced_keys: list[str],
) -> dict[str, Any]:
    metadata = inspect_metadata(root, FIRSTRUN_CONFIG_RELATIVE)
    if metadata["status"] == "ABSENT":
        return {
            "present": False,
            "parse_complete": False,
            "setting_names": sorted(set(referenced_keys)),
            "classes": {
                key: "ABSENT" for key in sorted(set(referenced_keys))
            },
            "unresolved": ["CONFIG_ABSENT"],
        }
    if metadata["kind"] != "regular":
        raise FirstrunAnalysisError("STOP_CONFIG_NOT_REGULAR")

    text = _decode(read_bounded_text(root, FIRSTRUN_CONFIG_RELATIVE))
    wanted = set(referenced_keys)
    classes: dict[str, str] = {}
    unresolved: set[str] = set()

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ASSIGNMENT_RE.match(raw)
        if match is None:
            if any(key in raw for key in wanted):
                unresolved.add("REFERENCED_CONFIG_SYNTAX_UNKNOWN")
            continue
        key, raw_value = match.groups()
        if key not in wanted:
            continue
        try:
            classes[key] = classify_config_value(raw_value)
        except FirstrunAnalysisError:
            classes[key] = "UNKNOWN"
            unresolved.add("CONFIG_VALUE_DYNAMIC")

    for key in wanted:
        classes.setdefault(key, "ABSENT")

    return {
        "present": True,
        "parse_complete": not unresolved,
        "setting_names": sorted(wanted),
        "classes": {key: classes[key] for key in sorted(classes)},
        "unresolved": sorted(unresolved),
    }
