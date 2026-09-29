#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SOURCE_HEAD = "8210cf7b53e9ec934d145f1c15e9619579c923be"
SOURCE_TREE = "5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c"
TARGET_PATH = "firmware/esphome_rc/board_lab/n3w_auto_safe_fallback_gate_a/generic.yml"
TARGET_BLOB = "7279271d469958940c2b51aa4a80602078470891"
PATCH_PATH = "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_tls_server_name_patch.py.script"
PATCH_BLOB = "49570a83ead08158d4d99c385740fa6d646b5e3d"
EXPECTED_PREFLIGHT_SCHEMA = "n3w.auto-safe-fallback.gate-a-readonly-preflight/1"
EXPECTED_BOARD_B_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
EXPECTED_PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
ESPHOME_VERSION = "2026.4.3"
ESP_IDF_VERSION = "5.5.4"
BROKER_PORT = 18883
TLS_SERVER_NAME = "n3w-gate-a.invalid"
REPOSITORY = "https://github.com/chrenguo-stack/HomeAssistant.git"


class StopExecution(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise StopExecution(f"required local tool is unavailable: {name}")
    return resolved


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
    stdout_path: Path | None = None,
) -> str:
    target = subprocess.PIPE
    handle = None
    if stdout_path is not None:
        handle = stdout_path.open("wb")
        os.chmod(stdout_path, 0o600)
        target = handle
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=target,
            stderr=subprocess.STDOUT if handle is not None else subprocess.PIPE,
            text=False,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StopExecution(f"command timed out after {timeout}s: {Path(argv[0]).name}") from exc
    finally:
        if handle is not None:
            handle.close()
    if completed.returncode != 0:
        if stdout_path is not None:
            raise StopExecution(
                f"command failed rc={completed.returncode}; private log={stdout_path}"
            )
        raw = completed.stderr or b""
        detail = raw.decode("utf-8", errors="backslashreplace").strip()
        raise StopExecution(f"command failed rc={completed.returncode}: {detail[:600]}")
    if stdout_path is not None:
        return ""
    raw = completed.stdout or b""
    return raw.decode("utf-8", errors="strict")


