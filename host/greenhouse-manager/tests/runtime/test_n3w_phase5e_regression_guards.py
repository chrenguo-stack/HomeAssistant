from __future__ import annotations

import ast
from pathlib import Path

import pytest

from greenhouse_manager.ops.registration_cli import _parser

MANAGER_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ROOT = MANAGER_ROOT / "src" / "greenhouse_manager" / "runtime"
OPS_ROOT = MANAGER_ROOT / "src" / "greenhouse_manager" / "ops"


RETIRED_CANONICAL_RUNTIME_FILES = {
    "n3w_path_lease.py",
    "n3w_ingress_router.py",
    "n3w_runtime_wiring.py",
    "n3w_product_pairing.py",
    "n3w_product_peer_authorization.py",
    "n3w_product_manager_adapter.py",
    "n3w_product_mqtt_service.py",
    "n3w_product_isolated_app.py",
    "n3w_product_isolated_launcher.py",
    "n3w_product_isolated_manager.py",
    "n3w_product_isolated_mqtt_service.py",
    "n3w_relay_authorization.py",
}

CURRENT_RUNTIME_FILES = {
    "n3w_auto_node_id.py",
    "n3w_canonical_ingress.py",
    "n3w_compact_relay.py",
    "n3w_credential_contract.py",
    "n3w_long_lived_peer_trust.py",
    "n3w_manager_runtime_wiring.py",
    "n3w_multi_ingress_router.py",
    "n3w_peer_trust_store.py",
    "n3w_simplified_isolated_mqtt_service.py",
}

HISTORICAL_RUNTIME_FILES = {
    "n3w_path_lease_legacy.py",
    "n3w_relay_ingress_legacy.py",
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_retired_manager_authority_is_absent_from_canonical_runtime() -> None:
    present = {path.name for path in RUNTIME_ROOT.glob("*.py")}
    assert RETIRED_CANONICAL_RUNTIME_FILES.isdisjoint(present)
    assert not (OPS_ROOT / "n3w_relay_authorization_admin.py").exists()


def test_current_simplified_runtime_entrypoints_remain_present() -> None:
    present = {path.name for path in RUNTIME_ROOT.glob("*.py")}
    assert present >= CURRENT_RUNTIME_FILES


def test_only_explicit_historical_runtime_modules_use_legacy_names() -> None:
    present_legacy = {path.name for path in RUNTIME_ROOT.glob("n3w_*_legacy.py")}
    assert present_legacy == HISTORICAL_RUNTIME_FILES


def test_active_runtime_never_imports_historical_legacy_modules() -> None:
    offenders: dict[str, list[str]] = {}
    for path in sorted(RUNTIME_ROOT.glob("n3w_*.py")):
        if path.name.endswith("_legacy.py"):
            continue
        legacy_imports = sorted(
            module
            for module in _imported_modules(path)
            if module.rsplit(".", 1)[-1].endswith("_legacy")
        )
        if legacy_imports:
            offenders[path.name] = legacy_imports
    assert offenders == {}


def test_registration_approve_uses_manager_assigned_node_id() -> None:
    parser = _parser()
    args = parser.parse_args(
        ["approve", "hardware-1", "pairing-1", "--logical-location-id", "bed-1"]
    )
    assert args.command == "approve"
    assert not hasattr(args, "node_id")

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "approve",
                "hardware-1",
                "pairing-1",
                "--logical-location-id",
                "bed-1",
                "--node-id",
                "operator-choice",
            ]
        )


def test_normal_rc2_does_not_select_retired_product_runtime() -> None:
    rc2 = (
        REPO_ROOT / "firmware" / "esphome_rc" / "f1_0_rc2" / "f1_0_rc2.yml"
    ).read_text(encoding="utf-8")
    assert "greenhouse_n3w_product_core" not in rc2
    assert "greenhouse_n3w_product_runtime" not in rc2
    assert "GREENHOUSE_N3W_ENABLE_LEGACY_RADIO" not in rc2


def test_legacy_radio_is_explicit_opt_in_only() -> None:
    radio_header = (
        REPO_ROOT
        / "firmware"
        / "esphome_rc"
        / "components"
        / "greenhouse_n3w_core"
        / "n3w_radio.h"
    ).read_text(encoding="utf-8")
    assert "#ifdef GREENHOUSE_N3W_ENABLE_LEGACY_RADIO" in radio_header
    assert '#include "n3w_radio_legacy.h"' in radio_header
