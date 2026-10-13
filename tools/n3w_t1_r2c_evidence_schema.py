from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SCHEMA = "gh.n3w.t1-r2c-readonly-evidence/1"
REQUIREMENT_IDS = tuple(f"E{i}" for i in range(1, 10))
REQUIREMENT_STATUSES = frozenset(
    {"OBSERVED", "ABSENT", "UNKNOWN", "ERROR", "NOT_EXECUTED"}
)
CAPTURE_STATUSES = frozenset({"NOT_EXECUTED", "COMPLETE", "INCOMPLETE", "FAILED"})
STATIC_REVIEW_STATUSES = frozenset(
    {"NOT_EXECUTED", "SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"}
)
PUBLIC_REVIEW_STATUSES = frozenset({"NOT_REVIEWED", "PASS", "FAIL"})
METHOD_IDS = frozenset({"R1", "R2", "R3", "C1", "C2", "C3", "C4", "C5", "C6"})
TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "execution_id",
        "source_head",
        "probe_sha256",
        "contract_sha256",
        "authorization",
        "target_binding",
        "requirements",
        "capture_status",
        "static_review_status",
        "stop_reasons",
        "boundaries",
        "os_identity_semantics_proven",
        "controlled_clone_boot_required",
        "disk_capture_ready",
        "public_projection_review",
    }
)
REQUIREMENT_ENVELOPE_KEYS = frozenset(
    {"status", "complete", "reason_code", "method_ids", "provenance", "fields"}
)
FIELD_KEYS = frozenset({"value", "status"})
AUTHORIZATION_KEYS = frozenset(
    {"grant_id", "granted", "claimed", "consumed", "replay_permitted"}
)
BOUNDARY_KEYS = frozenset(
    {
        "t1_access",
        "intentional_target_write",
        "service_mutation",
        "board_access",
        "merge",
    }
)
REQUIREMENT_FIELDS = {
    "E1": frozenset(
        {
            "os_release",
            "armbian_release",
            "architecture",
            "systemd_version",
            "package_versions",
            "executable_binding",
        }
    ),
    "E2": frozenset(
        {
            "firstrun_body_complete",
            "body_sha256",
            "identity_control_flow",
            "helper_dependencies",
            "conditions",
            "writes_declared_by_source",
        }
    ),
    "E3": frozenset(
        {
            "firstrun_config_present",
            "setting_names",
            "identity_setting_classes",
            "config_parse_complete",
            "source_references",
        }
    ),
    "E4": frozenset(
        {
            "etc_machine_id",
            "dbus_machine_id",
            "path_relation",
            "mount_relation",
            "contents_equal",
            "boot_condition_contract",
            "fallback_sources",
        }
    ),
    "E5": frozenset(
        {
            "ssh_key_metadata",
            "key_families",
            "keygen_conditions",
            "ssh_units",
            "hostkey_path_classes",
            "package_helpers",
            "socket_activation",
        }
    ),
    "E6": frozenset(
        {
            "nm_state_inventory",
            "profile_inventory",
            "netplan_inventory",
            "effective_identity_sources",
            "dhcp_identity_classes",
            "mac_identity_classes",
            "unknown_identity_state",
        }
    ),
    "E7": frozenset(
        {
            "journal_roots",
            "directory_identity_relation",
            "journal_storage_policy",
            "namespace_units",
            "journal_boot_order",
        }
    ),
    "E8": frozenset(
        {
            "seed_metadata",
            "seed_owner_unit",
            "seed_load_save_order",
            "alternate_seed_mechanisms",
            "boot_entropy_limit",
        }
    ),
    "E9": frozenset(
        {
            "unit_dependency_graph",
            "condition_evaluation",
            "activation_edges",
            "current_boot_timestamps",
            "identity_before_network",
            "identity_before_ssh",
            "unresolved_edges",
        }
    ),
}
PUBLIC_FIELD_ALLOWLIST = {
    "E1": frozenset(
        {
            "os_release",
            "armbian_release",
            "architecture",
            "systemd_version",
            "package_versions",
            "executable_binding",
        }
    ),
    "E2": frozenset(
        {
            "firstrun_body_complete",
            "body_sha256",
            "identity_control_flow",
            "conditions",
            "writes_declared_by_source",
        }
    ),
    "E3": frozenset(
        {
            "firstrun_config_present",
            "setting_names",
            "identity_setting_classes",
            "config_parse_complete",
        }
    ),
    "E4": frozenset(
        {
            "path_relation",
            "mount_relation",
            "contents_equal",
            "boot_condition_contract",
        }
    ),
    "E5": frozenset(
        {
            "ssh_key_metadata",
            "key_families",
            "keygen_conditions",
            "hostkey_path_classes",
            "socket_activation",
        }
    ),
    "E6": frozenset(
        {
            "nm_state_inventory",
            "profile_inventory",
            "netplan_inventory",
            "effective_identity_sources",
            "dhcp_identity_classes",
            "mac_identity_classes",
            "unknown_identity_state",
        }
    ),
    "E7": frozenset(
        {
            "journal_roots",
            "directory_identity_relation",
            "journal_storage_policy",
            "journal_boot_order",
        }
    ),
    "E8": frozenset(
        {
            "seed_metadata",
            "seed_owner_unit",
            "seed_load_save_order",
            "alternate_seed_mechanisms",
            "boot_entropy_limit",
        }
    ),
    "E9": frozenset(
        {
            "unit_dependency_graph",
            "condition_evaluation",
            "activation_edges",
            "identity_before_network",
            "identity_before_ssh",
            "unresolved_edges",
        }
    ),
}
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceSchemaError(RuntimeError):
    pass


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise EvidenceSchemaError(f"{label}_keys")


