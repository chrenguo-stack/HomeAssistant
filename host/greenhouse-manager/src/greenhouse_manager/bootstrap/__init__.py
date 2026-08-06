"""First-initialization and portable recovery lifecycle."""

from greenhouse_manager.bootstrap.anonymous_closure import (
    AnonymousClosureError,
    AnonymousClosureReport,
    validate_anonymous_closure_policy,
)
from greenhouse_manager.bootstrap.identity_guard import (
    IdentityConflictError,
    claim_identity,
    inspect_identity,
    release_identity,
)
from greenhouse_manager.bootstrap.persistence_migration import (
    PersistenceMigrationError,
    PersistenceMigrationPlan,
    build_persistence_migration_plan,
    load_audited_baseline,
)
from greenhouse_manager.bootstrap.portable_restore import (
    PortableBackupReport,
    PortableRestoreError,
    PortableRestoreReport,
    create_portable_backup,
    restore_portable_backup,
    verify_portable_backup,
)
from greenhouse_manager.bootstrap.system_init import (
    InitializationError,
    InitializationReport,
    initialize_system,
    verify_initialization,
)

__all__ = [
    "AnonymousClosureError",
    "AnonymousClosureReport",
    "IdentityConflictError",
    "InitializationError",
    "InitializationReport",
    "PersistenceMigrationError",
    "PersistenceMigrationPlan",
    "PortableBackupReport",
    "PortableRestoreError",
    "PortableRestoreReport",
    "build_persistence_migration_plan",
    "claim_identity",
    "create_portable_backup",
    "initialize_system",
    "inspect_identity",
    "load_audited_baseline",
    "release_identity",
    "restore_portable_backup",
    "validate_anonymous_closure_policy",
    "verify_initialization",
    "verify_portable_backup",
]
