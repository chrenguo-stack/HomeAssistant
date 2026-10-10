from __future__ import annotations

import json
import os

import pytest

from greenhouse_manager.ops.t1_clean_service_credential_bundle import (
    CleanServiceCredentialBundleError,
    create_clean_service_credential_bundle,
    verify_clean_service_credential_bundle,
)


def _random_source():
    values = iter(
        (
            b"a" * 32,
            b"b" * 32,
            b"c" * 32,
        )
    )

    def next_bytes(size: int) -> bytes:
        assert size == 32
        return next(values)

    return next_bytes


def test_clean_bundle_has_three_services_and_zero_nodes(
    tmp_path,
) -> None:
    root = tmp_path / "credentials"

    manifest = create_clean_service_credential_bundle(
        root,
        system_id="greenhouse",
        random_bytes=_random_source(),
    )

    assert manifest["service_count"] == 3
    assert manifest["service_names"] == [
        "manager",
        "provisioning",
        "homeassistant",
    ]
    assert manifest["node_credential_count"] == 0
    assert manifest["node_precreation_forbidden"] is True
    assert not (root / "node").exists()

    verified = verify_clean_service_credential_bundle(
        root
    )
    assert verified == manifest


def test_clean_bundle_uses_private_distinct_password_files(
    tmp_path,
) -> None:
    root = tmp_path / "credentials"

    create_clean_service_credential_bundle(
        root,
        system_id="greenhouse",
        random_bytes=_random_source(),
    )

    assert root.stat().st_mode & 0o777 == 0o700

    passwords = []
    for service in (
        "manager",
        "provisioning",
        "homeassistant",
    ):
        service_dir = root / service
        password = service_dir / "password"

        assert service_dir.stat().st_mode & 0o777 == 0o700
        assert password.stat().st_mode & 0o777 == 0o600
        passwords.append(
            password.read_text(
                encoding="utf-8"
            ).strip()
        )

    assert len(set(passwords)) == 3


def test_manager_and_provisioning_use_separate_readonly_mounts(
    tmp_path,
) -> None:
    root = tmp_path / "credentials"

    create_clean_service_credential_bundle(
        root,
        system_id="greenhouse",
        random_bytes=_random_source(),
    )

    runtime_env = (
        root / "manager/runtime.env"
    ).read_text(encoding="utf-8")
    compose = (
        root
        / "manager/compose-secret-fragment.yaml"
    ).read_text(encoding="utf-8")

    assert (
        "GH_MQTT_PASSWORD_FILE="
        "/run/secrets/gh_manager_mqtt_password"
        in runtime_env
    )
    assert (
        "GH_N3W_PROVISIONING_PASSWORD_FILE="
        "/run/secrets/"
        "gh_n3w_provisioning_mqtt_password"
        in runtime_env
    )
    assert "GH_MQTT_PASSWORD=" not in runtime_env

    assert compose.count("type: bind") == 2
    assert compose.count("read_only: true") == 2
    assert (
        "/run/secrets/gh_manager_mqtt_password"
        in compose
    )
    assert (
        "/run/secrets/"
        "gh_n3w_provisioning_mqtt_password"
        in compose
    )


def test_homeassistant_handoff_stays_nonautomatic(
    tmp_path,
) -> None:
    root = tmp_path / "credentials"

    create_clean_service_credential_bundle(
        root,
        system_id="greenhouse",
        random_bytes=_random_source(),
    )

    handoff = json.loads(
        (
            root
            / "homeassistant/mqtt-handoff.json"
        ).read_text(encoding="utf-8")
    )

    assert handoff["official_config_flow_only"] is True
    assert handoff["direct_storage_edit_forbidden"] is True
    assert handoff["automatic_apply"] is False
    assert handoff["operator_plaintext_copy_required"] is False
    assert handoff["fresh_product_consumer_verified"] is False
    assert "password" not in handoff
    assert handoff["password_file"] == (
        "homeassistant/password"
    )


def test_manifest_does_not_expose_password_values(
    tmp_path,
) -> None:
    root = tmp_path / "credentials"

    create_clean_service_credential_bundle(
        root,
        system_id="greenhouse",
        random_bytes=_random_source(),
    )

    password_values = [
        (
            root / f"{service}/password"
        ).read_text(encoding="utf-8").strip()
        for service in (
            "manager",
            "provisioning",
            "homeassistant",
        )
    ]
    manifest_text = (
        root / "manifest.json"
    ).read_text(encoding="utf-8")

    assert all(
        value not in manifest_text
        for value in password_values
    )


def test_existing_destination_is_rejected(
    tmp_path,
) -> None:
    root = tmp_path / "credentials"
    root.mkdir()

    with pytest.raises(
        CleanServiceCredentialBundleError,
        match="destination already exists",
    ):
        create_clean_service_credential_bundle(
            root,
            system_id="greenhouse",
            random_bytes=_random_source(),
        )


def test_verify_rejects_relaxed_secret_permissions(
    tmp_path,
) -> None:
    root = tmp_path / "credentials"

    create_clean_service_credential_bundle(
        root,
        system_id="greenhouse",
        random_bytes=_random_source(),
    )

    password = root / "manager/password"
    os.chmod(password, 0o640)

    with pytest.raises(
        CleanServiceCredentialBundleError,
        match="file is unsafe",
    ):
        verify_clean_service_credential_bundle(
            root
        )


def test_bundle_rejects_symlink_parent(
    tmp_path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)

    with pytest.raises(
        CleanServiceCredentialBundleError,
        match="parent is unavailable",
    ):
        create_clean_service_credential_bundle(
            alias / "credentials",
            system_id="greenhouse",
            random_bytes=_random_source(),
        )


def test_verify_rejects_manifest_file_binding_drift(
    tmp_path,
) -> None:
    root = tmp_path / "credentials"

    create_clean_service_credential_bundle(
        root,
        system_id="greenhouse",
        random_bytes=_random_source(),
    )

    identity = root / "manager/identity.json"
    identity.write_text(
        "{}\n",
        encoding="utf-8",
    )
    os.chmod(identity, 0o600)

    with pytest.raises(
        CleanServiceCredentialBundleError,
        match="manifest file binding is invalid",
    ):
        verify_clean_service_credential_bundle(
            root
        )
