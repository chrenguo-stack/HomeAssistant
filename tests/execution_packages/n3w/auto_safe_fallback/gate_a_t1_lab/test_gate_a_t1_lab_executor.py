from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_t1_lab/executor.py"

spec = importlib.util.spec_from_file_location("gate_a_t1_lab", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_private_bundle_binding_is_exact() -> None:
    assert module.APPLICATION_SIZE == 1140352
    assert module.APPLICATION_SHA256 == "77b0fd6a98c3e837d3543eebdd30b86354790847d0c78cdab7e96f0d7d66a8ad"
    assert module.OTADATA_SHA256 == "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
    assert module.CA_CERT_SHA256 == "66ca928aaab07eaef6aebf0a7dec9b8a0e0fac9a9d719f4e1354ea575eed0a66"
    assert module.SERVER_CERT_SHA256 == "c33bdac940da24cff4de772ff0478f0f069a3ab956dc03b1557738c4f640af4e"
    assert module.SERVER_KEY_SHA256 == "29ee45ca617fb5e4e854081e77a9ae4c468c3b07fb1d206cb0d61d86d8cbee61"
    assert module.SOURCE_HEAD == "8210cf7b53e9ec934d145f1c15e9619579c923be"
    assert module.BROKER_PORT == 18883
    assert module.TLS_SERVER_NAME == "n3w-gate-a.invalid"


def test_readonly_preflight_has_no_runtime_mutation_commands() -> None:
    source = module.REMOTE_PREFLIGHT
    forbidden = (
        "ip addr add",
        "ip addr del",
        "docker run",
        "docker rm",
        "docker restart",
        "docker compose",
        "systemctl",
        "iptables",
        "nft ",
    )
    for token in forbidden:
        assert token not in source


def test_activation_is_isolated_from_production_broker() -> None:
    source = module.REMOTE_ACTIVATE
    assert '"--network", "host"' in source
    assert '"gh.n3w.gate-a=1"' in source
    assert '"gh.n3w.gate-a.bundle=" + app_hash' in source
    assert 'port_open(18883)' in source
    assert '"ip", "addr", "add"' in source
    assert '"docker", "restart"' not in source
    assert '"docker", "compose"' not in source
    assert '"systemctl"' not in source
    assert '"iptables"' not in source
    assert '"nft"' not in source


def test_cleanup_is_bound_and_does_not_touch_production_services() -> None:
    source = module.REMOTE_CLEANUP
    assert 'labels.get("gh.n3w.gate-a") != "1"' in source
    assert 'labels.get("gh.n3w.gate-a.bundle") != app_hash' in source
    assert '"docker", "rm", "-f", container_name' in source
    assert '"ip", "addr", "del"' in source
    assert '"docker", "restart"' not in source
    assert '"docker", "compose"' not in source
    assert '"systemctl"' not in source


def test_confirmation_tokens_are_separate_and_explicit() -> None:
    assert module.ACTIVATE_CONFIRMATION == "N3W_GATE_A_T1_LAB_MUTATION_AUTHORIZED"
    assert module.CLEANUP_CONFIRMATION == "N3W_GATE_A_T1_LAB_CLEANUP_AUTHORIZED"
    assert module.ACTIVATE_CONFIRMATION != module.CLEANUP_CONFIRMATION


def test_public_console_does_not_print_private_profile_values() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    print_region = source[source.index('print("GATE_A_T1_LAB_PREFLIGHT=PASS")') :]
    assert 'print(profile["mqtt_username"])' not in print_region
    assert 'print(profile["mqtt_password"])' not in print_region
    assert 'print(profile["mqtt_client_id"])' not in print_region
    assert 'print(profile["restore_host"])' not in print_region
    assert 'print(profile["live_alias"])' not in print_region
    assert 'print(profile["blackhole_ip"])' not in print_region
