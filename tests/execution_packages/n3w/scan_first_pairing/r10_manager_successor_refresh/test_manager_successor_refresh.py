from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
BUILDER_PATH = (
    ROOT
    / "tools/execution_packages/n3w/scan_first_pairing/"
    "r10_manager_successor_refresh/package_builder.py"
)
EXECUTOR_PATH = (
    ROOT
    / "tools/execution_packages/n3w/scan_first_pairing/"
    "r10_manager_successor_refresh/live_refresh.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load_module("r10_manager_refresh_builder", BUILDER_PATH)
executor = load_module("r10_manager_refresh_executor", EXECUTOR_PATH)


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(payload))


def manager_archive(tmp_path: Path) -> Path:
    config_document = {
        "architecture": "arm64",
        "os": "linux",
        "config": {
            "Entrypoint": ["greenhouse-manager"],
            "Cmd": [],
            "User": "greenhouse",
            "Env": ["PYTHONUNBUFFERED=1"],
            "WorkingDir": "/app",
            "Labels": {},
            "Healthcheck": {},
            "StopSignal": "",
            "Volumes": {},
            "ExposedPorts": {},
        },
        "rootfs": {
            "type": "layers",
            "diff_ids": [
                "sha256:" + "a" * 64,
                "sha256:" + "b" * 64,
            ],
        },
    }
    config = json.dumps(
        config_document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    config_hex = hashlib.sha256(config).hexdigest()
    oci_manifest = b'{"schemaVersion":2,"config":{"digest":"sha256:' + (
        config_hex.encode()
    ) + b'"}}'
    manifest_hex = hashlib.sha256(oci_manifest).hexdigest()

    docker_manifest = json.dumps(
        [
            {
                "Config": f"blobs/sha256/{config_hex}",
                "RepoTags": [builder.TARGET_MANAGER_IMAGE],
                "Layers": [],
            }
        ],
        separators=(",", ":"),
    ).encode()
    index = json.dumps(
        {
            "schemaVersion": 2,
            "manifests": [{"digest": f"sha256:{manifest_hex}"}],
        },
        separators=(",", ":"),
    ).encode()

    target = tmp_path / "manager.tar"
    with tarfile.open(target, "w") as archive:
        add_bytes(archive, "manifest.json", docker_manifest)
        add_bytes(archive, "index.json", index)
        add_bytes(archive, f"blobs/sha256/{config_hex}", config)
        add_bytes(
            archive,
            f"blobs/sha256/{manifest_hex}",
            oci_manifest,
        )
    return target


def build_package(tmp_path: Path) -> tuple[Path, dict]:
    manager = manager_archive(tmp_path)
    distributions = tmp_path / "distributions.json"
    distributions.write_text(
        json.dumps(
            [
                {"name": "greenhouse-manager", "version": "0.4.99"},
                {"name": "zeroconf", "version": "0.148.0"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "package"
    args = argparse.Namespace(
        output=str(output),
        package_head="a" * 40,
        predecessor_source=builder.PREDECESSOR_SOURCE,
        target_source=builder.TARGET_SOURCE,
        target_tree=builder.TARGET_TREE,
        manager_tar=str(manager),
        manager_image=builder.TARGET_MANAGER_IMAGE,
        manager_image_id="sha256:" + "1" * 64,
        manager_image_size_bytes=123456,
        base_image_ref=builder.BASE_IMAGE_REF,
        base_arm64_digest="sha256:" + "2" * 64,
        base_image_id="sha256:" + "3" * 64,
        python_distributions=str(distributions),
        executor=str(EXECUTOR_PATH),
        candidate_ttl_seconds=60,
    )
    document = builder.build(args)
    return output, document


def function_block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_builder_freezes_integrated_product_authority_and_ttl_transition(
    tmp_path: Path,
) -> None:
    output, document = build_package(tmp_path)
    verified = builder.verify(output)

    assert verified == document
    assert document["product_authority"] == {
        "predecessor_source": builder.PREDECESSOR_SOURCE,
        "target_source": "ff750b3801a282af1667b5fa63481e2333e301b3",
        "target_tree": "ee6ee5e362628fa725d57fbdf50c6608e9032b17",
        "manager_discovery_blob": (
            "ac6e3f70879f980ee9a2d37938879dc6345a511e"
        ),
        "dockerfile_blob": "6486ff5fbcc23536676a48f36d67e4e0d364900a",
        "compose_blob": "c9038251d9ba1b05a472edda14b287470690815a",
        "predecessor_candidate_ttl_seconds": 30,
        "candidate_ttl_seconds": 60,
    }
    assert document["predecessor_manager_image"].endswith("e299c937a7b8")
    assert document["target_manager_image"].endswith("ff750b3801a2")


def test_package_contains_only_manager_refresh_material(tmp_path: Path) -> None:
    output, document = build_package(tmp_path)
    assert {
        path.name
        for path in output.iterdir()
        if path.is_file()
    } == {
        "manifest.json",
        "greenhouse-manager-arm64.tar",
        "refresh-executor.py",
        "manager-python-distributions.json",
    }
    policy = document["policy"]
    assert policy["secret_values_included"] is False
    assert policy["broker_image_included"] is False
    assert policy["homeassistant_image_included"] is False
    assert policy["registration_tls_included"] is False
    assert policy["compose_file_included"] is False
    assert policy["live_authorization_granted"] is False
    assert policy["old_candidate_upgrade_authorization_reusable"] is False


def test_package_verifier_rejects_extra_file(tmp_path: Path) -> None:
    output, _document = build_package(tmp_path)
    (output / "unexpected").write_text("drift\n", encoding="utf-8")
    with pytest.raises(builder.PackageError, match="package_file_set_invalid"):
        builder.verify(output)


def test_executor_is_bound_to_new_one_shot_authorization_namespace() -> None:
    assert executor.AUTHORIZATION_PATTERN.fullmatch(
        "N3W_R10_MANAGER_SUCCESSOR_REFRESH_20261029_01"
    )
    assert not executor.AUTHORIZATION_PATTERN.fullmatch(
        "N3W_R10_MANAGER_SUCCESSOR_REFRESH_TEST"
    )
    assert not executor.AUTHORIZATION_PATTERN.fullmatch(
        "N3W_R10_T1_CANDIDATE_UPGRADE_20261028_01"
    )
    assert executor.TRANSACTION.name == (
        "R10_MANAGER_SUCCESSOR_REFRESH_TRANSACTION.json"
    )


def test_preflight_is_read_only_by_source_contract() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    block = function_block(
        source,
        "def public_preflight(",
        "def parser()",
    )
    assert "validate_package(" in block
    assert "verify_prestate(" in block
    for forbidden in (
        "atomic_write",
        "systemctl\", \"stop",
        "systemctl\", \"start",
        "docker\", \"load",
        "claim_refresh(",
    ):
        assert forbidden not in block


def test_claim_happens_before_workspace_image_load_and_service_stop() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    block = function_block(
        source,
        "def execute_apply(",
        "def public_preflight(",
    )
    claim = block.index("claim_refresh(")
    workspace = block.index("create_workspace(")
    image = block.index("load_target_manager(")
    stop = block.index('run(("systemctl", "stop", SERVICES_UNIT)')
    env_write = block.index("atomic_write_bytes(\n            COMPOSE_ENV")
    assert claim < workspace < image < stop < env_write


def test_executor_does_not_regenerate_tls_or_rewrite_f4_or_compose_file() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert "generate_registration_tls" not in source
    assert "install_registration_tls" not in source
    assert "write_f4_successor" not in source
    assert "atomic_write_json(F4_TRANSACTION" not in source
    assert "atomic_write_bytes(\n            F4_TRANSACTION" not in source
    assert "atomic_write_json(PREDECESSOR_UPGRADE_TRANSACTION" not in source
    assert (
        "atomic_write_bytes(\n            PREDECESSOR_UPGRADE_TRANSACTION"
        not in source
    )
    assert "docker compose down" not in source
    assert "--force-recreate" not in source
    assert "atomic_write_bytes(\n            REGISTRATION_CERT" not in source
    assert "atomic_write_bytes(\n            REGISTRATION_KEY" not in source
    assert "atomic_write_bytes(\n            BROKER_DYNSEC" not in source
    assert "atomic_write_bytes(\n            COMPOSE_FILE" not in source


def test_only_manager_image_line_changes_in_compose_env() -> None:
    lines = [
        "GH_SYSTEM_ID=ghs_test",
        "GH_MANAGER_IMAGE=" + executor.PREDECESSOR_MANAGER_IMAGE,
        "GH_MQTT_USERNAME=manager",
    ]
    payload = executor.manager_env_payload(
        lines,
        executor.PREDECESSOR_MANAGER_IMAGE,
        executor.TARGET_MANAGER_IMAGE,
    ).decode()
    assert payload.splitlines() == [
        "GH_SYSTEM_ID=ghs_test",
        "GH_MANAGER_IMAGE=" + executor.TARGET_MANAGER_IMAGE,
        "GH_MQTT_USERNAME=manager",
    ]


def test_runtime_image_binding_accepts_cross_store_runtime_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layers = [
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
    ]
    config = {
        "Entrypoint": ["greenhouse-manager"],
        "Cmd": [],
        "User": "greenhouse",
        "Env": ["PYTHONUNBUFFERED=1"],
        "WorkingDir": "/app",
        "Labels": {},
        "Healthcheck": {},
        "StopSignal": "",
        "Volumes": {},
        "ExposedPorts": {},
    }
    runtime_id = "sha256:" + "c" * 64
    manifest = {
        "manager": {
            "rootfs_layers_sha256": executor.canonical_sha256(layers),
            "config_contract_sha256": executor.canonical_sha256(
                executor.image_config_contract(config)
            ),
        }
    }

    def fake_run(_argv, **_kwargs):
        return json.dumps(
            [
                {
                    "Id": runtime_id,
                    "Architecture": "arm64",
                    "Os": "linux",
                    "RootFS": {"Layers": layers},
                    "Config": config,
                }
            ]
        )

    monkeypatch.setattr(executor, "run", fake_run)
    binding = executor.runtime_image_binding(manifest)
    assert binding["runtime_id"] == runtime_id
    assert binding["rootfs_layers_sha256"] == manifest["manager"][
        "rootfs_layers_sha256"
    ]


def test_runtime_image_binding_rejects_rootfs_or_config_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_layers = ["sha256:" + "a" * 64]
    observed_layers = ["sha256:" + "b" * 64]
    expected_config = {
        "Entrypoint": ["greenhouse-manager"],
        "User": "greenhouse",
    }
    observed_config = {
        "Entrypoint": ["/bin/sh"],
        "User": "greenhouse",
    }
    manifest = {
        "manager": {
            "rootfs_layers_sha256": executor.canonical_sha256(expected_layers),
            "config_contract_sha256": executor.canonical_sha256(
                executor.image_config_contract(expected_config)
            ),
        }
    }

    def fake_run(_argv, **_kwargs):
        return json.dumps(
            [
                {
                    "Id": "sha256:" + "c" * 64,
                    "Architecture": "arm64",
                    "Os": "linux",
                    "RootFS": {"Layers": observed_layers},
                    "Config": observed_config,
                }
            ]
        )

    monkeypatch.setattr(executor, "run", fake_run)
    with pytest.raises(
        executor.RefreshError,
        match="target_image_rootfs_binding_invalid",
    ):
        executor.runtime_image_binding(manifest)


def test_live_package_validation_rechecks_distribution_inventory(
    tmp_path: Path,
) -> None:
    output, document = build_package(tmp_path)
    manifest_sha = hashlib.sha256(
        (output / "manifest.json").read_bytes()
    ).hexdigest()
    inventory = output / "manager-python-distributions.json"
    inventory.write_text(
        '[{"name":"tampered","version":"1"}]\n',
        encoding="utf-8",
    )
    with pytest.raises(
        executor.RefreshError,
        match="python_distributions_binding_invalid",
    ):
        executor.validate_package(output, manifest_sha)


def test_predecessor_ledgers_are_bound_and_protected() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    prestate = function_block(
        source,
        "def verify_prestate(",
        "def create_workspace(",
    )
    claim = function_block(
        source,
        "def claim_refresh(",
        "def advance(",
    )
    protected = function_block(
        source,
        "def protected_runtime_snapshot(",
        "def verify_prestate(",
    )
    assert "F4_TRANSACTION" in protected
    assert "PREDECESSOR_UPGRADE_TRANSACTION" in protected
    assert "r10_candidate_upgrade_committed" in prestate
    assert "candidate_upgrade_predecessor_authority_invalid" in prestate
    assert "predecessor_f4_transaction_sha256" in claim
    assert "predecessor_candidate_upgrade_transaction_sha256" in claim


def test_runtime_protection_covers_tls_dynsec_compose_and_registration_db() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    protected = function_block(
        source,
        "def protected_runtime_snapshot(",
        "def verify_prestate(",
    )
    for token in (
        '"compose_file": file_binding(COMPOSE_FILE)',
        '"registration_cert": file_binding(REGISTRATION_CERT)',
        '"registration_key": file_binding(REGISTRATION_KEY)',
        '"broker_dynsec": file_binding(BROKER_DYNSEC)',
        '"f4_transaction": file_binding(F4_TRANSACTION)',
        '"predecessor_upgrade_transaction": file_binding(',
        '"database": database_state()',
    ):
        assert token in protected

    database = function_block(
        source,
        "def database_state(",
        "def pairing_window_closed(",
    )
    assert '"business_fingerprint_sha256"' in database
    assert '"registrations"' in database
    assert '"first_registration_attempts"' in database


def test_predecessor_must_be_ttl30_and_target_must_be_ttl60() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    prestate = function_block(
        source,
        "def verify_prestate(",
        "def create_workspace(",
    )
    post = function_block(
        source,
        "def strict_target_postcheck(",
        "def wait_target_postcheck(",
    )
    assert "PREDECESSOR_CANDIDATE_TTL_SECONDS = 30" in source
    assert "EXPECTED_CANDIDATE_TTL_SECONDS = 60" in source
    assert "predecessor_candidate_ttl_not_30" in prestate
    assert "manager_candidate_ttl_not_60" in post

    rollback = function_block(
        source,
        "def strict_predecessor_postcheck(",
        "def wait_predecessor_postcheck(",
    )
    assert "rollback_candidate_ttl_not_30" in rollback


def test_broker_and_homeassistant_are_continuity_authorities() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    post = function_block(
        source,
        "def strict_target_postcheck(",
        "def wait_target_postcheck(",
    )
    assert 'if broker != prestate["broker"]:' in post
    assert 'homeassistant["id"] != prestate["homeassistant"]["id"]' in post
    assert 'homeassistant["image_id"] != prestate["homeassistant"]["image_id"]' in post
    assert 'homeassistant["image"] != prestate["homeassistant"]["image"]' in post


def test_rollback_restores_env_before_predecessor_restart() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    block = function_block(
        source,
        "def rollback(",
        "def execute_apply(",
    )
    stop = block.index('run(\n            ("systemctl", "stop", SERVICES_UNIT)')
    restore = block.index("atomic_write_bytes(\n            COMPOSE_ENV")
    start = block.index('run(("systemctl", "start", SERVICES_UNIT)')
    verify = block.index("wait_predecessor_postcheck(prestate)")
    assert stop < restore < start < verify


def test_no_board_or_secret_material_is_part_of_executor_output_contract() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert '"board_access": False' in source
    assert "setup_secret" not in source.lower()
    assert "mqtt_password" not in source.lower()
