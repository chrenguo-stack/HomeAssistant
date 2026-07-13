from __future__ import annotations

import json

import pytest

from greenhouse_manager.t1_manager_runtime_secret_ownership import (
    ManagerRuntimeSecretOwnershipError,
    resolve_manager_runtime_identity,
    verify_bound_runtime_identity,
)


class FakeRunner:
    def __init__(self, *, image_user: str = "999:999", effective: str = "999:999") -> None:
        self.image_user = image_user
        self.effective = effective
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command[:3] == ("docker", "image", "inspect"):
            return 0, json.dumps([{"Config": {"User": self.image_user}}])
        if command[:3] == ("docker", "run", "--rm"):
            return 0, self.effective + "\n"
        return 1, "unexpected command"


def _document(user: str = "999:999") -> dict[str, object]:
    return {
        "Image": "sha256:manager-image-id",
        "Config": {"User": user},
    }


def test_resolves_non_root_identity_from_three_consistent_sources() -> None:
    runner = FakeRunner()

    result = resolve_manager_runtime_identity(_document(), runner)

    assert result == {
        "manager_runtime_uid": 999,
        "manager_runtime_gid": 999,
        "manager_runtime_user_source": "container+image+isolated-candidate",
        "manager_runtime_image_id": "sha256:manager-image-id",
        "manager_runtime_user_spec": "999:999",
    }
    assert runner.commands[1][:7] == (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
    )
    assert "no-new-privileges" in runner.commands[1]


def test_rejects_container_image_user_disagreement() -> None:
    with pytest.raises(
        ManagerRuntimeSecretOwnershipError,
        match="container and image user bindings disagree",
    ):
        resolve_manager_runtime_identity(_document("999:999"), FakeRunner(image_user="998:998"))


def test_rejects_root_effective_identity() -> None:
    with pytest.raises(ManagerRuntimeSecretOwnershipError, match="must not be root"):
        resolve_manager_runtime_identity(_document("0:0"), FakeRunner(image_user="0:0", effective="0:0"))


def test_bound_identity_rejects_image_or_user_drift() -> None:
    binding = resolve_manager_runtime_identity(_document(), FakeRunner())

    assert verify_bound_runtime_identity(
        binding,
        image_id="sha256:manager-image-id",
        user_spec="999:999",
    ) == (999, 999)

    with pytest.raises(ManagerRuntimeSecretOwnershipError, match="image drifted"):
        verify_bound_runtime_identity(
            binding,
            image_id="sha256:different-image",
            user_spec="999:999",
        )
