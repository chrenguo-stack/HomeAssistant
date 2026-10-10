from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[2]
    / "infra/n3w-t1/broker/mosquitto.conf"
)


def _directives() -> list[str]:
    lines = [
        line.strip()
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert all("\x00" not in line for line in lines)
    return lines


def test_production_listener_and_global_dynsec_are_exact() -> None:
    lines = _directives()
    assert [x for x in lines if x.startswith("listener ")] == [
        "listener 8883 0.0.0.0"
    ]
    assert [x for x in lines if x.startswith("allow_anonymous ")] == [
        "allow_anonymous false"
    ]
    assert [x for x in lines if x.startswith("global_plugin ")] == [
        "global_plugin /usr/lib/mosquitto_dynamic_security.so"
    ]
    assert [x for x in lines if x.startswith("plugin_opt_config_file ")] == [
        "plugin_opt_config_file /mosquitto/data/dynamic-security.json"
    ]
    assert not any(
        x.startswith(("per_listener_settings ", "plugin ", "auth_plugin "))
        for x in lines
    )


def test_tls_uses_fixed_readonly_bind_targets() -> None:
    lines = _directives()
    assert [x for x in lines if x.startswith("cafile ")] == [
        "cafile /mosquitto/config/n3w-ca.pem"
    ]
    assert [x for x in lines if x.startswith("certfile ")] == [
        "certfile /mosquitto/config/n3w-server.pem"
    ]
    assert [x for x in lines if x.startswith("keyfile ")] == [
        "keyfile /mosquitto/config/n3w-server.key"
    ]
    assert [x for x in lines if x.startswith("tls_version ")] == [
        "tls_version tlsv1.2"
    ]
    assert not any("ca-key.pem" in x for x in lines)


def test_persistence_and_logs_are_explicit() -> None:
    lines = _directives()
    assert [x for x in lines if x.startswith("persistence ")] == [
        "persistence true"
    ]
    assert [x for x in lines if x.startswith("persistence_location ")] == [
        "persistence_location /mosquitto/data/"
    ]
    assert lines.count("log_dest stdout") == 1
    assert lines.count("connection_messages true") == 1
    assert not any(
        "password " in x.lower() or "secret " in x.lower()
        for x in lines
    )
