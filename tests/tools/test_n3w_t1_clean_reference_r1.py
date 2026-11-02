from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import n3w_t1_clean_reference_executor as executor
from tools import n3w_t1_clean_reference_runtime_payload_builder as builder
from tools import n3w_t1_clean_reference_staging_host as host

SOURCE_HEAD = "24382caae4a1f5d459297f86e8d18f10a848ca64"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def s1_binding(root: Path) -> dict:
    records = {}
    values = {
        "manager": (
            "greenhouse-manager-arm64.tar",
            f"local/greenhouse-manager:fresh-{SOURCE_HEAD[:12]}",
            "sha256:" + "1" * 64,
        ),
        "homeassistant": (
            "homeassistant-arm64.tar",
            "local/n3w-homeassistant:2026.10.0-0c73235a",
            "sha256:" + "2" * 64,
        ),
        "broker": (
            "broker-arm64.tar",
            "local/n3w-mosquitto:2.1.2-3184566d",
            "sha256:" + "3" * 64,
        ),
    }
    for label, (filename, image, image_id) in values.items():
        path = root / filename
        path.write_bytes((label * 8).encode())
        records[label] = {
            "image": image,
            "image_id": image_id,
            "tar_sha256": sha(path),
            "tar_size_bytes": path.stat().st_size,
            "platform": "linux/arm64",
        }
    records["homeassistant"]["manifest_digest"] = (
        "sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4"
    )
    records["broker"]["manifest_digest"] = (
        "sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549"
    )
    document = {
        "schema": builder.S1_SCHEMA,
        "source_head": SOURCE_HEAD,
        **records,
        "fresh_runtime_identity_binding": True,
        "node_credential_count": 0,
        "production_service_start": False,
        "secret_values_included": False,
        "t1_access": False,
        "board_access": False,
    }
    (root / "binding.json").write_text(
        json.dumps(document, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return document


def runtime_root(tmp_path: Path, image_root: Path) -> Path:
    root = tmp_path / "runtime"
    root.mkdir()
    binding = json.loads((image_root / "binding.json").read_text())
    image_records = {
        label: {
            key: binding[label][key]
            for key in ("image", "image_id", "tar_sha256", "tar_size_bytes", "platform")
        }
        for label in ("manager", "homeassistant", "broker")
    }
    runtime_binding = {
        "schema": host.RUNTIME_BINDING_SCHEMA,
        "source_head": SOURCE_HEAD,
        "s1_binding_sha256": sha(image_root / "binding.json"),
        "runtime_payload_sha256": "a" * 64,
        "payload_manifest_sha256": "b" * 64,
        "images": image_records,
        "image_rebuild_performed": False,
        "registry_pull_performed": False,
        "production_service_start": False,
        "t1_access": False,
        "board_access": False,
    }
    for name in host.RUNTIME_FILES:
        if name == "runtime-binding.json":
            (root / name).write_text(json.dumps(runtime_binding), encoding="utf-8")
        else:
            (root / name).write_text(name, encoding="utf-8")
    return root


def test_s1_binding_rejects_tampered_image(tmp_path: Path) -> None:
    root = tmp_path / "images"
    root.mkdir()
    s1_binding(root)
    (root / "greenhouse-manager-arm64.tar").write_bytes(b"tampered")
    with pytest.raises(
        builder.CleanReferenceRuntimeBuildError,
        match="s1_image_binding_invalid:manager",
    ):
        builder._verify_s1(root, SOURCE_HEAD)


def test_runtime_builder_source_contains_no_image_build_or_pull() -> None:
    source = Path(builder.__file__).read_text(encoding="utf-8")
    executable = source.split("\ndef _parser(", 1)[0]
    assert '("docker", "load"' in executable
    assert '"docker", "build"' not in executable
    assert '"docker", "pull"' not in executable
    assert '"buildx"' not in executable


def test_executor_dynamic_payload_import_does_not_write_bytecode(
    tmp_path: Path,
) -> None:
    module_path = tmp_path / "payload_module.py"
    module_path.write_text("VALUE = 7\n", encoding="utf-8")

    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = False
        loaded = executor._load_module(
            module_path,
            "n3w_test_clean_reference_payload_module",
        )
    finally:
        sys.dont_write_bytecode = previous

    assert loaded.VALUE == 7
    assert not (tmp_path / "__pycache__").exists()


def test_clean_reference_bridge_enables_staged_units_before_postcheck() -> None:
    calls: list[str] = []

    class Adapter:
        def enable_staged_units(self):
            calls.append("enable")
            return {
                "status": "PASS",
                "provision_resume_enabled": True,
                "production_activation_enabled": False,
                "production_service_start": False,
            }

        def stopped_postcheck(self, system_id: str):
            calls.append(f"postcheck:{system_id}")
            return {"status": "PASS"}

    bridge = executor.CleanReferenceAdapterBridge(Adapter())
    report = bridge.stopped_postcheck("system-1")

    assert report == {"status": "PASS"}
    assert calls == ["enable", "postcheck:system-1"]


def test_clean_reference_bridge_cleanup_disables_units_before_delegate(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...] | str] = []

    class Runner:
        def run(self, argv, **_kwargs):
            calls.append(tuple(argv))
            return ""

    class Adapter:
        runner = Runner()

        def cleanup(self, candidate_root: Path):
            calls.append(f"cleanup:{candidate_root}")
            return {
                "status": "PASS",
                "transaction_owned_only": True,
                "production_service_start": False,
            }

    bridge = executor.CleanReferenceAdapterBridge(Adapter())
    candidate = tmp_path / "candidate"
    report = bridge.cleanup(candidate)

    expected = [
        ("systemctl", "disable", unit)
        for unit in executor.STAGED_UNITS
    ]
    assert calls[:3] == expected
    assert calls[3] == f"cleanup:{candidate}"
    assert report["status"] == "PASS"


def test_clean_reference_bridge_cleanup_failure_is_not_silenced(
    tmp_path: Path,
) -> None:
    class Runner:
        def run(self, argv, **_kwargs):
            if argv[-1] == executor.STAGED_UNITS[1]:
                raise RuntimeError("disable failed")
            return ""

    class Adapter:
        runner = Runner()
        cleanup_called = False

        def cleanup(self, _candidate_root: Path):
            self.cleanup_called = True
            return {
                "status": "PASS",
                "transaction_owned_only": True,
                "production_service_start": False,
            }

    adapter = Adapter()
    bridge = executor.CleanReferenceAdapterBridge(adapter)

    with pytest.raises(
        executor.CleanReferenceExecutorError,
        match="staged_unit_cleanup_incomplete",
    ):
        bridge.cleanup(tmp_path / "candidate")

    assert adapter.cleanup_called is True


def test_executor_requires_explicit_clean_reference_confirmation() -> None:
    with pytest.raises(
        executor.CleanReferenceExecutorError,
        match="clean_reference_confirmation_mismatch",
    ):
        executor.execute_apply(Path("/does-not-matter"), "WRONG")


def test_executor_calls_stopped_fresh_staging_without_production_v2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class Contract:
        @staticmethod
        def run_fresh_staging(adapter, candidate, *, before_mutation=None):
            calls.append("run_fresh_staging")
            assert before_mutation is not None
            before_mutation()
            return {
                "status": "PASS",
                "fresh_product_staged": True,
                "node_credential_count": 0,
                "production_service_start": False,
                "activation_authorized": False,
            }

    manifest = {"source_head": SOURCE_HEAD, "production_service_start": False}
    monkeypatch.setattr(executor.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        executor,
        "_load_payload",
        lambda _root: (
            SimpleNamespace(),
            Contract(),
            manifest,
            SimpleNamespace(),
        ),
    )
    report = executor.execute_apply(tmp_path, executor.CONFIRMATION)
    assert calls == ["run_fresh_staging"]
    assert report["status"] == "PASS"
    assert report["production_v2_authority_used"] is False
    assert report["production_service_start"] is False
    assert report["activation_authorized"] is False


def test_executor_source_does_not_reference_production_marker_or_ledger() -> None:
    source = Path(executor.__file__).read_text(encoding="utf-8")
    assert "production_marker" not in source
    assert "AUTHORIZATION_LEDGER" not in source
    assert "run_context" not in source


def test_local_split_rejects_runtime_s1_source_mismatch(
    tmp_path: Path,
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    s1_binding(images)
    runtime = runtime_root(tmp_path, images)
    document = json.loads((runtime / "runtime-binding.json").read_text())
    document["source_head"] = "0" * 40
    (runtime / "runtime-binding.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(
        host.CleanReferenceHostError,
        match="runtime_s1_binding_mismatch",
    ):
        host._materialize_local_work(runtime, images)


def test_local_split_rejects_image_tar_tamper(
    tmp_path: Path,
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    s1_binding(images)
    runtime = runtime_root(tmp_path, images)
    (images / "broker-arm64.tar").write_bytes(b"tampered")
    with pytest.raises(
        host.CleanReferenceHostError,
        match="image_cache_sha256_mismatch:broker",
    ):
        host._materialize_local_work(runtime, images)


def test_clean_reference_host_has_no_github_large_artifact_download_path() -> None:
    source = Path(host.__file__).read_text(encoding="utf-8")
    assert "_download_artifact(" not in source
    assert "gh run download" not in source
    assert '"docker", "pull"' not in source


def test_executor_is_staged_outside_payload_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "n3w_t1_clean_reference_staging_host.py"
    executor_source = tmp_path / "n3w_t1_clean_reference_executor.py"
    source.write_text("", encoding="utf-8")
    executor_source.write_text("print('executor')\n", encoding="utf-8")

    calls = []

    class Result:
        stdout = host._sha256_file(executor_source) + "  remote\n"
        stderr = ""
        returncode = 0

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        return Result()

    monkeypatch.setattr(host, "__file__", str(source))
    monkeypatch.setattr(host.fresh, "_run", fake_run)

    remote_dir = "/var/tmp/n3w-clean-reference-r1.ABC123"
    remote = host._transfer_executor("root@t1", remote_dir)

    assert remote == remote_dir + ".executor.py"
    assert calls[0][0] == "scp"
    assert calls[0][-1] == "root@t1:" + remote
    assert not remote.startswith(remote_dir + "/")


def test_success_cleanup_removes_payload_tree_and_sibling_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        return Result()

    monkeypatch.setattr(host.fresh, "_run", fake_run)

    remote_dir = "/var/tmp/n3w-clean-reference-r1.ABC123"
    assert host._cleanup_remote("root@t1", remote_dir) is True

    command = calls[0]
    assert command[0:3] == ("ssh", "-n", "root@t1")
    rendered = command[3]
    assert remote_dir in rendered
    assert remote_dir + ".executor.py" in rendered


def test_production_wrapper_still_requires_v2_run_context() -> None:
    source = Path(host.fresh.__file__).read_text(encoding="utf-8")
    assert 'raise FreshHostTransportError("v2_run_context_required")' in source
    assert '"production_marker_sha256"' in source
