"""Disposable loopback-only Mosquitto 2.1.2 regression; never uses a T1 target."""
from __future__ import annotations

import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import n3w_t1_production_v2_executor as executor

pytestmark = pytest.mark.skipif(
    os.environ.get("N3W_ISOLATED_MQTT_TEST") != "1",
    reason="requires explicitly enabled disposable Docker broker",
)
IMAGE = "eclipse-mosquitto:2.1.2-alpine@sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=60, **kwargs).stdout.strip()


@pytest.fixture
def broker(tmp_path, monkeypatch):
    tmp_path.chmod(0o755)
    assert "mosquitto version 2.1.2" in run("docker", "run", "--rm", IMAGE, "mosquitto", "-h")
    password = secrets.token_hex(24)
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-keyout", str(tmp_path / "key.pem"), "-out", str(tmp_path / "ca.pem"),
        "-subj", "/CN=armbian", "-addext", "subjectAltName=DNS:armbian")
    run("docker", "run", "--rm", "-i", "--user", "0:0", "-v", f"{tmp_path}:/work", IMAGE,
        "mosquitto_ctrl", "dynsec", "init", "/work/dynsec.json", "fixture-admin",
        input=password + "\n" + password + "\n")
    # Offline fixture identities only. Clone the generated password hash, retaining
    # the real DynSec password format and exact ClientID matching behavior.
    run("docker", "run", "--rm", "--user", "0:0", "-v", f"{tmp_path}:/work", IMAGE,
        "chmod", "666", "/work/dynsec.json")
    document = json.loads((tmp_path / "dynsec.json").read_text())
    admin = document["clients"][0]
    for name in ("fixture-manager", "fixture-ha"):
        document["clients"].append({**admin, "username": name, "clientid": name, "roles": []})
    (tmp_path / "dynsec.json").write_text(json.dumps(document))
    (tmp_path / "mosquitto.conf").write_text(
        "allow_anonymous false\n"
        "global_plugin /usr/lib/mosquitto_dynamic_security.so\n"
        "plugin_opt_config_file /work/dynsec.json\n"
        "log_dest stdout\nlog_type error\nlog_type warning\nlog_type notice\nconnection_messages true\n"
        "listener 1883\nlistener 8883\ncertfile /work/ca.pem\nkeyfile /work/key.pem\n"
    )
    (tmp_path / "key.pem").chmod(0o644)
    name = "n3w-isolated-" + secrets.token_hex(8)
    try:
        run("docker", "run", "-d", "--name", name,
            "-p", "127.0.0.1::1883", "-p", "127.0.0.1::8883",
            "-v", f"{tmp_path}:/work", IMAGE, "mosquitto", "-c", "/work/mosquitto.conf")
        ports = {port: int(run("docker", "port", name, str(port)).rsplit(":", 1)[1])
                 for port in (1883, 8883)}
        deadline = time.monotonic() + 15
        while True:
            try:
                with socket.create_connection(("127.0.0.1", ports[1883]), timeout=1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    pytest.fail("disposable broker did not become ready")
                time.sleep(0.1)
        monkeypatch.setattr(executor, "BROKER_TLS_PORT", ports[8883])
        yield name, ports, password, (tmp_path / "ca.pem").read_text()
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True, timeout=30)


def connect(broker, identity, port):
    _, ports, password, ca = broker
    stream = socket.create_connection(("127.0.0.1", ports[port]), timeout=3)
    if port == 8883:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=ca)
        stream = context.wrap_socket(stream, server_hostname="armbian")
    stream.settimeout(3)
    variable = b"\x00\x04MQTT\x05\xc2\x00\x3c\x00"
    payload = b"".join(executor._mqtt_field(value) for value in (identity, identity, password))
    stream.sendall(b"\x10" + executor._mqtt_varint(len(variable + payload)) + variable + payload)
    assert executor._recv_exact(stream, 1) == b"\x20"
    ack = executor._recv_exact(stream, executor._recv_varint(stream))
    assert ack[1] == 0
    return stream


@pytest.mark.parametrize("identity,original_port", [("fixture-manager", 8883), ("fixture-ha", 1883)])
def test_old_positive_probe_takes_over_existing_client_across_listeners(broker, identity, original_port):
    with connect(broker, identity, original_port) as original, connect(broker, identity, 8883):
        # MQTT 5 permits omission of zero property length in a short DISCONNECT.
        assert executor._recv_exact(original, 1) == b"\xe0"
        size = executor._recv_varint(original)
        assert executor._recv_exact(original, size) in {b"\x8e", b"\x8e\x00"}


def test_new_external_probes_leave_both_runtime_connections_alive(broker):
    name, _, _, ca = broker
    adapter = object.__new__(executor.LiveProductionAdapter)
    adapter.host, adapter._ca_pem = "127.0.0.1", ca
    with connect(broker, "fixture-manager", 8883) as manager, connect(broker, "fixture-ha", 1883) as ha:
        before = run("docker", "logs", name)
        for _ in range(3):
            for probe in ("TCP_8883", "TLS_CA", "TLS_HOSTNAME_SNI", "INVALID_CREDENTIAL_REJECTED"):
                assert adapter.external_probe(probe)["accepted"] is True
            for stream in (manager, ha):
                stream.sendall(b"\xc0\x00")
                assert executor._recv_exact(stream, 2) == b"\xd0\x00"
        after = run("docker", "logs", name)
        for identity in ("fixture-manager", "fixture-ha"):
            assert after.count(" as " + identity + " (") == before.count(" as " + identity + " (") == 1
            assert "Client " + identity + " disconnected" not in after
        # Correct password + wrong ClientID is still refused by the real DynSec plugin.
        assert executor._mqtt_rejection_reason(
            "127.0.0.1", ca_pem=ca, username="fixture-manager",
            password=broker[2], client_id="fixture-manager-wrong",
        ) in {0x86, 0x87}
