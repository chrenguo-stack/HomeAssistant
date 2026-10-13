from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_os_identity_readonly_probe.py"


def load_tool():
    name = "n3w_t1_os_identity_readonly_probe"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def write(root: Path, relative: str, content: str, mode: int = 0o644) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return path


def test_probe_collects_public_safe_identity_evidence(tmp_path: Path) -> None:
    tool = load_tool()
    write(
        tmp_path,
        "etc/os-release",
        'ID=ubuntu\nVERSION_ID="24.04"\nVERSION_CODENAME=noble\n',
    )
    write(
        tmp_path,
        "etc/armbian-release",
        "BOARD=example\nVERSION=25.8\nARCH=arm64\n",
    )
    write(tmp_path, "etc/hostname", "armbian\n")
    write(tmp_path, "etc/machine-id", "a" * 32 + "\n")
    write(tmp_path, "var/lib/dbus/machine-id", "a" * 32 + "\n")

    public_blob = base64.b64encode(b"public-key-blob").decode()
    write(
        tmp_path,
        "etc/ssh/ssh_host_ed25519_key.pub",
        f"ssh-ed25519 {public_blob} host\n",
    )
    write(
        tmp_path,
        "etc/ssh/ssh_host_ed25519_key",
        "PRIVATE-KEY-MATERIAL\n",
        0o600,
    )
    write(
        tmp_path,
        "etc/NetworkManager/system-connections/wired.nmconnection",
        "[connection]\n"
        "id=Customer LAN\n"
        "uuid=11111111-2222-3333-4444-555555555555\n"
        "type=ethernet\n"
        "[ethernet]\n"
        "cloned-mac-address=permanent\n"
        "[wifi-security]\n"
        "psk=TOP-SECRET\n",
        0o600,
    )
    write(
        tmp_path,
        "usr/lib/systemd/system/systemd-machine-id-commit.service",
        "[Unit]\nConditionPathIsMountPoint=/etc/machine-id\n"
        "[Service]\nExecStart=systemd-machine-id-setup --commit\n",
    )

    report = tool.collect(tmp_path)
    encoded = json.dumps(report, sort_keys=True)

    assert report["status"] == "PASS"
    assert report["os_release"]["ID"] == "ubuntu"
    assert report["armbian_release"]["ARCH"] == "arm64"
    assert report["hostname"] == "armbian"
    assert report["machine_identity"]["etc/machine-id"]["valid_hex32"] is True
    assert report["secret_values_included"] is False
    assert report["mutation"] is False
    assert report["os_identity_semantics_proven"] is False
    assert report["controlled_clone_boot_evidence_required"] is True
    assert "PRIVATE-KEY-MATERIAL" not in encoded
    assert "TOP-SECRET" not in encoded
    assert "Customer LAN" not in encoded
    assert (
        report["networkmanager_profiles"][0]["selected_identity_fields"][
            "connection.uuid"
        ]
        == "11111111-2222-3333-4444-555555555555"
    )
    public = next(
        item
        for item in report["ssh_host_keys"]
        if item["material"] == "public"
    )
    assert public["public_key_parse"] == "PASS"
    assert public["fingerprint_sha256"].startswith("SHA256:")


def test_probe_records_machine_id_symlink_without_following(tmp_path: Path) -> None:
    tool = load_tool()
    target = write(tmp_path, "run/machine-id", "b" * 32 + "\n")
    path = tmp_path / "etc/machine-id"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)

    report = tool.collect(tmp_path)
    record = report["machine_identity"]["etc/machine-id"]

    assert record["kind"] == "symlink"
    assert "content_sha256" not in record
    assert record["symlink_target"] == str(target)


def test_probe_never_reports_networkmanager_secrets(tmp_path: Path) -> None:
    tool = load_tool()
    write(
        tmp_path,
        "etc/NetworkManager/system-connections/wifi.nmconnection",
        "[connection]\n"
        "id=Private SSID\n"
        "uuid=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n"
        "type=wifi\n"
        "[802-11-wireless]\n"
        "ssid=Private SSID\n"
        "[wifi-security]\n"
        "psk=DO-NOT-LEAK\n",
        0o600,
    )

    report = tool.collect(tmp_path)
    encoded = json.dumps(report, sort_keys=True)

    assert "DO-NOT-LEAK" not in encoded
    assert "Private SSID" not in encoded
    assert report["networkmanager_profiles"][0]["secret_values_included"] is False
