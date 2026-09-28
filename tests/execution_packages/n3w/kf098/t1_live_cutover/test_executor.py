from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = (
    ROOT
    / "tools/execution_packages/n3w/kf098/t1_live_cutover"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load_module("kf098_host_executor", PACKAGE / "executor.py")
remote = load_module(
    "kf098_remote_cutover",
    PACKAGE / "remote_cutover.py",
)
bootstrap = load_module(
    "kf098_bootstrap_runner",
    PACKAGE / "bootstrap_runner.py",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_host_transport_disables_stdin_consumption() -> None:
    ssh = host.ssh_argv("root@t1", "true")
    scp = host.scp_argv(Path("/tmp/a"), "root@t1", "/tmp/b")
    assert "-n" in ssh
    assert "BatchMode=yes" in ssh
    assert "-B" in scp
    assert "BatchMode=yes" in scp


@pytest.mark.parametrize(
    "value",
    (
        "",
        " root@t1",
        "root@t1 ",
        "root @t1",
        "t1_ssh_target",
        "<root@host>",
    ),
)
def test_host_target_validation_rejects_unsafe_values(
    value: str,
) -> None:
    with pytest.raises(host.StopExecution):
        host.validate_target(value)


def test_local_artifact_requires_exact_manifest_and_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "greenhouse-manager-arm64.tar"
    image.write_bytes(b"image")
    image_sha = sha256(b"image")
    monkeypatch.setattr(host, "IMAGE_TAR_SHA256", image_sha)

    manifest = {
        "schema": "gh.n3w-manager-exact-source-artifact/1",
        "source": {"commit": host.SOURCE_SHA},
        "image": {
            "id": host.IMAGE_ID,
            "architecture": "arm64",
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha = sha256(manifest_path.read_bytes())
    (tmp_path / "manifest.sha256").write_text(
        f"{manifest_sha}  manifest.json\n",
        encoding="utf-8",
    )

    result = host.verify_local_artifact(tmp_path)
    assert result["artifact_id"] == host.ARTIFACT_ID
    assert result["image_tar_sha256"] == image_sha


def test_remote_env_rewrite_changes_only_pairing_value(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manager.env"
    path.write_text(
        "GH_ALPHA=one\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.10\n"
        "GH_BETA=two\n",
        encoding="utf-8",
    )
    before = remote.env_without_target_hash(path)
    remote.rewrite_pairing_env_to_auto(path)
    assert remote.env_values(path, remote.PAIRING_KEY) == ["auto"]
    assert remote.env_without_target_hash(path) == before
    assert path.read_text(encoding="utf-8") == (
        "GH_ALPHA=one\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=auto\n"
        "GH_BETA=two\n"
    )


def test_remote_env_rewrite_rejects_duplicate_target(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manager.env"
    path.write_text(
        "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.10\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.11\n",
        encoding="utf-8",
    )
    with pytest.raises(remote.StopExecution):
        remote.rewrite_pairing_env_to_auto(path)


def test_remote_recreate_uses_live_contract_not_compose() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    assert "manager_recreate_contract" in source
    assert '"docker",\n        "create"' in source
    assert "compose_up(" not in source
    assert "compose_shadow(" not in source
    assert "--remove-orphans" not in source


def test_remote_uses_current_pr480_activation_blob() -> None:
    assert (
        remote.EXPECTED_ACTIVATION_UNIT_BLOB
        == "5033b7475f4fafb1409ed277425197a93fd0d5a5"
    )


def test_remote_does_not_mutate_service_identities_source() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    assert "SERVICE_ENV" in source
    assert "rewrite_pairing_env_to_auto(MANAGER_ENV)" in source
    assert "rewrite_pairing_env_to_auto(SERVICE_ENV)" not in source
    assert "--remove-orphans" not in source


def test_git_blob_hash_uses_canonical_nul_header(
    tmp_path: Path,
) -> None:
    path = tmp_path / "blob"
    path.write_bytes(b"hello")
    expected = hashlib.sha1(b"blob 5\0hello").hexdigest()
    assert remote.git_blob_hash(path) == expected


def manager_fixture(
    *,
    image: str,
    pairing: str,
    running: bool = False,
) -> dict:
    return {
        "Image": image,
        "RestartCount": 0,
        "Config": {
            "Entrypoint": ["greenhouse-manager"],
            "User": "greenhouse",
            "Env": [
                "GH_ALPHA=one",
                f"{remote.PAIRING_KEY}={pairing}",
            ],
            "Healthcheck": None,
            "OpenStdin": False,
            "StdinOnce": False,
            "StopSignal": None,
            "StopTimeout": None,
            "Tty": False,
            "WorkingDir": "/app",
        },
        "HostConfig": {
            "AutoRemove": False,
            "CapAdd": None,
            "CapDrop": ["ALL"],
            "CgroupnsMode": "private",
            "DeviceRequests": None,
            "Devices": [],
            "Init": True,
            "IpcMode": "private",
            "LogConfig": {"Type": "json-file", "Config": {}},
            "Memory": 100663296,
            "MemorySwap": 201326592,
            "NanoCpus": 0,
            "NetworkMode": "host",
            "OomKillDisable": False,
            "PidMode": "",
            "PidsLimit": 64,
            "PortBindings": {},
            "Privileged": False,
            "ReadonlyRootfs": True,
            "RestartPolicy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
            "SecurityOpt": ["no-new-privileges"],
            "ShmSize": 67108864,
            "Tmpfs": {"/tmp": "size=16777216,mode=1777"},
            "Ulimits": None,
        },
        "Mounts": [
            {
                "Type": "bind",
                "Source": "/state",
                "Destination": "/state",
                "RW": True,
                "Propagation": "rprivate",
            }
        ],
        "State": {"Running": running},
    }


def test_runtime_security_fingerprint_detects_security_drift() -> None:
    current = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    same = manager_fixture(
        image=remote.NEW_IMAGE_MANIFEST_DIGEST,
        pairing="auto",
    )
    drift = manager_fixture(
        image=remote.NEW_IMAGE_MANIFEST_DIGEST,
        pairing="auto",
    )
    drift["HostConfig"]["ReadonlyRootfs"] = False
    assert (
        remote.manager_runtime_security_fingerprint(current)
        == remote.manager_runtime_security_fingerprint(same)
    )
    assert (
        remote.manager_runtime_security_fingerprint(current)
        != remote.manager_runtime_security_fingerprint(drift)
    )


def test_runtime_security_fingerprint_normalizes_docker_default_forms() -> None:
    live = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    shadow = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    live["HostConfig"]["Dns"] = []
    live["HostConfig"]["OomKillDisable"] = None
    shadow["HostConfig"]["Dns"] = None
    shadow["HostConfig"]["OomKillDisable"] = False

    assert (
        remote.pre495_runtime_security_fingerprint(live)
        != remote.pre495_runtime_security_fingerprint(shadow)
    )
    assert (
        remote.manager_runtime_security_fingerprint(live)
        == remote.manager_runtime_security_fingerprint(shadow)
    )


def test_runtime_security_fingerprint_keeps_nondefault_drift_visible() -> None:
    current = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    dns_drift = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    oom_drift = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    current["HostConfig"]["Dns"] = []
    current["HostConfig"]["OomKillDisable"] = None
    dns_drift["HostConfig"]["Dns"] = ["192.0.2.53"]
    dns_drift["HostConfig"]["OomKillDisable"] = False
    oom_drift["HostConfig"]["Dns"] = None
    oom_drift["HostConfig"]["OomKillDisable"] = True

    baseline = remote.manager_runtime_security_fingerprint(current)
    assert baseline != remote.manager_runtime_security_fingerprint(dns_drift)
    assert baseline != remote.manager_runtime_security_fingerprint(oom_drift)


def test_shadow_contract_accepts_only_exact_reproduction() -> None:
    current = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    count, mount_hash = remote.manager_mount_fingerprint(current)
    prestate = {
        "manager_mount_count": count,
        "manager_mount_hash": mount_hash,
        "manager_gh_env_hash": remote.gh_env_fingerprint(current),
        "manager_all_env_hash":
            remote.all_env_fingerprint_excluding_pairing(current),
        "manager_runtime_security_hash":
            remote.manager_runtime_security_fingerprint(current),
    }
    candidate = manager_fixture(
        image=remote.NEW_IMAGE_MANIFEST_DIGEST,
        pairing="auto",
    )
    remote.validate_shadow_manager(
        candidate,
        prestate,
        expected_image=remote.NEW_IMAGE_MANIFEST_DIGEST,
        expected_pairing=["auto"],
        label="new",
    )
    candidate["HostConfig"]["Privileged"] = True
    with pytest.raises(remote.StopExecution):
        remote.validate_shadow_manager(
            candidate,
            prestate,
            expected_image=remote.NEW_IMAGE_MANIFEST_DIGEST,
            expected_pairing=["auto"],
            label="new",
        )


def test_manual_rollback_requires_private_prestate_authority() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    assert 'rollback prestate authority is missing' in source
    assert 'rollback prestate authority is incomplete' in source


def test_rollback_preconditions_reject_unknown_manager_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose = tmp_path / "docker-compose.yml"
    manager_env = tmp_path / "manager.env"
    service_env = tmp_path / "service-identities.env"
    compose.write_text("services:\n  manager:\n", encoding="utf-8")
    manager_env.write_text(
        "GH_ALPHA=one\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=auto\n",
        encoding="utf-8",
    )
    service_env.write_text("GH_ALPHA=one\n", encoding="utf-8")

    monkeypatch.setattr(remote, "COMPOSE", compose)
    monkeypatch.setattr(remote, "MANAGER_ENV", manager_env)
    monkeypatch.setattr(remote, "SERVICE_ENV", service_env)
    monkeypatch.setattr(
        remote,
        "EXPECTED_COMPOSE_SHA256",
        remote.sha256_file(compose),
    )
    monkeypatch.setattr(
        remote,
        "EXPECTED_SERVICE_ENV_SHA256",
        remote.sha256_file(service_env),
    )
    monkeypatch.setattr(
        remote,
        "EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256",
        remote.env_without_target_hash(manager_env),
    )

    def fake_run(args, *, timeout=30):
        if args[:3] == ["docker", "inspect", remote.MANAGER_NAME]:
            return type(
                "Result",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps(
                        [{"Image": "sha256:" + "f" * 64}]
                    ),
                    "stderr": "",
                },
            )()
        raise AssertionError(args)

    monkeypatch.setattr(remote, "run", fake_run)

    with pytest.raises(remote.StopExecution) as error:
        remote.rollback_preconditions()
    assert "not transaction-owned" in str(error.value)


def test_rollback_preconditions_accept_transaction_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose = tmp_path / "docker-compose.yml"
    manager_env = tmp_path / "manager.env"
    service_env = tmp_path / "service-identities.env"
    compose.write_text("services:\n  manager:\n", encoding="utf-8")
    manager_env.write_text(
        "GH_ALPHA=one\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=auto\n",
        encoding="utf-8",
    )
    service_env.write_text("GH_ALPHA=one\n", encoding="utf-8")

    monkeypatch.setattr(remote, "COMPOSE", compose)
    monkeypatch.setattr(remote, "MANAGER_ENV", manager_env)
    monkeypatch.setattr(remote, "SERVICE_ENV", service_env)
    monkeypatch.setattr(
        remote,
        "EXPECTED_COMPOSE_SHA256",
        remote.sha256_file(compose),
    )
    monkeypatch.setattr(
        remote,
        "EXPECTED_SERVICE_ENV_SHA256",
        remote.sha256_file(service_env),
    )
    monkeypatch.setattr(
        remote,
        "EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256",
        remote.env_without_target_hash(manager_env),
    )

    def fake_run(args, *, timeout=30):
        if args[:3] == ["docker", "inspect", remote.MANAGER_NAME]:
            return type(
                "Result",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps(
                        [{"Image": remote.NEW_IMAGE_MANIFEST_DIGEST}]
                    ),
                    "stderr": "",
                },
            )()
        raise AssertionError(args)

    monkeypatch.setattr(remote, "run", fake_run)
    remote.rollback_preconditions()


def test_shadow_uses_direct_create_not_compose() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    assert "direct_shadow(" in source
    assert '"docker",\n        "create"' in source
    assert '"--no-start"' not in source
    assert '"COMPOSE_IGNORE_ORPHANS=true"' not in source
    assert '"--remove-orphans"' not in source


def test_host_evidence_root_and_files_are_private(
    tmp_path: Path,
) -> None:
    root = tmp_path / "evidence"
    host.validate_evidence_root(root)
    assert root.stat().st_mode & 0o777 == 0o700
    text_path = root / "text.txt"
    bytes_path = root / "bytes.bin"
    host.write_private_text(text_path, "value\n")
    host.write_private_bytes(bytes_path, b"value")
    assert text_path.stat().st_mode & 0o777 == 0o600
    assert bytes_path.stat().st_mode & 0o777 == 0o600


def test_host_rejects_existing_nonprivate_evidence_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "evidence"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(host.StopExecution):
        host.validate_evidence_root(root)


def test_apply_preserves_fail_rolled_back_terminal_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_env = tmp_path / "manager.env"
    manager_env.write_text(
        "GH_ALPHA=one\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.10\n",
        encoding="utf-8",
    )
    rollback_root = tmp_path / "rollback"
    monkeypatch.setattr(remote, "MANAGER_ENV", manager_env)
    monkeypatch.setattr(remote, "ROLLBACK_ROOT", rollback_root)
    monkeypatch.setattr(
        remote,
        "MANAGER_ENV_BACKUP",
        rollback_root / "manager.env.before",
    )
    monkeypatch.setattr(
        remote,
        "PRESTATE_JSON",
        rollback_root / "manager-prestate.json",
    )
    monkeypatch.setattr(
        remote,
        "EXPECTED_MANAGER_ENV_SHA256",
        remote.sha256_file(manager_env),
    )
    monkeypatch.setattr(
        remote,
        "EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256",
        remote.env_without_target_hash(manager_env),
    )
    monkeypatch.setattr(
        remote,
        "verify_stage_artifact",
        lambda: {"artifact": "PASS"},
    )
    monkeypatch.setattr(
        remote,
        "ensure_loaded_exact_image",
        lambda: {
            "runtime_image_id":
                remote.NEW_IMAGE_MANIFEST_DIGEST,
            "config_digest":
                remote.NEW_IMAGE_CONFIG_DIGEST,
            "manifest_digest":
                remote.NEW_IMAGE_MANIFEST_DIGEST,
            "rootfs_layers_sha256": "rootfs",
        },
    )
    monkeypatch.setattr(
        remote,
        "bind_old_rollback_image",
        lambda: {
            "runtime_image_id": remote.OLD_IMAGE_ID,
            "rootfs_layers_sha256": "old-rootfs",
        },
    )
    monkeypatch.setattr(
        remote,
        "base_preflight",
        lambda: {"prestate": "PASS"},
    )
    monkeypatch.setattr(
        remote,
        "cleanup_known_pretransaction_residual",
        lambda: "none",
    )
    monkeypatch.setattr(
        remote,
        "shadow_preflight",
        lambda _prestate, _old_runtime_id: {"shadow": "PASS"},
    )
    monkeypatch.setattr(
        remote,
        "create_manager_from_contract",
        lambda *args, **kwargs: {},
    )

    def fake_rewrite(path: Path) -> None:
        path.write_text(
            "GH_ALPHA=one\n"
            "GH_N3W_PAIRING_ADVERTISED_HOST=auto\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        remote,
        "rewrite_pairing_env_to_auto",
        fake_rewrite,
    )
    monkeypatch.setattr(
        remote,
        "postcheck",
        lambda _prestate: (_ for _ in ()).throw(
            remote.StopExecution("forced postcheck failure")
        ),
    )
    monkeypatch.setattr(
        remote,
        "rollback",
        lambda _prestate: {"rollback_result": "PASS"},
    )

    def fake_run(args, *, timeout=30):
        return remote.subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(remote, "run", fake_run)

    result = remote.apply()
    assert result["result"] == "FAIL_ROLLED_BACK"
    assert result["rollback"]["rollback_result"] == "PASS"
    assert result["rollback_error"] is None


def test_bootstrap_requires_exact_commit_sha() -> None:
    bootstrap.validate_ref("a" * 40)
    with pytest.raises(bootstrap.StopExecution):
        bootstrap.validate_ref("main")
    with pytest.raises(bootstrap.StopExecution):
        bootstrap.validate_ref("A" * 40)


def test_bootstrap_has_no_git_worktree_dependency() -> None:
    source = (PACKAGE / "bootstrap_runner.py").read_text(
        encoding="utf-8"
    )
    assert "git status" not in source
    assert "git fetch" not in source
    assert "git checkout" not in source
    assert "git rev-parse" not in source
    assert "gh" in source
    assert "ARTIFACT_RUN_ID" in source


def test_bootstrap_cached_package_is_hash_bound(
    tmp_path: Path,
) -> None:
    package_ref = "a" * 40
    package_dir = tmp_path / f"package-{package_ref[:12]}"
    package_dir.mkdir(mode=0o700)
    hashes = {}
    for name in bootstrap.PACKAGE_FILES:
        payload = f"{name}\n".encode()
        path = package_dir / name
        path.write_bytes(payload)
        path.chmod(0o600)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    authority = {
        "repository": bootstrap.REPOSITORY,
        "package_ref": package_ref,
        "files": hashes,
    }
    authority_path = package_dir / "package-authority.json"
    authority_path.write_text(
        json.dumps(authority),
        encoding="utf-8",
    )
    authority_path.chmod(0o600)

    assert (
        bootstrap.verify_cached_package(package_dir, package_ref)
        == hashes
    )

    (package_dir / "executor.py").write_text(
        "drift\n",
        encoding="utf-8",
    )
    with pytest.raises(bootstrap.StopExecution):
        bootstrap.verify_cached_package(
            package_dir,
            package_ref,
        )


def test_bootstrap_evidence_path_is_work_root_relative(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private-root"
    root.mkdir(mode=0o700)
    path = bootstrap.evidence_root(
        root,
        "local-preflight",
        1,
    )
    assert path == root / "evidence-local-preflight-01"
    assert path.stat().st_mode & 0o777 == 0o700
    with pytest.raises(bootstrap.StopExecution):
        bootstrap.evidence_root(
            root,
            "local-preflight",
            1,
        )


def test_bootstrap_private_root_rejects_loose_mode(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(bootstrap.StopExecution):
        bootstrap.ensure_private_root(root)


def test_record_timeout_becomes_structured_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "evidence"
    root.mkdir(mode=0o700)

    def fake_run(*args, **kwargs):
        raise host.subprocess.TimeoutExpired(
            cmd=["ssh"],
            timeout=30,
            output=b"partial-out",
            stderr=b"partial-err",
        )

    monkeypatch.setattr(host.subprocess, "run", fake_run)

    with pytest.raises(host.StopExecution) as error:
        host.record(
            root,
            1,
            "target_preflight",
            ["ssh"],
            timeout=30,
        )

    assert "timed out after 30 seconds" in str(error.value)
    result = json.loads(
        (root / "op_01_target_preflight/result.json")
        .read_text(encoding="utf-8")
    )
    assert result["timed_out"] is True
    assert result["timeout_seconds"] == 30
    assert (
        root / "op_01_target_preflight/stdout.bin"
    ).read_bytes() == b"partial-out"
    assert (
        root / "op_01_target_preflight/stderr.bin"
    ).read_bytes() == b"partial-err"


def test_target_preflight_has_inner_and_outer_timeout_contract() -> None:
    source = (PACKAGE / "executor.py").read_text(
        encoding="utf-8"
    )
    assert 'timeout=10,' in source
    assert '"docker_probe": docker_probe' in source
    assert '"target_preflight",' in source
    assert 'timeout=30,' in source


def test_remote_phase_has_phase_specific_timeout_budget() -> None:
    source = (PACKAGE / "executor.py").read_text(
        encoding="utf-8"
    )
    assert '"preflight": 180' in source
    assert '"apply": 900' in source
    assert '"rollback": 600' in source


def test_ssh_uses_server_alive_bounds() -> None:
    argv = host.ssh_argv("root@t1", "true")
    assert "ServerAliveInterval=5" in argv
    assert "ServerAliveCountMax=2" in argv


def test_new_image_accepts_classic_and_containerd_runtime_ids() -> None:
    assert remote.accepted_new_runtime_image_ids() == {
        remote.NEW_IMAGE_CONFIG_DIGEST,
        remote.NEW_IMAGE_MANIFEST_DIGEST,
    }


@pytest.mark.parametrize(
    "runtime_id",
    (
        remote.NEW_IMAGE_CONFIG_DIGEST,
        remote.NEW_IMAGE_MANIFEST_DIGEST,
    ),
)
def test_verify_loaded_exact_image_accepts_store_specific_id(
    runtime_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = {
        "Id": runtime_id,
        "Architecture": "arm64",
        "Os": "linux",
        "Config": {
            "Entrypoint": ["greenhouse-manager"],
            "User": "greenhouse",
        },
        "RootFS": {
            "Layers": [
                "sha256:a",
                "sha256:b",
            ]
        },
    }
    expected_rootfs = remote.normalized_hash(
        item["RootFS"]["Layers"]
    )
    monkeypatch.setattr(
        remote,
        "EXPECTED_NEW_ROOTFS_LAYERS_SHA256",
        expected_rootfs,
    )
    monkeypatch.setattr(
        remote,
        "image_inspect",
        lambda _reference: item,
    )
    result = remote.verify_loaded_exact_image()
    assert result["runtime_image_id"] == runtime_id
    assert (
        result["config_digest"]
        == remote.NEW_IMAGE_CONFIG_DIGEST
    )
    assert (
        result["manifest_digest"]
        == remote.NEW_IMAGE_MANIFEST_DIGEST
    )


def test_verify_loaded_exact_image_rejects_unknown_runtime_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        remote,
        "image_inspect",
        lambda _reference: {
            "Id": "sha256:" + "f" * 64,
            "Architecture": "arm64",
            "Os": "linux",
            "Config": {
                "Entrypoint": ["greenhouse-manager"],
                "User": "greenhouse",
            },
            "RootFS": {"Layers": []},
        },
    )
    with pytest.raises(remote.StopExecution):
        remote.verify_loaded_exact_image()


def test_prepare_transaction_snapshot_reuses_exact_pretransaction_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_env = tmp_path / "manager.env"
    manager_env.write_text("GH_ALPHA=one\n", encoding="utf-8")
    expected_env_sha = remote.sha256_file(manager_env)
    rollback_root = tmp_path / "rollback"
    rollback_root.mkdir(mode=0o700)
    backup = rollback_root / "manager.env.before"
    backup.write_bytes(manager_env.read_bytes())
    prestate_path = rollback_root / "manager-prestate.json"
    prestate = {
        "manager_image_id": remote.OLD_IMAGE_ID,
        "manager_mount_count": 6,
        "manager_mount_hash": "m",
        "manager_gh_env_hash": "e",
        "manager_all_env_hash": "a",
        "manager_runtime_security_hash": "s",
        "manager_recreate_contract": {
            "env": [],
            "mounts": [],
        },
        "broker_id": "b",
        "broker_restart_count": 0,
        "firewall": {"x": 1},
    }
    prestate_path.write_text(
        json.dumps(prestate),
        encoding="utf-8",
    )
    monkeypatch.setattr(remote, "ROLLBACK_ROOT", rollback_root)
    monkeypatch.setattr(remote, "MANAGER_ENV_BACKUP", backup)
    monkeypatch.setattr(remote, "PRESTATE_JSON", prestate_path)
    monkeypatch.setattr(remote, "EXPECTED_MANAGER_ENV_SHA256", expected_env_sha)
    monkeypatch.setattr(
        remote,
        "cleanup_known_pretransaction_residual",
        lambda: "none",
    )

    original_stat = remote.Path.stat

    def fake_stat(path_self):
        result = original_stat(path_self)
        if path_self == rollback_root:
            values = list(result)
            values[4] = 0
            return os.stat_result(values)
        return result

    monkeypatch.setattr(remote.Path, "stat", fake_stat)
    result = remote.prepare_transaction_snapshot(prestate)
    assert result == {
        "snapshot": "reused_verified_pretransaction",
        "residual_cleanup": "none",
    }


def test_postrollback_reacquire_accepts_only_lifecycle_and_docker_defaults() -> None:
    before = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    after = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    before["HostConfig"]["Dns"] = []
    before["HostConfig"]["OomKillDisable"] = None
    after["HostConfig"]["Dns"] = None
    after["HostConfig"]["OomKillDisable"] = False

    common = {
        "manager_image_id": remote.OLD_IMAGE_ID,
        "manager_mount_count": 6,
        "manager_mount_hash": "m",
        "manager_gh_env_hash": "e",
        "manager_all_env_hash": "a",
        "manager_runtime_security_hash":
            remote.manager_runtime_security_fingerprint(before),
        "broker_id": "b",
        "broker_restart_count": 0,
        "firewall": {"x": 1},
        "current_eth0_ipv4_sha256": "ip",
    }
    saved = {
        **common,
        "manager_started_at": "2026-09-28T01:01:03Z",
        "manager_restart_count": 1,
        "manager_recreate_contract":
            remote.manager_recreate_contract(before),
    }
    current = {
        **common,
        "manager_started_at": "2026-09-28T03:53:13Z",
        "manager_restart_count": 0,
        "manager_recreate_contract":
            remote.manager_recreate_contract(after),
    }

    assert remote.verified_postrollback_reacquire(saved, current)

    drift = dict(current)
    drift["broker_restart_count"] = 1
    assert not remote.verified_postrollback_reacquire(saved, drift)


def test_prepare_transaction_snapshot_reacquires_verified_postrollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_env = tmp_path / "manager.env"
    manager_env.write_text("GH_ALPHA=one\n", encoding="utf-8")
    expected_env_sha = remote.sha256_file(manager_env)
    rollback_root = tmp_path / "rollback"
    rollback_root.mkdir(mode=0o700)
    backup = rollback_root / "manager.env.before"
    backup.write_bytes(manager_env.read_bytes())
    prestate_path = rollback_root / "manager-prestate.json"

    before = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    after = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    before["HostConfig"]["Dns"] = []
    before["HostConfig"]["OomKillDisable"] = None
    after["HostConfig"]["Dns"] = None
    after["HostConfig"]["OomKillDisable"] = False

    common = {
        "manager_image_id": remote.OLD_IMAGE_ID,
        "manager_mount_count": 6,
        "manager_mount_hash": "m",
        "manager_gh_env_hash": "e",
        "manager_all_env_hash": "a",
        "manager_runtime_security_hash":
            remote.manager_runtime_security_fingerprint(before),
        "broker_id": "b",
        "broker_restart_count": 0,
        "firewall": {"x": 1},
        "current_eth0_ipv4_sha256": "ip",
    }
    saved = {
        **common,
        "manager_started_at": "2026-09-28T01:01:03Z",
        "manager_restart_count": 1,
        "manager_recreate_contract":
            remote.manager_recreate_contract(before),
    }
    current = {
        **common,
        "manager_started_at": "2026-09-28T03:53:13Z",
        "manager_restart_count": 0,
        "manager_recreate_contract":
            remote.manager_recreate_contract(after),
    }
    prestate_path.write_text(
        json.dumps(saved),
        encoding="utf-8",
    )

    monkeypatch.setattr(remote, "ROLLBACK_ROOT", rollback_root)
    monkeypatch.setattr(remote, "MANAGER_ENV_BACKUP", backup)
    monkeypatch.setattr(remote, "PRESTATE_JSON", prestate_path)
    monkeypatch.setattr(
        remote,
        "EXPECTED_MANAGER_ENV_SHA256",
        expected_env_sha,
    )
    monkeypatch.setattr(
        remote,
        "cleanup_known_pretransaction_residual",
        lambda: "none",
    )

    original_stat = remote.Path.stat

    def fake_stat(path_self):
        result = original_stat(path_self)
        if path_self == rollback_root:
            values = list(result)
            values[4] = 0
            return os.stat_result(values)
        return result

    monkeypatch.setattr(remote.Path, "stat", fake_stat)
    result = remote.prepare_transaction_snapshot(current)
    assert result == {
        "snapshot": "upgraded_verified_pretransaction",
        "snapshot_migration": "post-rollback-live-reacquire",
        "residual_cleanup": "none",
    }
    assert json.loads(
        prestate_path.read_text(encoding="utf-8")
    ) == current


def test_postcheck_waits_for_health_before_listener_assertions() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    block = source[
        source.index("def postcheck("):
        source.index("LEGACY_PRESTATE_KEYS")
    ]
    assert block.index("wait_health()") < block.index(
        'socket_port_count("tcp", 47112)'
    )


def test_preflight_accepts_original_or_rollback_restart_count() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    assert 'manager.get("RestartCount") not in (0, 1)' in source


def test_prepare_transaction_snapshot_upgrades_pre493_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_env = tmp_path / "manager.env"
    manager_env.write_text("GH_ALPHA=one\n", encoding="utf-8")
    expected_env_sha = remote.sha256_file(manager_env)
    rollback_root = tmp_path / "rollback"
    rollback_root.mkdir(mode=0o700)
    backup = rollback_root / "manager.env.before"
    backup.write_bytes(manager_env.read_bytes())
    prestate_path = rollback_root / "manager-prestate.json"

    current = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    current["Config"]["Labels"] = {}
    current["HostConfig"]["Dns"] = []
    current["HostConfig"]["ExtraHosts"] = []

    prestate = {
        "manager_started_at": "2026-09-28T00:00:00Z",
        "manager_restart_count": 1,
        "manager_image_id": remote.OLD_IMAGE_ID,
        "manager_mount_count": 6,
        "manager_mount_hash": "m",
        "manager_gh_env_hash": "e",
        "manager_all_env_hash": "a",
        "manager_runtime_security_hash":
            remote.manager_runtime_security_fingerprint(current),
        "manager_recreate_contract": {
            "env": [],
            "mounts": [],
        },
        "broker_id": "b",
        "broker_restart_count": 0,
        "firewall": {"x": 1},
        "current_eth0_ipv4_sha256": "ip",
    }
    saved = {
        key: prestate[key]
        for key in remote.PRE493_PRESTATE_KEYS
    }
    saved["manager_runtime_security_hash"] = (
        remote.pre493_runtime_security_fingerprint(current)
    )
    assert (
        saved["manager_runtime_security_hash"]
        != prestate["manager_runtime_security_hash"]
    )
    prestate_path.write_text(
        json.dumps(saved),
        encoding="utf-8",
    )

    monkeypatch.setattr(remote, "ROLLBACK_ROOT", rollback_root)
    monkeypatch.setattr(remote, "MANAGER_ENV_BACKUP", backup)
    monkeypatch.setattr(remote, "PRESTATE_JSON", prestate_path)
    monkeypatch.setattr(
        remote,
        "EXPECTED_MANAGER_ENV_SHA256",
        expected_env_sha,
    )
    monkeypatch.setattr(
        remote,
        "cleanup_known_pretransaction_residual",
        lambda: "none",
    )
    monkeypatch.setattr(
        remote,
        "docker_inspect",
        lambda _name: current,
    )

    original_stat = remote.Path.stat

    def fake_stat(path_self):
        result = original_stat(path_self)
        if path_self == rollback_root:
            values = list(result)
            values[4] = 0
            return os.stat_result(values)
        return result

    monkeypatch.setattr(remote.Path, "stat", fake_stat)
    result = remote.prepare_transaction_snapshot(prestate)
    assert result == {
        "snapshot": "upgraded_verified_pretransaction",
        "snapshot_migration": "pre-PR493",
        "residual_cleanup": "none",
    }
    assert json.loads(
        prestate_path.read_text(encoding="utf-8")
    ) == prestate


def test_prepare_transaction_snapshot_upgrades_pre495_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_env = tmp_path / "manager.env"
    manager_env.write_text("GH_ALPHA=one\n", encoding="utf-8")
    expected_env_sha = remote.sha256_file(manager_env)
    rollback_root = tmp_path / "rollback"
    rollback_root.mkdir(mode=0o700)
    backup = rollback_root / "manager.env.before"
    backup.write_bytes(manager_env.read_bytes())
    prestate_path = rollback_root / "manager-prestate.json"

    current = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    current["Config"]["Labels"] = {}
    current["HostConfig"]["Dns"] = []
    current["HostConfig"]["ExtraHosts"] = []
    current["HostConfig"]["OomKillDisable"] = None

    prestate = {
        "manager_started_at": "2026-09-28T00:00:00Z",
        "manager_restart_count": 1,
        "manager_image_id": remote.OLD_IMAGE_ID,
        "manager_mount_count": 6,
        "manager_mount_hash": "m",
        "manager_gh_env_hash": "e",
        "manager_all_env_hash": "a",
        "manager_runtime_security_hash":
            remote.manager_runtime_security_fingerprint(current),
        "manager_recreate_contract": {
            "env": [],
            "mounts": [],
        },
        "broker_id": "b",
        "broker_restart_count": 0,
        "firewall": {"x": 1},
        "current_eth0_ipv4_sha256": "ip",
    }
    saved = dict(prestate)
    saved["manager_runtime_security_hash"] = (
        remote.pre495_runtime_security_fingerprint(current)
    )
    assert set(saved) == remote.PRE495_PRESTATE_KEYS
    assert (
        saved["manager_runtime_security_hash"]
        != prestate["manager_runtime_security_hash"]
    )
    prestate_path.write_text(
        json.dumps(saved),
        encoding="utf-8",
    )

    monkeypatch.setattr(remote, "ROLLBACK_ROOT", rollback_root)
    monkeypatch.setattr(remote, "MANAGER_ENV_BACKUP", backup)
    monkeypatch.setattr(remote, "PRESTATE_JSON", prestate_path)
    monkeypatch.setattr(
        remote,
        "EXPECTED_MANAGER_ENV_SHA256",
        expected_env_sha,
    )
    monkeypatch.setattr(
        remote,
        "cleanup_known_pretransaction_residual",
        lambda: "none",
    )
    monkeypatch.setattr(
        remote,
        "docker_inspect",
        lambda _name: current,
    )

    original_stat = remote.Path.stat

    def fake_stat(path_self):
        result = original_stat(path_self)
        if path_self == rollback_root:
            values = list(result)
            values[4] = 0
            return os.stat_result(values)
        return result

    monkeypatch.setattr(remote.Path, "stat", fake_stat)
    result = remote.prepare_transaction_snapshot(prestate)
    assert result == {
        "snapshot": "upgraded_verified_pretransaction",
        "snapshot_migration": "pre-PR495-runtime-normalization",
        "residual_cleanup": "none",
    }
    assert json.loads(
        prestate_path.read_text(encoding="utf-8")
    ) == prestate


def test_pre493_runtime_security_fingerprint_matches_old_contract() -> None:
    current = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    current["Config"]["Labels"] = {}
    current["HostConfig"]["Dns"] = []
    current["HostConfig"]["ExtraHosts"] = []
    assert (
        remote.pre493_runtime_security_fingerprint(current)
        != remote.manager_runtime_security_fingerprint(current)
    )


def test_source_binds_containerd_manifest_and_rootfs() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    assert remote.NEW_IMAGE_MANIFEST_DIGEST in source
    assert remote.NEW_IMAGE_CONFIG_DIGEST in source
    assert remote.EXPECTED_NEW_ROOTFS_LAYERS_SHA256 in source
    assert "verify_loaded_exact_image" in source
    assert "reused_verified_pretransaction" in source


def test_stage_classifier_allows_only_verified_pretransaction_snapshot() -> None:
    source = (PACKAGE / "executor.py").read_text(
        encoding="utf-8"
    )
    assert "REUSABLE_PRETRANSACTION_SNAPSHOT" in source
    assert "manager.env.before" in source
    assert "manager-prestate.json" in source
    assert host.EXPECTED_MANAGER_ENV_SHA256 in source


def test_shadow_accepts_either_artifact_owned_new_image_id() -> None:
    current = manager_fixture(
        image=remote.OLD_IMAGE_ID,
        pairing="192.0.2.10",
    )
    count, mount_hash = remote.manager_mount_fingerprint(current)
    prestate = {
        "manager_mount_count": count,
        "manager_mount_hash": mount_hash,
        "manager_gh_env_hash": remote.gh_env_fingerprint(current),
        "manager_all_env_hash":
            remote.all_env_fingerprint_excluding_pairing(current),
        "manager_runtime_security_hash":
            remote.manager_runtime_security_fingerprint(current),
    }
    for runtime_id in (
        remote.NEW_IMAGE_CONFIG_DIGEST,
        remote.NEW_IMAGE_MANIFEST_DIGEST,
    ):
        candidate = manager_fixture(
            image=runtime_id,
            pairing="auto",
        )
        remote.validate_shadow_manager(
            candidate,
            prestate,
            expected_image=remote.accepted_new_runtime_image_ids(),
            expected_pairing=["auto"],
            label="new",
        )


def test_ensure_loaded_exact_image_reuses_existing_exact_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(args, *, timeout=30):
        assert args == [
            "docker",
            "image",
            "inspect",
            remote.NEW_IMAGE_TAG,
        ]
        return remote.subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="[]",
            stderr="",
        )

    monkeypatch.setattr(remote, "run", fake_run)
    monkeypatch.setattr(
        remote,
        "verify_loaded_exact_image",
        lambda: {
            "runtime_image_id":
                remote.NEW_IMAGE_MANIFEST_DIGEST,
            "config_digest":
                remote.NEW_IMAGE_CONFIG_DIGEST,
            "manifest_digest":
                remote.NEW_IMAGE_MANIFEST_DIGEST,
            "rootfs_layers_sha256":
                remote.EXPECTED_NEW_ROOTFS_LAYERS_SHA256,
        },
    )
    result = remote.ensure_loaded_exact_image()
    assert result["load_action"] == "reused_existing_exact_tag"
    assert (
        result["runtime_image_id"]
        == remote.NEW_IMAGE_MANIFEST_DIGEST
    )


def test_ensure_loaded_exact_image_loads_when_tag_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_run(args, *, timeout=30):
        calls.append((args, timeout))
        if args == [
            "docker",
            "image",
            "inspect",
            remote.NEW_IMAGE_TAG,
        ]:
            return remote.subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout="",
                stderr="missing",
            )
        if args == [
            "docker",
            "load",
            "-i",
            str(remote.IMAGE_TAR),
        ]:
            return remote.subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="loaded",
                stderr="",
            )
        raise AssertionError(args)

    monkeypatch.setattr(remote, "run", fake_run)
    monkeypatch.setattr(
        remote,
        "verify_loaded_exact_image",
        lambda: {
            "runtime_image_id":
                remote.NEW_IMAGE_CONFIG_DIGEST,
            "config_digest":
                remote.NEW_IMAGE_CONFIG_DIGEST,
            "manifest_digest":
                remote.NEW_IMAGE_MANIFEST_DIGEST,
            "rootfs_layers_sha256":
                remote.EXPECTED_NEW_ROOTFS_LAYERS_SHA256,
        },
    )
    result = remote.ensure_loaded_exact_image()
    assert result["load_action"] == "loaded_exact_tar"
    assert calls[1][1] == 180


def test_pairing_replaced_env_changes_only_target() -> None:
    before = [
        "GH_ALPHA=one",
        "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.10",
        "PATH=/usr/bin",
    ]
    assert remote.pairing_replaced_env(before, "auto") == [
        "GH_ALPHA=one",
        "GH_N3W_PAIRING_ADVERTISED_HOST=auto",
        "PATH=/usr/bin",
    ]


def test_manager_create_argv_uses_live_runtime_contract(
    tmp_path: Path,
) -> None:
    contract = {
        "env": [
            "GH_ALPHA=one",
            "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.10",
        ],
        "mounts": [
            {
                "Type": "bind",
                "Source": f"/state/{i}",
                "Destination": f"/target/{i}",
                "RW": i % 2 == 0,
                "Propagation": "rprivate",
            }
            for i in range(6)
        ],
        "labels": {},
        "entrypoint": ["greenhouse-manager"],
        "cmd": None,
        "user": "greenhouse",
        "working_dir": "/app",
        "healthcheck": None,
        "stop_signal": None,
        "stop_timeout": None,
        "open_stdin": False,
        "stdin_once": False,
        "tty": False,
        "host": {
            "AutoRemove": False,
            "CapAdd": None,
            "CapDrop": None,
            "CgroupnsMode": "private",
            "DeviceRequests": None,
            "Devices": [],
            "Dns": [],
            "ExtraHosts": None,
            "Init": None,
            "IpcMode": "private",
            "LogConfig": {
                "Type": "json-file",
                "Config": {"max-file": "3", "max-size": "10m"},
            },
            "Memory": 0,
            "MemorySwap": 0,
            "NanoCpus": 0,
            "NetworkMode": "host",
            "OomKillDisable": False,
            "PidMode": "",
            "PidsLimit": None,
            "PortBindings": {},
            "Privileged": False,
            "ReadonlyRootfs": True,
            "RestartPolicy": {
                "Name": "unless-stopped",
                "MaximumRetryCount": 0,
            },
            "SecurityOpt": None,
            "ShmSize": 67108864,
            "Tmpfs": {"/tmp": "size=16m,mode=1777"},
            "Ulimits": None,
        },
    }
    argv = remote.manager_create_argv(
        contract,
        image=remote.NEW_IMAGE_TAG,
        name="candidate",
        env_file=tmp_path / "runtime.env",
    )
    assert argv[:2] == ["docker", "create"]
    assert argv.count("--mount") == 6
    assert "--network" in argv and "host" in argv
    assert "--read-only" in argv
    assert "--tmpfs" in argv
    assert "--log-driver" in argv
    assert argv[-1] == remote.NEW_IMAGE_TAG


def test_source_no_longer_uses_compose_for_manager_recreate() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    assert "create_manager_from_contract" in source
    assert "compose_up(" not in source
    assert "compose_shadow(" not in source
    assert "docker\", \"compose" not in source


def test_stage_classifier_knows_failed_shadow_residual() -> None:
    source = (PACKAGE / "executor.py").read_text(
        encoding="utf-8"
    )
    assert "manager-kf098-shadow-old-overlay.yml" in source
    assert host.STALE_SHADOW_OLD_OVERLAY_SHA256 in source
