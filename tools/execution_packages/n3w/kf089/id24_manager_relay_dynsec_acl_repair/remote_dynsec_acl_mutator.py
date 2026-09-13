#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

ACL_TYPES = {
    "subscribePattern",
    "publishClientReceive",
    "unsubscribePattern",
}


def fail(reason: str, *, rc: int = 2) -> int:
    print(
        json.dumps(
            {
                "result": "STOP",
                "response_error": True,
                "reason": reason,
            },
            sort_keys=True,
        )
    )
    return rc


def required_env(name: str) -> str:
    value = os.getenv(name) or ""
    if not value:
        raise RuntimeError(f"missing_{name.lower()}")
    return value


def load_secret(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise RuntimeError("provisioning_password_file_invalid")
    value = path.read_text(encoding="utf-8").rstrip("\r\n")
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise RuntimeError("provisioning_password_invalid")
    return value


def env_contract() -> dict[str, Any]:
    host = required_env("GH_MQTT_HOST")
    port = int(required_env("GH_MQTT_PORT"))
    if not 1 <= port <= 65535:
        raise RuntimeError("mqtt_port_invalid")
    username = required_env("GH_N3W_PROVISIONING_USERNAME")
    password_file = required_env("GH_N3W_PROVISIONING_PASSWORD_FILE")
    client_id = required_env("GH_N3W_PROVISIONING_CLIENT_ID")
    tls_text = (os.getenv("GH_MQTT_TLS") or "").strip().lower()
    if tls_text not in {
        "", "0", "false", "no", "off", "1", "true", "yes", "on"
    }:
        raise RuntimeError("mqtt_tls_invalid")
    tls = tls_text in {"1", "true", "yes", "on"}
    ca_file = os.getenv("GH_MQTT_CA_FILE") or ""
    if tls and not ca_file:
        raise RuntimeError("mqtt_ca_missing")
    password = load_secret(password_file)
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "client_id": client_id,
        "tls": tls,
        "ca_file": ca_file,
    }


def execute_one(
    *,
    action: str,
    role_name: str,
    acl_type: str,
    topic: str,
) -> int:
    if action not in {"preflight", "add", "remove"}:
        return fail("action_invalid")
    if acl_type not in ACL_TYPES:
        return fail("acltype_invalid")
    if not role_name or not topic:
        return fail("target_invalid")

    try:
        config = env_contract()
        import paho.mqtt.client as mqtt
        from greenhouse_manager.runtime.dynsec_api import PahoDynsecTransport
    except Exception as exc:
        return fail(f"preflight_{type(exc).__name__}")

    if action == "preflight":
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "response_error": False,
                    "phase": "preflight",
                },
                sort_keys=True,
            )
        )
        return 0

    connected = threading.Event()
    rejected: list[str] = []
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=config["client_id"],
        protocol=mqtt.MQTTv5,
    )
    client.username_pw_set(config["username"], config["password"])
    if config["tls"]:
        client.tls_set(ca_certs=config["ca_file"])

    def on_connect(
        _client: Any,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        if getattr(reason_code, "is_failure", False):
            rejected.append(str(reason_code))
        connected.set()

    client.on_connect = on_connect

    try:
        client.connect(config["host"], config["port"], keepalive=30)
        client.loop_start()
        if not connected.wait(10.0):
            return fail("mqtt_connect_timeout")
        if rejected:
            return fail("mqtt_connect_rejected")

        transport = PahoDynsecTransport(client, timeout_s=10.0)
        client.on_message = transport.on_message
        if action == "add":
            command = {
                "command": "addRoleACL",
                "rolename": role_name,
                "acltype": acl_type,
                "topic": topic,
                "priority": 100,
                "allow": True,
            }
        else:
            command = {
                "command": "removeRoleACL",
                "rolename": role_name,
                "acltype": acl_type,
                "topic": topic,
            }

        responses = transport.execute((command,))
        if len(responses) != 1:
            return fail("dynsec_response_count_invalid")
        response = responses[0]
        if response.get("command") != command["command"]:
            return fail("dynsec_response_command_mismatch")
        if response.get("error"):
            return fail("dynsec_response_error")

        print(
            json.dumps(
                {
                    "result": "PASS",
                    "response_error": False,
                    "action": action,
                    "acltype": acl_type,
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        return fail(f"dynsec_{type(exc).__name__}")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
        try:
            client.loop_stop()
        except Exception:
            pass


def main() -> int:
    if len(sys.argv) != 5:
        return fail("argument_count_invalid")
    return execute_one(
        action=sys.argv[1],
        role_name=sys.argv[2],
        acl_type=sys.argv[3],
        topic=sys.argv[4],
    )


if __name__ == "__main__":
    raise SystemExit(main())