def _status(value: Any, allowed: frozenset[str], label: str) -> None:
    if value not in allowed:
        raise EvidenceSchemaError(label)


def _hex(value: Any, pattern: re.Pattern[str], label: str) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise EvidenceSchemaError(label)


def validate_report(report: Mapping[str, Any]) -> None:
    _exact_keys(report, TOP_LEVEL_KEYS, "top_level")
    if report["schema"] != SCHEMA:
        raise EvidenceSchemaError("schema")
    if not isinstance(report["execution_id"], str) or not report["execution_id"]:
        raise EvidenceSchemaError("execution_id")
    _hex(report["source_head"], HEX40, "source_head")
    _hex(report["probe_sha256"], HEX64, "probe_sha256")
    _hex(report["contract_sha256"], HEX64, "contract_sha256")

    authorization = report["authorization"]
    if not isinstance(authorization, Mapping):
        raise EvidenceSchemaError("authorization_type")
    _exact_keys(authorization, AUTHORIZATION_KEYS, "authorization")
    for key in ("granted", "claimed", "consumed", "replay_permitted"):
        if not isinstance(authorization[key], bool):
            raise EvidenceSchemaError(f"authorization_{key}")
    if not isinstance(authorization["grant_id"], str):
        raise EvidenceSchemaError("authorization_grant_id")

    if not isinstance(report["target_binding"], Mapping):
        raise EvidenceSchemaError("target_binding_type")

    requirements = report["requirements"]
    if not isinstance(requirements, Mapping):
        raise EvidenceSchemaError("requirements_type")
    if tuple(sorted(requirements)) != REQUIREMENT_IDS:
        raise EvidenceSchemaError("requirements_keys")
    for requirement_id in REQUIREMENT_IDS:
        envelope = requirements[requirement_id]
        if not isinstance(envelope, Mapping):
            raise EvidenceSchemaError(f"{requirement_id}_type")
        _exact_keys(envelope, REQUIREMENT_ENVELOPE_KEYS, requirement_id)
        _status(envelope["status"], REQUIREMENT_STATUSES, f"{requirement_id}_status")
        if not isinstance(envelope["complete"], bool):
            raise EvidenceSchemaError(f"{requirement_id}_complete")
        reason_code = envelope["reason_code"]
        if reason_code is not None and (
            not isinstance(reason_code, str) or not REASON_RE.fullmatch(reason_code)
        ):
            raise EvidenceSchemaError(f"{requirement_id}_reason_code")
        method_ids = envelope["method_ids"]
        if not isinstance(method_ids, list) or any(
            method not in METHOD_IDS for method in method_ids
        ):
            raise EvidenceSchemaError(f"{requirement_id}_method_ids")
        if not isinstance(envelope["provenance"], list):
            raise EvidenceSchemaError(f"{requirement_id}_provenance")
        fields = envelope["fields"]
        if not isinstance(fields, Mapping):
            raise EvidenceSchemaError(f"{requirement_id}_fields_type")
        _exact_keys(fields, REQUIREMENT_FIELDS[requirement_id], f"{requirement_id}_fields")
        for field_name, field in fields.items():
            if not isinstance(field, Mapping):
                raise EvidenceSchemaError(f"{requirement_id}_{field_name}_type")
            _exact_keys(field, FIELD_KEYS, f"{requirement_id}_{field_name}")
            _status(
                field["status"],
                REQUIREMENT_STATUSES,
                f"{requirement_id}_{field_name}_status",
            )

    _status(report["capture_status"], CAPTURE_STATUSES, "capture_status")
    _status(
        report["static_review_status"],
        STATIC_REVIEW_STATUSES,
        "static_review_status",
    )
    _status(
        report["public_projection_review"],
        PUBLIC_REVIEW_STATUSES,
        "public_projection_review",
    )
    if not isinstance(report["stop_reasons"], list) or any(
        not isinstance(reason, str) or not REASON_RE.fullmatch(reason)
        for reason in report["stop_reasons"]
    ):
        raise EvidenceSchemaError("stop_reasons")

    boundaries = report["boundaries"]
    if not isinstance(boundaries, Mapping):
        raise EvidenceSchemaError("boundaries_type")
    _exact_keys(boundaries, BOUNDARY_KEYS, "boundaries")
    if any(not isinstance(boundaries[key], bool) for key in BOUNDARY_KEYS):
        raise EvidenceSchemaError("boundaries_value")

    if report["os_identity_semantics_proven"] is not False:
        raise EvidenceSchemaError("os_identity_semantics_proven")
    if report["controlled_clone_boot_required"] is not True:
        raise EvidenceSchemaError("controlled_clone_boot_required")
    if report["disk_capture_ready"] is not False:
        raise EvidenceSchemaError("disk_capture_ready")


