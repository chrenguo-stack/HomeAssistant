from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from n3w_t1_core_updater_v2_common import (
    COMPONENTS,
    ComponentTarget,
    UpdaterV2Error,
    V2Host,
)

PEER_RUNTIME_KEYS = (
    "image_ref",
    "image_id",
    "network_mode",
    "runtime_contract_sha256",
)


@dataclass(frozen=True)
class ComponentAdapter:
    component: str

    def __post_init__(self) -> None:
        if self.component not in COMPONENTS:
            raise UpdaterV2Error("component_invalid")

    @property
    def peers(self) -> tuple[str, ...]:
        return tuple(name for name in COMPONENTS if name != self.component)

    def current_binding(self, snapshot: dict[str, Any]) -> str:
        bindings = snapshot.get("image_bindings")
        if not isinstance(bindings, dict):
            raise UpdaterV2Error("image_bindings_missing")
        value = bindings.get(self.component)
        if not isinstance(value, str):
            raise UpdaterV2Error("component_binding_missing")
        return value

    def quiesce(self, host: V2Host) -> None:
        host.quiesce_component(self.component)

    def activate(self, host: V2Host) -> None:
        host.activate_component(self.component)

    def peer_runtime_authority(
        self, snapshot: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        runtime = snapshot.get("runtime")
        if not isinstance(runtime, dict):
            raise UpdaterV2Error("runtime_missing")
        authority: dict[str, dict[str, Any]] = {}
        for peer in self.peers:
            item = runtime.get(peer)
            if not isinstance(item, dict):
                raise UpdaterV2Error("peer_runtime_missing")
            authority[peer] = {
                key: item.get(key)
                for key in PEER_RUNTIME_KEYS
            }
        return authority

    def verify_peer_runtime(
        self,
        snapshot: dict[str, Any],
        authority: dict[str, dict[str, Any]],
    ) -> None:
        runtime = snapshot.get("runtime")
        if not isinstance(runtime, dict):
            raise UpdaterV2Error("runtime_missing")
        for peer, expected in authority.items():
            current = runtime.get(peer)
            if not isinstance(current, dict):
                raise UpdaterV2Error("peer_runtime_missing")
            for key, value in expected.items():
                if current.get(key) != value:
                    raise UpdaterV2Error(
                        f"peer_runtime_drift:{peer}:{key}"
                    )

    def verify_target_runtime(
        self,
        snapshot: dict[str, Any],
        target: ComponentTarget,
        runtime_image_id: str,
        predecessor_network_mode: Any,
    ) -> None:
        binding = self.current_binding(snapshot)
        if binding != target.target_image_ref:
            raise UpdaterV2Error("post_target_binding_invalid")
        runtime = snapshot.get("runtime")
        item = runtime.get(self.component) if isinstance(runtime, dict) else None
        if not isinstance(item, dict):
            raise UpdaterV2Error("post_target_runtime_missing")
        if (
            item.get("image_ref") != target.target_image_ref
            or item.get("image_id") != runtime_image_id
            or item.get("network_mode") != predecessor_network_mode
            or not isinstance(item.get("runtime_contract_sha256"), str)
        ):
            raise UpdaterV2Error("post_target_runtime_invalid")


def adapter_for(component: str) -> ComponentAdapter:
    return ComponentAdapter(component)
