from __future__ import annotations

import os
import secrets
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .dynsec_api import DynsecError
from .t1_backup import _extract_verified
from .t1_broker_identity_activation_checks import (
    Runner,
    Verifier,
    read_json,
    sha256_path,
    validated_handoff,
)
from .t1_broker_identity_activation_handoff import (
    verify_broker_identity_activation_handoff,
)
from .t1_broker_identity_isolated_helpers import (
    _CANDIDATE_NAME,
    BrokerIdentityIsolatedTransactionError,
    _active_config_lines,
    _anonymous_control_denied,
    _anonymous_enabled,
    _anonymous_retained,
    _ha_config,
    _identity_retained,
    _list_clients,
    _private_file,
    _request_commands,
    _safe_relative,
    _sha,
    _tree_inventory,
)
from .t1_migration_stage import verify_migration_stage
from .t1_shadow import (
    PLUGIN_CONFIG_LINE,
    PLUGIN_LINE,
    PLUGIN_PASSWORD_INIT_LINE,
    SubprocessRunner,
    _mount,
    _prepare_snapshot_directories,
    _require_success,
    _wait_for_file,
    prepare_shadow_config,
)
from .t1_shadow_services import MosquittoRRTransport

MUTATION_SCHEMA = "gh.m2.t1-broker-identity-isolated-mutation/1"
POSTACTIVATION_SCHEMA = "gh.m2.t1-broker-identity-isolated-postactivation/1"
ROLLBACK_SCHEMA = "gh.m2.t1-broker-identity-isolated-rollback/1"

FAULT_PHASES = (
    "after_snapshot_write",
    "mosquitto_start",
    "dynamic_security_init",
    "after_exact_request",
    "provisioning",
    "bootstrap_delete",
    "postactivation",
    "rollback_incomplete",
)

_REQUIRED_MATERIAL = (
    "material/broker/dynsec-request.json",
    "material/broker/mosquitto-plugin.conf",
    "material/bootstrap/dynsec-password-init",
    "material/bootstrap/admin-client.conf",
    "material/provisioning/mosquitto-client.conf",
    "material/homeassistant/mqtt-update.json",
)

NameFactory = Callable[[], str]
StageVerifier = Callable[[str | Path], dict[str, Any]]
BackupExtractor = Callable[[Path, Path], dict[str, Any]]
WaitForFile = Callable[..., bool]