def public_requirement_projection(
    requirement_id: str,
    envelope: Mapping[str, Any],
) -> dict[str, Any]:
    if requirement_id not in REQUIREMENT_FIELDS:
        raise EvidenceSchemaError("unknown_requirement")
    if not isinstance(envelope, Mapping):
        raise EvidenceSchemaError("requirement_type")
    _exact_keys(envelope, REQUIREMENT_ENVELOPE_KEYS, requirement_id)
    fields = envelope["fields"]
    if not isinstance(fields, Mapping):
        raise EvidenceSchemaError("fields_type")
    _exact_keys(fields, REQUIREMENT_FIELDS[requirement_id], f"{requirement_id}_fields")
    allowed = PUBLIC_FIELD_ALLOWLIST[requirement_id]
    projected_fields = {}
    for name in sorted(allowed):
        field = fields[name]
        if not isinstance(field, Mapping):
            raise EvidenceSchemaError(f"{requirement_id}_{name}_type")
        _exact_keys(field, FIELD_KEYS, f"{requirement_id}_{name}")
        _status(field["status"], REQUIREMENT_STATUSES, f"{requirement_id}_{name}_status")
        projected_fields[name] = {"status": field["status"]}
    return {
        "status": envelope["status"],
        "complete": envelope["complete"],
        "reason_code": envelope["reason_code"],
        "method_ids": list(envelope["method_ids"]),
        "fields": projected_fields,
    }