def require_private_input(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise StopExecution("preflight result is missing or unsafe")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise StopExecution("preflight result must not be group/world accessible")


def load_preflight(path: Path) -> dict[str, Any]:
    require_private_input(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("preflight result is unreadable") from exc
    if doc.get("schema") != EXPECTED_PREFLIGHT_SCHEMA or doc.get("status") != "PASS":
        raise StopExecution("preflight result is not a PASS Gate A preflight")
    if doc.get("t1_mutation") is not False or doc.get("board_flash") is not False:
        raise StopExecution("preflight mutation boundary is invalid")
    board = doc.get("board")
    t1 = doc.get("t1")
    if not isinstance(board, dict) or not isinstance(t1, dict):
        raise StopExecution("preflight board/T1 binding is missing")
    if board.get("hardware_id_sha256") != EXPECTED_BOARD_B_HARDWARE_ID_SHA256:
        raise StopExecution("preflight is not bound to frozen Board B")
    if board.get("partition_table_sha256") != EXPECTED_PARTITION_TABLE_SHA256:
        raise StopExecution("preflight partition table binding drifted")
    if board.get("flash_write") is not False or board.get("persistent_mutation") is not False:
        raise StopExecution("preflight board mutation boundary drifted")
    if t1.get("wildcard_8883") is not True:
        raise StopExecution("production Broker wildcard 8883 preflight was not PASS")
    if t1.get("broker_running") is not True or t1.get("manager_running") is not True:
        raise StopExecution("production Broker/Manager continuity was not PASS")
    current_ip = t1.get("current_ip")
    live_alias = t1.get("live_alias")
    blackhole_ip = t1.get("blackhole_ip")
    prefixlen = t1.get("prefixlen")
    if not all(isinstance(value, str) and value for value in (current_ip, live_alias, blackhole_ip)):
        raise StopExecution("preflight address binding is incomplete")
    if not isinstance(prefixlen, int) or isinstance(prefixlen, bool):
        raise StopExecution("preflight prefix length is invalid")
    try:
        restore_interface = ipaddress.ip_interface(f"{current_ip}/{prefixlen}")
        live = ipaddress.ip_address(live_alias)
        blackhole = ipaddress.ip_address(blackhole_ip)
    except ValueError as exc:
        raise StopExecution("preflight contains an invalid IPv4 binding") from exc
    if restore_interface.version != 4 or live.version != 4 or blackhole.version != 4:
        raise StopExecution("Gate A requires IPv4")
    network = restore_interface.network
    if live not in network or blackhole not in network:
        raise StopExecution("Gate A candidates are not in the restore-host subnet")
    if len({str(restore_interface.ip), str(live), str(blackhole)}) != 3:
        raise StopExecution("Gate A addresses are not distinct")
    if live in (network.network_address, network.broadcast_address):
        raise StopExecution("live alias is not a usable host address")
    if blackhole in (network.network_address, network.broadcast_address):
        raise StopExecution("blackhole address is not a usable host address")
    return doc


def create_private_workspace(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == Path("/") or len(resolved.parts) < 3:
        raise StopExecution("output directory is too broad")
    if resolved.exists():
        if resolved.is_symlink() or not resolved.is_dir() or any(resolved.iterdir()):
            raise StopExecution("output directory must be absent or empty")
        os.chmod(resolved, 0o700)
    else:
        resolved.mkdir(parents=True, mode=0o700)
    if stat.S_IMODE(resolved.stat().st_mode) != 0o700:
        raise StopExecution("output directory mode must be 0700")
    return resolved


def private_write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")
    os.chmod(path, 0o600)


def private_write_json(path: Path, value: object) -> None:
    private_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def verify_git_source(source: Path) -> None:
    head = run(["git", "rev-parse", "HEAD"], cwd=source).strip()
    tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=source).strip()
    target_blob = run(["git", "hash-object", TARGET_PATH], cwd=source).strip()
    patch_blob = run(["git", "hash-object", PATCH_PATH], cwd=source).strip()
    if head != SOURCE_HEAD:
        raise StopExecution("exact source HEAD mismatch")
    if tree != SOURCE_TREE:
        raise StopExecution("exact source tree mismatch")
    if target_blob != TARGET_BLOB:
        raise StopExecution("Gate A target blob mismatch")
    if patch_blob != PATCH_BLOB:
        raise StopExecution("MQTT retarget patch blob mismatch")


def clone_exact_source(root: Path) -> Path:
    source = root / "source"
    source.mkdir(mode=0o700)
    run(["git", "init", "-q"], cwd=source)
    run(["git", "remote", "add", "origin", REPOSITORY], cwd=source)
    run(["git", "fetch", "-q", "--depth=1", "origin", SOURCE_HEAD], cwd=source, timeout=180)
    run(["git", "checkout", "-q", "--detach", "FETCH_HEAD"], cwd=source)
    verify_git_source(source)
    return source


def generate_tls(root: Path) -> dict[str, str]:
    openssl = require_tool("openssl")
    tls = root / "lab"
    tls.mkdir(mode=0o700)
    ca_key = tls / "ca.key"
    ca_cert = tls / "ca.crt"
    server_key = tls / "server.key"
    server_csr = tls / "server.csr"
    server_cert = tls / "server.crt"
    extfile = tls / "server-ext.cnf"

    run([openssl, "genrsa", "-out", str(ca_key), "2048"], timeout=60)
    run(
        [
            openssl,
            "req",
            "-x509",
            "-new",
            "-sha256",
            "-key",
            str(ca_key),
            "-subj",
            "/CN=N3W Gate A Ephemeral CA",
            "-days",
            "3",
            "-out",
            str(ca_cert),
        ],
        timeout=60,
    )
    run([openssl, "genrsa", "-out", str(server_key), "2048"], timeout=60)
    run(
        [
            openssl,
            "req",
            "-new",
            "-sha256",
            "-key",
            str(server_key),
            "-subj",
            f"/CN={TLS_SERVER_NAME}",
            "-out",
            str(server_csr),
        ],
        timeout=60,
    )
    private_write_text(
        extfile,
        "\n".join(
            (
                "[v3_server]",
                f"subjectAltName=DNS:{TLS_SERVER_NAME}",
                "basicConstraints=critical,CA:FALSE",
                "keyUsage=critical,digitalSignature,keyEncipherment",
                "extendedKeyUsage=serverAuth",
                "",
            )
        ),
    )
    run(
        [
            openssl,
            "x509",
            "-req",
            "-in",
            str(server_csr),
            "-CA",
            str(ca_cert),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-out",
            str(server_cert),
            "-days",
            "3",
            "-sha256",
            "-extfile",
            str(extfile),
            "-extensions",
            "v3_server",
        ],
        timeout=60,
    )
    for path in (ca_cert, server_key, server_cert):
        os.chmod(path, 0o600)
    for path in (ca_key, server_csr, extfile, tls / "ca.srl"):
        path.unlink(missing_ok=True)
    return {
        "ca_cert_sha256": sha256_file(ca_cert),
        "server_cert_sha256": sha256_file(server_cert),
        "server_key_sha256": sha256_file(server_key),
    }


def verify_idf_version() -> None:
    home = Path.home()
    version_file = home / ".platformio/packages/framework-espidf/tools/cmake/version.cmake"
    if not version_file.is_file():
        raise StopExecution("ESP-IDF version file is unavailable after compile")
    text = version_file.read_text(encoding="utf-8", errors="strict")
    expected = ((5, "MAJOR"), (5, "MINOR"), (4, "PATCH"))
    for value, name in expected:
        if re.search(rf"set\(IDF_VERSION_{name}\s+{value}\)", text) is None:
            raise StopExecution("ESP-IDF version is not exact 5.5.4")


def create_venv(root: Path) -> Path:
    venv = root / "venv"
    run([sys.executable, "-m", "venv", str(venv)], timeout=120)
    python = venv / "bin" / "python"
    if not python.is_file():
        raise StopExecution("private build venv was not created")
    pip_log = root / "pip-install.log"
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            f"esphome=={ESPHOME_VERSION}",
        ],
        timeout=600,
        stdout_path=pip_log,
    )
    return python