class IsolatedBrokerIdentitySnapshotAdapters:
    def __init__(
        self,
        handoff_directory: str | Path,
        stage_directory: str | Path,
        *,
        expected_retained_topic: str,
        runner: Runner | None = None,
        fault_phase: str | None = None,
        name_factory: NameFactory | None = None,
        handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
        stage_verifier: StageVerifier = verify_migration_stage,
        backup_extractor: BackupExtractor = _extract_verified,
        wait_for_file: WaitForFile = _wait_for_file,
    ) -> None:
        if not expected_retained_topic.startswith("gh/"):
            raise ValueError("expected retained topic must be in the gh namespace")
        if fault_phase is not None and fault_phase not in FAULT_PHASES:
            raise ValueError("unsupported isolated transaction fault phase")
        self.handoff = Path(handoff_directory).expanduser().resolve()
        self.stage = Path(stage_directory).expanduser().resolve()
        self.expected_retained_topic = expected_retained_topic
        self.runner = runner or SubprocessRunner()
        self.fault_phase = fault_phase
        self.name_factory = name_factory
        self.handoff_verifier = handoff_verifier
        self.stage_verifier = stage_verifier
        self.backup_extractor = backup_extractor
        self.wait_for_file = wait_for_file

        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._workspace: Path | None = None
        self._baseline: Path | None = None
        self._working: Path | None = None
        self._rollback_archive: Path | None = None
        self._image_id: str | None = None
        self._baseline_inventory: tuple[tuple[str, int, str], ...] | None = None
        self._baseline_config_sha256: str | None = None
        self._candidate_name: str | None = None
        self._candidate_created = False
        self._snapshot_mutation_started = False
        self._mutation_report: dict[str, object] | None = None
        self._source_inventory_before: tuple[
            tuple[str, int, str], ...
        ] | None = None

    def __enter__(self) -> IsolatedBrokerIdentitySnapshotAdapters:
        self._prepare()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _phase(self, phase: str) -> None:
        if self.fault_phase == phase:
            raise BrokerIdentityIsolatedTransactionError(
                f"injected isolated transaction fault: {phase}"
            )

    def _new_candidate_name(self, suffix: str = "candidate") -> str:
        if self.name_factory is not None:
            name = self.name_factory()
        else:
            name = f"gh-m2-isolated-{suffix}-{secrets.token_hex(4)}"
        if _CANDIDATE_NAME.fullmatch(name) is None:
            raise BrokerIdentityIsolatedTransactionError(
                "isolated candidate name is invalid"
            )
        if name == "mosquitto":
            raise BrokerIdentityIsolatedTransactionError(
                "isolated candidate cannot target the live Broker"
            )
        return name

    def _validate_sources(self) -> tuple[dict[str, Any], Path]:
        if (
            not self.handoff.is_dir()
            or self.handoff.is_symlink()
            or not self.stage.is_dir()
            or self.stage.is_symlink()
        ):
            raise BrokerIdentityIsolatedTransactionError(
                "isolated transaction source directory is unsafe"
            )
        manifest, _plan = validated_handoff(
            self.handoff,
            self.handoff_verifier,
        )
        stage_manifest = self.stage_verifier(self.stage)
        if (
            stage_manifest.get("activation_enabled") is not False
            or stage_manifest.get("current_services_modified") is not False
            or stage_manifest.get("active_paths_modified") is not False
        ):
            raise BrokerIdentityIsolatedTransactionError(
                "migration stage is not an inactive source"
            )
        stage_record = manifest.get("stage")
        if not isinstance(stage_record, dict):
            raise BrokerIdentityIsolatedTransactionError(
                "activation handoff stage binding is missing"
            )
        stage_manifest_path = self.stage / "stage-manifest.json"
        if (
            stage_record.get("name") != self.stage.name
            or stage_record.get("manifest_sha256")
            != sha256_path(stage_manifest_path)
        ):
            raise BrokerIdentityIsolatedTransactionError(
                "activation handoff stage binding has drifted"
            )
        for relative in _REQUIRED_MATERIAL:
            _private_file(
                self.handoff / relative,
                f"activation handoff material {relative}",
            )
        fresh = manifest.get("fresh_rollback")
        if not isinstance(fresh, dict):
            raise BrokerIdentityIsolatedTransactionError(
                "fresh rollback record is missing"
            )
        relative = _safe_relative(fresh.get("path"), "fresh rollback")
        rollback = self.handoff.joinpath(*relative.parts)
        _private_file(rollback, "fresh rollback archive")
        if fresh.get("sha256") != _sha(rollback):
            raise BrokerIdentityIsolatedTransactionError(
                "fresh rollback fingerprint has drifted"
            )
        return manifest, rollback

    def _prepare(self) -> None:
        if self._workspace is not None:
            return
        manifest, rollback = self._validate_sources()
        self._source_inventory_before = (
            _tree_inventory(self.handoff) + _tree_inventory(self.stage)
        )
        self._temporary = tempfile.TemporaryDirectory(
            prefix="gh-m2-isolated-transaction-"
        )
        workspace = Path(self._temporary.name)
        workspace.chmod(0o700)
        baseline = workspace / "baseline"
        working = workspace / "working"
        baseline.mkdir(mode=0o700)
        rollback_manifest = self.backup_extractor(rollback, baseline)
        shutil.copytree(baseline, working, copy_function=shutil.copy2)

        config = baseline / "mosquitto-config/mosquitto.conf"
        data = baseline / "mosquitto-data"
        if not config.is_file() or not data.is_dir():
            raise BrokerIdentityIsolatedTransactionError(
                "fresh rollback snapshot is incomplete"
            )
        stage_record = manifest["stage"]
        if config.is_symlink() or _sha(config) != stage_record.get(
            "broker_config_sha256"
        ):
            raise BrokerIdentityIsolatedTransactionError(
                "fresh rollback Broker configuration is not bound to the handoff"
            )
        image_id = (
            rollback_manifest.get("sources", {})
            .get("mosquitto", {})
            .get("image_id")
        )
        if not isinstance(image_id, str) or not image_id:
            raise BrokerIdentityIsolatedTransactionError(
                "fresh rollback Mosquitto image binding is missing"
            )

        self._workspace = workspace
        self._baseline = baseline
        self._working = working
        self._rollback_archive = rollback
        self._image_id = image_id
        self._baseline_inventory = _tree_inventory(baseline)
        self._baseline_config_sha256 = _sha(config)

    def _require_prepared(self) -> tuple[Path, Path, str]:
        self._prepare()
        if self._baseline is None or self._working is None or self._image_id is None:
            raise BrokerIdentityIsolatedTransactionError(
                "isolated snapshot workspace is unavailable"
            )
        return self._baseline, self._working, self._image_id

    def _remove_candidate(self) -> None:
        if self._candidate_name is None:
            return
        self.runner.run(("docker", "rm", "-f", self._candidate_name))
        code, _output = self.runner.run(
            ("docker", "inspect", self._candidate_name)
        )
        if code == 0:
            raise BrokerIdentityIsolatedTransactionError(
                "isolated candidate container remained after cleanup"
            )
        self._candidate_created = False
        self._candidate_name = None

    def _copy_candidate_config(self, source: Path, destination: str) -> None:
        _require_success(
            self.runner,
            (
                "docker",
                "cp",
                "--archive",
                str(source),
                f"{self._candidate_name}:{destination}",
            ),
            "isolated candidate client configuration copy failed",
        )

    def mutation_executor(
        self,
        handoff_directory: Path,
        runner: Runner,
    ) -> dict[str, object]:
        if handoff_directory.resolve() != self.handoff or runner is not self.runner:
            raise BrokerIdentityIsolatedTransactionError(
                "isolated mutation adapter binding is invalid"
            )
        _baseline, working, image_id = self._require_prepared()
        config_dir = working / "mosquitto-config"
        data_dir = working / "mosquitto-data"
        config_path = config_dir / "mosquitto.conf"
        dynsec_path = data_dir / "dynamic-security.json"
        if dynsec_path.exists():
            raise BrokerIdentityIsolatedTransactionError(
                "isolated working snapshot already has Dynamic Security state"
            )

        candidate_name = self._new_candidate_name()

        plugin_lines = _active_config_lines(
            self.handoff / "material/broker/mosquitto-plugin.conf"
        )
        if plugin_lines != (
            PLUGIN_LINE,
            PLUGIN_CONFIG_LINE,
            PLUGIN_PASSWORD_INIT_LINE,
        ):
            raise BrokerIdentityIsolatedTransactionError(
                "activation handoff plugin configuration is not canonical"
            )
        self._snapshot_mutation_started = True
        prepare_shadow_config(config_path)
        _prepare_snapshot_directories(config_dir, data_dir)
        password_init = config_dir / "dynsec-password-init"
        password_init.write_bytes(
            (
                self.handoff
                / "material/bootstrap/dynsec-password-init"
            ).read_bytes()
        )
        password_init.chmod(0o644)
        self._phase("after_snapshot_write")

        self._candidate_name = candidate_name
        output = _require_success(
            self.runner,
            (
                "docker",
                "create",
                "--network",
                "none",
                "--name",
                candidate_name,
                "--mount",
                _mount(config_dir, "/mosquitto/config"),
                "--mount",
                _mount(data_dir, "/mosquitto/data"),
                image_id,
            ),
            "isolated candidate container could not be created",
        )
        self._candidate_created = True
        if output.strip() and output.strip() != candidate_name:
            self._candidate_name = output.strip()
        self._phase("mosquitto_start")
        _require_success(
            self.runner,
            ("docker", "start", self._candidate_name),
            "isolated candidate Broker did not start",
        )
        state = _require_success(
            self.runner,
            (
                "docker",
                "inspect",
                "-f",
                "{{.State.Status}}",
                self._candidate_name,
            ),
            "isolated candidate state could not be inspected",
        ).strip()
        if state != "running":
            raise BrokerIdentityIsolatedTransactionError(
                "isolated candidate Broker is not running"
            )
        self._phase("dynamic_security_init")
        if not self.wait_for_file(dynsec_path):
            raise BrokerIdentityIsolatedTransactionError(
                "isolated Dynamic Security state was not created"
            )
        owner = data_dir.stat()
        state_owner = dynsec_path.stat()
        if (state_owner.st_uid, state_owner.st_gid) != (
            owner.st_uid,
            owner.st_gid,
        ):
            os.chown(dynsec_path, owner.st_uid, owner.st_gid)
        dynsec_path.chmod(0o600)
        password_init.unlink(missing_ok=True)

        admin_container_path = "/tmp/gh-m2-isolated-admin.conf"
        provisioning_container_path = "/tmp/gh-m2-isolated-provisioning.conf"
        self._copy_candidate_config(
            self.handoff / "material/bootstrap/admin-client.conf",
            admin_container_path,
        )
        self._copy_candidate_config(
            self.handoff / "material/provisioning/mosquitto-client.conf",
            provisioning_container_path,
        )
        bootstrap = MosquittoRRTransport(
            self.runner,
            self._candidate_name,
            admin_container_path,
        )
        bootstrap.execute(
            _request_commands(
                self.handoff / "material/broker/dynsec-request.json"
            )
        )
        self._phase("after_exact_request")

        provisioning = MosquittoRRTransport(
            self.runner,
            self._candidate_name,
            provisioning_container_path,
        )
        self._phase("provisioning")
        responses = provisioning.execute(({"command": "listClients"},))
        if not responses or responses[0].get("command") != "listClients":
            raise BrokerIdentityIsolatedTransactionError(
                "isolated provisioning identity could not manage the candidate"
            )
        self._phase("bootstrap_delete")
        provisioning.execute(
            ({"command": "deleteClient", "username": "admin"},)
        )
        try:
            bootstrap.execute(({"command": "listClients"},))
        except DynsecError:
            pass
        else:
            raise BrokerIdentityIsolatedTransactionError(
                "isolated bootstrap administrator remained usable"
            )
        responses = provisioning.execute(({"command": "listClients"},))
        if not responses or responses[0].get("command") != "listClients":
            raise BrokerIdentityIsolatedTransactionError(
                "isolated provisioning identity failed after bootstrap removal"
            )

        report = {
            "schema": MUTATION_SCHEMA,
            "mutation_started": True,
            "mosquitto_restarted": True,
            "bootstrap_admin_removed": True,
            "provisioning_identity_verified": True,
            "network": "none",
            "isolated_snapshot": True,
            "active_paths_modified": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }
        self._mutation_report = report
        return report

    def postactivation_auditor(
        self,
        handoff_directory: Path,
        runner: Runner,
    ) -> dict[str, object]:
        if (
            handoff_directory.resolve() != self.handoff
            or runner is not self.runner
            or self._candidate_name is None
            or self._mutation_report is None
            or self._working is None
        ):
            raise BrokerIdentityIsolatedTransactionError(
                "isolated postactivation adapter binding is invalid"
            )
        self._phase("postactivation")
        config_path = self._working / "mosquitto-config/mosquitto.conf"
        dynsec_path = self._working / "mosquitto-data/dynamic-security.json"
        lines = _active_config_lines(config_path)
        update = read_json(
            self.handoff / "material/homeassistant/mqtt-update.json",
            "isolated Home Assistant identity",
        )
        provisioning = (
            self.handoff / "material/provisioning/mosquitto-client.conf"
        ).read_text(encoding="utf-8")
        bootstrap = (
            self.handoff / "material/bootstrap/admin-client.conf"
        ).read_text(encoding="utf-8")
        correct = _ha_config(update)
        wrong = _ha_config(
            update,
            f"{update['required_client_id']}-wrong",
        )
        mode = (
            format(dynsec_path.stat().st_mode & 0o777, "03o")
            if dynsec_path.is_file()
            else "missing"
        )
        checks = {
            "candidate_running": _require_success(
                self.runner,
                (
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Status}}",
                    self._candidate_name,
                ),
                "isolated candidate cannot be inspected",
            ).strip()
            == "running",
            "broker_config_changed_from_baseline": (
                self._baseline_config_sha256 is not None
                and _sha(config_path) != self._baseline_config_sha256
            ),
            "dynamic_security_plugin_configured": all(
                line in lines
                for line in (
                    PLUGIN_LINE,
                    PLUGIN_CONFIG_LINE,
                    PLUGIN_PASSWORD_INIT_LINE,
                )
            ),
            "dynamic_security_state_present_private": mode == "600",
            "anonymous_compatibility_enabled": _anonymous_enabled(lines),
            "anonymous_retained_state_readable": _anonymous_retained(
                self.runner,
                self._candidate_name,
                self.expected_retained_topic,
            ),
            "homeassistant_identity_retained_state_readable": (
                _identity_retained(
                    self.runner,
                    self._candidate_name,
                    correct,
                    self.expected_retained_topic,
                )
            ),
            "homeassistant_wrong_client_id_rejected": not _identity_retained(
                self.runner,
                self._candidate_name,
                wrong,
                self.expected_retained_topic,
            ),
            "provisioning_control_readable": _list_clients(
                self.runner,
                self._candidate_name,
                provisioning,
            ),
            "bootstrap_admin_rejected": not _list_clients(
                self.runner,
                self._candidate_name,
                bootstrap,
            ),
            "anonymous_control_denied": _anonymous_control_denied(
                self.runner,
                self._candidate_name,
            ),
        }
        verified = all(checks.values())
        report = {
            "schema": POSTACTIVATION_SCHEMA,
            "checks": checks,
            "activation_verified": verified,
            "rollback_required": not verified,
            "broker_identity_activated": verified,
            "ready_for_homeassistant_reconfigure_handoff": verified,
            "network": "none",
            "isolated_snapshot": True,
            "active_paths_modified": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }
        if verified:
            self._remove_candidate()
        return report

    def _probe_restored_snapshot(self, restored: Path, image_id: str) -> bool:
        probe = self._workspace / "rollback-probe"  # type: ignore[operator]
        shutil.copytree(restored, probe, copy_function=shutil.copy2)
        config_dir = probe / "mosquitto-config"
        data_dir = probe / "mosquitto-data"
        _prepare_snapshot_directories(config_dir, data_dir)
        candidate = self._new_candidate_name("rollback")
        self._candidate_name = candidate
        output = _require_success(
            self.runner,
            (
                "docker",
                "create",
                "--network",
                "none",
                "--name",
                candidate,
                "--mount",
                _mount(config_dir, "/mosquitto/config"),
                "--mount",
                _mount(data_dir, "/mosquitto/data"),
                image_id,
            ),
            "rollback probe container could not be created",
        )
        self._candidate_created = True
        if output.strip() and output.strip() != candidate:
            self._candidate_name = output.strip()
        try:
            _require_success(
                self.runner,
                ("docker", "start", self._candidate_name),
                "rollback probe Broker did not start",
            )
            state = _require_success(
                self.runner,
                (
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Status}}",
                    self._candidate_name,
                ),
                "rollback probe state could not be inspected",
            ).strip()
            if state != "running":
                return False
            return _anonymous_retained(
                self.runner,
                self._candidate_name,
                self.expected_retained_topic,
            )
        finally:
            self._remove_candidate()
            shutil.rmtree(probe, ignore_errors=True)

    def rollback_executor(
        self,
        handoff_directory: Path,
        runner: Runner,
    ) -> dict[str, object]:
        if handoff_directory.resolve() != self.handoff or runner is not self.runner:
            raise BrokerIdentityIsolatedTransactionError(
                "isolated rollback adapter binding is invalid"
            )
        baseline, working, image_id = self._require_prepared()
        self._remove_candidate()
        shutil.rmtree(working, ignore_errors=True)
        shutil.copytree(baseline, working, copy_function=shutil.copy2)
        config = working / "mosquitto-config/mosquitto.conf"
        dynsec = working / "mosquitto-data/dynamic-security.json"
        baseline_restored = (
            self._baseline_inventory is not None
            and _tree_inventory(working) == self._baseline_inventory
            and self._baseline_config_sha256 == _sha(config)
        )
        dynamic_security_absent = not dynsec.exists() and not any(
            line.startswith(("plugin ", "global_plugin ", "auth_plugin "))
            for line in _active_config_lines(config)
        )
        retained_readable = self._probe_restored_snapshot(working, image_id)
        self._phase("rollback_incomplete")
        if not (
            baseline_restored
            and dynamic_security_absent
            and retained_readable
        ):
            raise BrokerIdentityIsolatedTransactionError(
                "isolated rollback verification is incomplete"
            )
        return {
            "schema": ROLLBACK_SCHEMA,
            "rollback_completed": True,
            "baseline_config_restored": True,
            "dynamic_security_state_absent": True,
            "anonymous_retained_state_readable": True,
            "candidate_cleanup_verified": True,
            "network": "none",
            "isolated_snapshot": True,
            "active_paths_modified": False,
            "current_services_modified": False,
        }

    @property
    def snapshot_mutation_started(self) -> bool:
        return self._snapshot_mutation_started

    def sources_unchanged(self) -> bool:
        if self._source_inventory_before is None:
            return False
        return self._source_inventory_before == (
            _tree_inventory(self.handoff) + _tree_inventory(self.stage)
        )

    def close(self) -> None:
        cleanup_error: Exception | None = None
        try:
            self._remove_candidate()
        except Exception as error:  # pragma: no cover - defensive cleanup
            cleanup_error = error
        if self._temporary is not None:
            self._temporary.cleanup()
        self._temporary = None
        self._workspace = None
        self._baseline = None
        self._working = None
        if cleanup_error is not None:
            raise cleanup_error
