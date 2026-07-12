from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
    BrokerIdentityActivationHandoffError,
    Runner,
    Verifier,
    read_json,
    require_success,
    runtime_healthy,
    runtime_summary,
    validated_handoff,
)
from .t1_broker_identity_activation_handoff import (
    verify_broker_identity_activation_handoff,
)
from .t1_shadow import SubprocessRunner

SCHEMA = "gh.m2.t1-broker-identity-postactivation-audit/1"
_CONTROL = "$CONTROL/dynamic-security/v1"
_RESPONSE = "$CONTROL/dynamic-security/v1/response"
_LIST_CLIENTS = '{"commands":[{"command":"listClients"}]}'


def _live_security(runner: Runner) -> tuple[bool, bool, str, str]:
    config = require_success(
        runner,
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "test -r /mosquitto/config/mosquitto.conf && cat /mosquitto/config/mosquitto.conf",
        ),
        "live mosquitto.conf cannot be read",
    )
    lines = [
        line.strip() for line in config.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    anonymous = any(
        line.lower()
        in {
            "allow_anonymous true",
            "allow_anonymous yes",
            "allow_anonymous 1",
            "allow_anonymous on",
        }
        for line in lines
    )
    plugin = any(
        line.startswith(("plugin ", "global_plugin ")) and "dynamic_security" in line for line in lines
    )
    mode = require_success(
        runner,
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "test -s /mosquitto/data/dynamic-security.json && "
            "stat -c '%a' /mosquitto/data/dynamic-security.json",
        ),
        "Dynamic Security state is missing",
    ).strip()
    return anonymous, plugin, mode, hashlib.sha256(config.encode()).hexdigest()


def _anonymous_retained(runner: Runner, topic: str) -> bool:
    code, output = runner.run(
        (
            "docker",
            "exec",
            "mosquitto",
            "mosquitto_sub",
            "-h",
            "127.0.0.1",
            "-V",
            "5",
            "-C",
            "1",
            "-W",
            "5",
            "-F",
            "%p",
            "-t",
            topic,
        )
    )
    return code == 0 and bool(output.strip())


def _temporary_client(
    runner: Runner,
    config: str,
    program: str,
    arguments: Sequence[str],
) -> tuple[int, str]:
    script = (
        "umask 077; f=/tmp/gh-m2-postcheck-$$.conf; "
        "trap 'rm -f \"$f\"' EXIT; cat > \"$f\"; "
        f"{program} -o \"$f\" \"$@\""
    )
    return runner.run(
        ("docker", "exec", "-i", "mosquitto", "sh", "-c", script, "sh", *arguments),
        input_text=config,
    )


def _ha_config(update: dict[str, Any], client_id: str | None = None) -> str:
    username = update.get("username")
    password = update.get("password")
    required_id = update.get("required_client_id")
    if not all(isinstance(value, str) and value for value in (username, password, required_id)):
        raise BrokerIdentityActivationCheckError("staged Home Assistant identity is incomplete")
    selected = client_id or str(required_id)
    return f"-h 127.0.0.1\n-u {username}\n-P {password}\n-i {selected}\n-V 5\n"


def _identity_retained(runner: Runner, config: str, topic: str) -> bool:
    code, output = _temporary_client(
        runner,
        config,
        "mosquitto_sub",
        ("-C", "1", "-W", "5", "-F", "%p", "-t", topic),
    )
    return code == 0 and bool(output.strip())


def _list_clients(runner: Runner, config: str) -> bool:
    code, output = _temporary_client(
        runner,
        config,
        "mosquitto_rr",
        (
            "-q",
            "1",
            "-W",
            "5",
            "-t",
            _CONTROL,
            "-e",
            _RESPONSE,
            "-m",
            _LIST_CLIENTS,
        ),
    )
    if code != 0:
        return False
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return False
    responses = value.get("responses") if isinstance(value, dict) else None
    return bool(
        isinstance(responses, list)
        and responses
        and isinstance(responses[0], dict)
        and responses[0].get("command") == "listClients"
        and not responses[0].get("error")
    )


def _anonymous_control_denied(runner: Runner) -> bool:
    code, _output = runner.run(
        (
            "docker",
            "exec",
            "mosquitto",
            "mosquitto_rr",
            "-h",
            "127.0.0.1",
            "-V",
            "5",
            "-q",
            "1",
            "-W",
            "2",
            "-t",
            _CONTROL,
            "-e",
            _RESPONSE,
            "-m",
            _LIST_CLIENTS,
        )
    )
    return code != 0


def audit_broker_identity_postactivation(
    handoff_directory: str | Path,
    *,
    expected_retained_topic: str,
    runner: Runner | None = None,
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    root = Path(handoff_directory).expanduser().resolve()
    manifest, _plan = validated_handoff(root, handoff_verifier)
    update = read_json(
        root / "material/homeassistant/mqtt-update.json",
        "Home Assistant identity material",
    )
    provisioning = (root / "material/provisioning/mosquitto-client.conf").read_text(encoding="utf-8")
    bootstrap = (root / "material/bootstrap/admin-client.conf").read_text(encoding="utf-8")
    runtime = runtime_summary(command_runner)
    anonymous, plugin, mode, post_sha = _live_security(command_runner)
    stage = manifest.get("stage")
    baseline_sha = stage.get("broker_config_sha256") if isinstance(stage, dict) else None
    correct = _ha_config(update)
    wrong = _ha_config(update, f"{update['required_client_id']}-wrong")
    checks = {
        "services_running_zero_restart": runtime_healthy(runtime),
        "broker_config_changed_from_baseline": post_sha != baseline_sha,
        "dynamic_security_plugin_configured": plugin,
        "dynamic_security_state_present_private": mode == "600",
        "anonymous_compatibility_enabled": anonymous,
        "anonymous_retained_state_readable": _anonymous_retained(command_runner, expected_retained_topic),
        "homeassistant_identity_retained_state_readable": _identity_retained(
            command_runner, correct, expected_retained_topic
        ),
        "homeassistant_wrong_client_id_rejected": not _identity_retained(
            command_runner, wrong, expected_retained_topic
        ),
        "provisioning_control_readable": _list_clients(command_runner, provisioning),
        "bootstrap_admin_rejected": not _list_clients(command_runner, bootstrap),
        "anonymous_control_denied": _anonymous_control_denied(command_runner),
    }
    verified = all(checks.values())
    return {
        "schema": SCHEMA,
        "read_only": True,
        "checks": checks,
        "activation_verified": verified,
        "rollback_required": not verified,
        "postactivation_config_sha256": post_sha,
        "runtime": runtime,
        "broker_identity_activated": verified,
        "ready_for_homeassistant_reconfigure_handoff": verified,
        "operator_action_authorized": False,
        "ready_for_live_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "current_services_modified": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Run a read-only Broker identity postactivation audit.")
    parser.add_argument("handoff_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_broker_identity_postactivation(
            args.handoff_directory,
            expected_retained_topic=args.expected_retained_topic,
            runner=runner,
        )
    except (
        BrokerIdentityActivationCheckError,
        BrokerIdentityActivationHandoffError,
        OSError,
        ValueError,
    ) as error:
        print(f"T1 Broker identity postactivation audit failed: {error}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if report["activation_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
