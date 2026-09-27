from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/n3w_mosquitto_21_deprecation_repair.py"
SPEC = importlib.util.spec_from_file_location("n3w_mosquitto_21_deprecation_repair", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_transform_preserves_global_security_semantics() -> None:
    source = (
        "per_listener_settings false\n"
        "listener 8883 0.0.0.0\n"
        "allow_anonymous false\n"
        "cafile /mosquitto/tls/ca.pem\n"
        "certfile /mosquitto/tls/server.pem\n"
        "keyfile /mosquitto/tls/server.key\n"
        "plugin /usr/lib/mosquitto_dynamic_security.so\n"
    )

    repaired = MODULE.transform_config(source)

    assert "per_listener_settings" not in repaired
    assert "global_plugin /usr/lib/mosquitto_dynamic_security.so" in repaired
    assert "plugin /usr/lib/mosquitto_dynamic_security.so" not in repaired.splitlines()
    assert "allow_anonymous false" in repaired
    assert "listener 8883 0.0.0.0" in repaired
    assert "cafile /mosquitto/tls/ca.pem" in repaired
    assert "certfile /mosquitto/tls/server.pem" in repaired
    assert "keyfile /mosquitto/tls/server.key" in repaired


def test_transform_rejects_per_listener_true() -> None:
    source = (
        "per_listener_settings true\n"
        "listener 8883 0.0.0.0\n"
        "plugin /usr/lib/mosquitto_dynamic_security.so\n"
    )

    try:
        MODULE.transform_config(source)
    except MODULE.RepairError as exc:
        assert "per_listener_settings false" in str(exc)
    else:
        raise AssertionError("expected RepairError")


def test_transform_rejects_ambiguous_plugin_state() -> None:
    source = (
        "per_listener_settings false\n"
        "plugin /usr/lib/mosquitto_dynamic_security.so\n"
        "global_plugin /usr/lib/mosquitto_dynamic_security.so\n"
    )

    try:
        MODULE.transform_config(source)
    except MODULE.RepairError as exc:
        assert "already present" in str(exc)
    else:
        raise AssertionError("expected RepairError")
