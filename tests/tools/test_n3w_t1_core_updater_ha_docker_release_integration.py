from __future__ import annotations

import json
import os
import subprocess

import pytest

import n3w_t1_core_updater_ha_recovery_startup as recovery_startup


ENABLED = os.environ.get("N3W_DOCKER_RELEASE_INTEGRATION") == "1"
REFERENCE = os.environ.get("N3W_DOCKER_RELEASE_PROBE_IMAGE", "busybox:1.36.1")


def _run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=check, text=True, capture_output=True)


@pytest.mark.skipif(not ENABLED, reason="real Docker release integration is CI-only")
def test_real_docker_engine_removes_single_tag_image_with_same_repository_digest() -> None:
    _run("docker", "image", "rm", "--force", REFERENCE, check=False)
    image_id = None
    try:
        _run("docker", "pull", REFERENCE)
        image = json.loads(_run("docker", "image", "inspect", REFERENCE).stdout)[0]
        assert image["RepoTags"] == [REFERENCE]
        assert image["RepoDigests"]
        assert recovery_startup._exclusive_image_references(image, REFERENCE)

        image_id = image["Id"]
        users = _run(
            "docker", "ps", "--all", "--no-trunc", "--quiet",
            "--filter", f"ancestor={image_id}",
        ).stdout.split()
        assert users == []

        removal = _run("docker", "image", "rm", "--no-prune", image_id, check=False)
        assert removal.returncode == 0, removal.stderr
        assert _run("docker", "image", "inspect", image_id, check=False).returncode != 0
        assert _run("docker", "image", "inspect", REFERENCE, check=False).returncode != 0
    finally:
        if image_id is not None:
            _run("docker", "image", "rm", "--force", image_id, check=False)
        _run("docker", "image", "rm", "--force", REFERENCE, check=False)