def compile_firmware(
    root: Path,
    source: Path,
    python: Path,
    preflight: dict[str, Any],
    profile: dict[str, str],
) -> dict[str, Any]:
    target_dir = source / "firmware/esphome_rc/board_lab/n3w_auto_safe_fallback_gate_a"
    ca_pem = (root / "lab/ca.crt").read_text(encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "N3W_GATE_A_LIVE_ALIAS": str(preflight["t1"]["live_alias"]),
            "N3W_GATE_A_BLACKHOLE_IP": str(preflight["t1"]["blackhole_ip"]),
            "N3W_GATE_A_RESTORE_HOST": str(preflight["t1"]["current_ip"]),
            "N3W_GATE_A_BROKER_PORT": str(BROKER_PORT),
            "N3W_GATE_A_TLS_SERVER_NAME": TLS_SERVER_NAME,
            "N3W_GATE_A_CA_PEM_ESCAPED": ca_pem.replace("\\", "\\\\").replace("\n", "\\n"),
            "N3W_GATE_A_MQTT_USERNAME": profile["mqtt_username"],
            "N3W_GATE_A_MQTT_PASSWORD": profile["mqtt_password"],
            "N3W_GATE_A_MQTT_CLIENT_ID": profile["mqtt_client_id"],
        }
    )
    config_log = root / "esphome-config.log"
    compile_log = root / "esphome-compile.log"
    run(
        [str(python), "-m", "esphome", "config", "generic.yml"],
        cwd=target_dir,
        env=env,
        timeout=180,
        stdout_path=config_log,
    )
    run(
        [str(python), "-m", "esphome", "compile", "generic.yml"],
        cwd=target_dir,
        env=env,
        timeout=1200,
        stdout_path=compile_log,
    )
    verify_idf_version()
    env_dir = (
        target_dir
        / ".esphome/build/gh-n3w-phase4-generic/.pioenvs/gh-n3w-phase4-generic"
    )
    app = env_dir / "firmware.bin"
    ota = env_dir / "ota_data_initial.bin"
    if not app.is_file() or not ota.is_file():
        raise StopExecution("exact Gate A firmware output is incomplete")
    artifact = root / "artifact"
    artifact.mkdir(mode=0o700)
    app_out = artifact / "firmware.bin"
    ota_out = artifact / "ota_data_initial.bin"
    shutil.copy2(app, app_out)
    shutil.copy2(ota, ota_out)
    os.chmod(app_out, 0o600)
    os.chmod(ota_out, 0o600)
    return {
        "application_size": app_out.stat().st_size,
        "application_sha256": sha256_file(app_out),
        "otadata_size": ota_out.stat().st_size,
        "otadata_sha256": sha256_file(ota_out),
    }


