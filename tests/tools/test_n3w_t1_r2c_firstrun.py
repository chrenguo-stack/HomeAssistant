from __future__ import annotations

from pathlib import Path

from n3w_t1_r2c_firstrun import (
    analyze_firstrun_config,
    analyze_firstrun_tree,
)


def _write_static_tree(root: Path) -> None:
    main = root / "usr" / "lib" / "armbian" / "armbian-firstrun"
    helper = root / "usr" / "lib" / "armbian" / "helper-identity.sh"
    config = root / "etc" / "default" / "armbian-firstrun"
    main.parent.mkdir(parents=True)
    helper.parent.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True)
    main.write_text(
        "#!/bin/sh\n"
        "source /etc/default/armbian-firstrun\n"
        'if [ "${SET_HOSTNAME}" = "yes" ]; then\n'
        '  hostnamectl set-hostname "${TARGET_HOSTNAME}"\n'
        "fi\n"
        "source /usr/lib/armbian/helper-identity.sh\n"
    )
    helper.write_text(
        'if [ "${SSH_HOST_KEY_REGENERATE}" = "yes" ]; then\n'
        "  ssh-keygen -A\n"
        "fi\n"
    )
    config.write_text(
        "SET_HOSTNAME=yes\n"
        "TARGET_HOSTNAME=custom-value\n"
        "SSH_HOST_KEY_REGENERATE=no\n"
    )


def test_analyze_firstrun_tree_closes_static_helper_set(tmp_path: Path) -> None:
    _write_static_tree(tmp_path)
    analysis = analyze_firstrun_tree(str(tmp_path))
    assert analysis["status"] == "OBSERVED"
    assert analysis["main_complete"] is True
    assert len(analysis["main_sha256"]) == 64
    assert len(analysis["files"]) == 2
    assert analysis["unresolved"] == []
    assert analysis["config_source_lines"]
    assert analysis["referenced_config_keys"] == [
        "SET_HOSTNAME",
        "SSH_HOST_KEY_REGENERATE",
        "TARGET_HOSTNAME",
    ]
    assert any(
        "hostname" in item["categories"]
        for item in analysis["identity_lines"]
    )
    assert any(
        "ssh-keygen" in item["categories"]
        for item in analysis["identity_lines"]
    )


def test_dynamic_source_is_unresolved_and_not_followed(tmp_path: Path) -> None:
    main = tmp_path / "usr" / "lib" / "armbian" / "armbian-firstrun"
    main.parent.mkdir(parents=True)
    main.write_text(
        "#!/bin/sh\n"
        'source "${HELPER_PATH}"\n'
        "hostnamectl set-hostname static-placeholder\n"
    )
    analysis = analyze_firstrun_tree(str(tmp_path))
    assert "DYNAMIC_SOURCE" in analysis["unresolved"]
    assert len(analysis["files"]) == 1


def test_config_returns_classes_without_raw_values(tmp_path: Path) -> None:
    _write_static_tree(tmp_path)
    tree = analyze_firstrun_tree(str(tmp_path))
    config = analyze_firstrun_config(
        str(tmp_path),
        tree["referenced_config_keys"],
    )
    assert config["present"] is True
    assert config["parse_complete"] is True
    assert config["classes"] == {
        "SET_HOSTNAME": "BOOLEAN",
        "SSH_HOST_KEY_REGENERATE": "BOOLEAN",
        "TARGET_HOSTNAME": "CUSTOM",
    }
    assert "custom-value" not in repr(config)


def test_dynamic_config_value_stays_unresolved(tmp_path: Path) -> None:
    _write_static_tree(tmp_path)
    config_path = tmp_path / "etc" / "default" / "armbian-firstrun"
    config_path.write_text(
        "SET_HOSTNAME=yes\n"
        "TARGET_HOSTNAME=$(hostname)\n"
        "SSH_HOST_KEY_REGENERATE=no\n"
    )
    tree = analyze_firstrun_tree(str(tmp_path))
    config = analyze_firstrun_config(
        str(tmp_path),
        tree["referenced_config_keys"],
    )
    assert config["parse_complete"] is False
    assert config["classes"]["TARGET_HOSTNAME"] == "UNKNOWN"
    assert "CONFIG_VALUE_DYNAMIC" in config["unresolved"]
