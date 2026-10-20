from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load(
    "n3w_t1_production_v2_contract_release_builder",
    "n3w_t1_production_v2_contract.py",
)
builder = load(
    "n3w_t1_f5_v2_release_builder_test",
    "n3w_t1_f5_v2_release_builder.py",
)


def write_inputs(tmp_path: Path) -> Path:
    artifacts = {}
    for index, name in enumerate(sorted(contract.REQUIRED_RELEASE_ARTIFACTS), start=1):
        path = tmp_path / f"{name}.bin"
        path.write_bytes((name + "\n").encode() * index)
        artifacts[name] = path.name
    head, tree = exact_source()
    document = {
        "schema": builder.INPUT_SCHEMA,
        "source_head": head,
        "source_tree": tree,
        "os_contract": {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
            "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
            "BOARD": "S912-Phicomm-T1",
            "BOARD_NAME": "Aml.S912",
            "VERSION": "26.05.0",
            "BRANCH": "current",
            "ARCH": "arm64",
            "IMAGE_TYPE": "rebuild",
            "kernel_arch": "aarch64",
        },
        "packages": {
            "docker.io": "29.1.3-0ubuntu4.1",
            "docker-compose-v2": "2.40.3+ds1-0ubuntu1",
        },
        "apt_source_policy": {
            "host": "ports.ubuntu.com",
            "suite": "resolute",
            "component": "universe",
            "architecture": "arm64",
        },
        "artifacts": artifacts,
        "capacity": {"minimum_post_peak_free_bytes": 5 * 1024**3},
        "public_evidence_fields": [
            "status",
            "release_id",
            "source_head",
            "run_id_sha256",
        ],
    }
    path = tmp_path / "release-inputs.json"
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    return path


def exact_source():
    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"],
        text=True,
    ).strip()
    return head, tree


def test_builder_binds_exact_source_and_every_required_artifact(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    destination = tmp_path / "release"
    report = builder.build_release(
        ROOT,
        inputs,
        destination,
        source_head=head,
        source_tree=tree,
        production_authority=False,
    )
    verified = builder.verify_release_directory(destination)
    manifest = json.loads(
        (destination / builder.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert report["status"] == "PASS"
    assert report["production_authority"] is False
    assert report["source_head"] == head
    assert report["source_tree"] == tree
    assert set(manifest["artifacts"]) == set(contract.REQUIRED_RELEASE_ARTIFACTS)
    assert verified["release_sha256"] == report["release_sha256"]


def test_builder_is_deterministic_for_same_source_and_inputs(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    first = builder.build_release(
        ROOT,
        inputs,
        tmp_path / "first",
        source_head=head,
        source_tree=tree,
    )
    second = builder.build_release(
        ROOT,
        inputs,
        tmp_path / "second",
        source_head=head,
        source_tree=tree,
    )
    assert first["release_id"] == second["release_id"]
    assert first["release_sha256"] == second["release_sha256"]


def test_verify_rejects_artifact_tamper(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    destination = tmp_path / "release"
    builder.build_release(
        ROOT,
        inputs,
        destination,
        source_head=head,
        source_tree=tree,
    )
    target = destination / builder.ARTIFACT_DIR / "f3_payload"
    target.write_bytes(target.read_bytes() + b"tamper")
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_artifact_binding_invalid:f3_payload",
    ):
        builder.verify_release_directory(destination)


def test_production_authority_requires_exact_origin_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    original = builder._git

    def fake_git(repository, *args):
        if args == ("rev-parse", "origin/main"):
            return "0" * 40
        return original(repository, *args)

    monkeypatch.setattr(builder, "_git", fake_git)
    with pytest.raises(
        builder.ReleaseBuildError,
        match="production_source_not_exact_merged_main",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
            production_authority=True,
        )


def test_inputs_cannot_escape_artifact_root(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    document = json.loads(inputs.read_text(encoding="utf-8"))
    document["artifacts"]["f3_payload"] = "../outside"
    inputs.write_text(json.dumps(document) + "\n", encoding="utf-8")
    head, tree = exact_source()
    with pytest.raises(
        builder.ReleaseBuildError,
        match="artifact_path_escape:f3_payload",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
        )



def test_builder_rejects_release_inputs_from_different_source(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    document = json.loads(inputs.read_text(encoding="utf-8"))
    document["source_head"] = "0" * 40
    inputs.write_text(json.dumps(document) + "\n", encoding="utf-8")
    head, tree = exact_source()
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_inputs_source_head_mismatch",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
        )


def test_builder_rejects_symlinked_artifact_input(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    document = json.loads(inputs.read_text(encoding="utf-8"))
    real = tmp_path / "real.bin"
    real.write_bytes(b"real")
    link = tmp_path / "linked.bin"
    link.symlink_to(real)
    document["artifacts"]["f3_payload"] = link.name
    inputs.write_text(json.dumps(document) + "\n", encoding="utf-8")
    head, tree = exact_source()
    with pytest.raises(
        builder.ReleaseBuildError,
        match="artifact_source_symlink:f3_payload",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
        )