def create_lab_profile(root: Path, preflight: dict[str, Any]) -> dict[str, str]:
    profile = {
        "schema": "n3w.auto-safe-fallback.gate-a-private-lab-profile/1",
        "restore_host": str(preflight["t1"]["current_ip"]),
        "live_alias": str(preflight["t1"]["live_alias"]),
        "blackhole_ip": str(preflight["t1"]["blackhole_ip"]),
        "prefixlen": str(preflight["t1"]["prefixlen"]),
        "interface": str(preflight["t1"]["interface"]),
        "broker_port": str(BROKER_PORT),
        "tls_server_name": TLS_SERVER_NAME,
        "mqtt_username": "gate_a_" + secrets.token_hex(8),
        "mqtt_password": secrets.token_urlsafe(32),
        "mqtt_client_id": "gate-a-" + secrets.token_hex(8),
    }
    private_write_json(root / "lab/profile.json", profile)
    return profile


def build(args: argparse.Namespace) -> int:
    require_tool("git")
    preflight = load_preflight(Path(args.preflight))
    root = create_private_workspace(Path(args.output_dir))
    try:
        tls = generate_tls(root)
        profile = create_lab_profile(root, preflight)
        source = clone_exact_source(root)
        python = create_venv(root)
        firmware = compile_firmware(root, source, python, preflight, profile)
        manifest = {
            "schema": "n3w.auto-safe-fallback.gate-a-private-build/1",
            "status": "PASS",
            "source": {
                "head": SOURCE_HEAD,
                "tree": SOURCE_TREE,
                "target_path": TARGET_PATH,
                "target_blob": TARGET_BLOB,
                "patch_path": PATCH_PATH,
                "patch_blob": PATCH_BLOB,
                "esphome_version": ESPHOME_VERSION,
                "esp_idf_version": ESP_IDF_VERSION,
            },
            "board": {
                "hardware_id_sha256": EXPECTED_BOARD_B_HARDWARE_ID_SHA256,
                "partition_table_sha256": EXPECTED_PARTITION_TABLE_SHA256,
            },
            "lab": {
                "broker_port": BROKER_PORT,
                "tls_server_name": TLS_SERVER_NAME,
                **tls,
            },
            "firmware": firmware,
            "bound_preflight": {
                "schema": preflight["schema"],
                "status": preflight["status"],
                "t1_mutation": False,
                "board_flash": False,
            },
            "execution_boundary": {
                "board_access": False,
                "board_flash": False,
                "t1_mutation": False,
                "production_broker_mutation": False,
                "manager_mutation": False,
                "dynsec_mutation": False,
                "product_nvs_write": False,
            },
        }
        private_write_json(root / "manifest.json", manifest)
        shutil.rmtree(root / "source", ignore_errors=True)
        shutil.rmtree(root / "venv", ignore_errors=True)
        print("GATE_A_PRIVATE_BUILD=PASS")
        print(f"SOURCE_HEAD={SOURCE_HEAD}")
        print(f"SOURCE_TREE={SOURCE_TREE}")
        print(f"TARGET_BLOB={TARGET_BLOB}")
        print(f"PATCH_BLOB={PATCH_BLOB}")
        print(f"APPLICATION_SIZE={firmware['application_size']}")
        print(f"APPLICATION_SHA256={firmware['application_sha256']}")
        print(f"OTADATA_SIZE={firmware['otadata_size']}")
        print(f"OTADATA_SHA256={firmware['otadata_sha256']}")
        print(f"CA_CERT_SHA256={tls['ca_cert_sha256']}")
        print(f"SERVER_CERT_SHA256={tls['server_cert_sha256']}")
        print(f"SERVER_KEY_SHA256={tls['server_key_sha256']}")
        print(f"BROKER_PORT={BROKER_PORT}")
        print(f"TLS_SERVER_NAME={TLS_SERVER_NAME}")
        print("BOARD_ACCESS=false")
        print("BOARD_FLASH=false")
        print("T1_MUTATION=false")
        print("PRODUCTION_BROKER_MUTATION=false")
        print(f"PRIVATE_BUNDLE={root}")
        return 0
    except Exception:
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--preflight", required=True)
    value.add_argument("--output-dir", required=True)
    return value


def main() -> int:
    try:
        return build(parser().parse_args())
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
