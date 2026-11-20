# KF-168 Manager OTA IPC export isolation

Status: SOURCE_REVIEW_ONLY. Live deployment and Phase-A acceptance pending.

## Confirmed fault

Manager's read-only recursive bind of the entire OTA runtime directory
retained the writable ext4 superblock of a recovery USB submount. The
isolated strict read-only mount reproduced exit 32/device busy. The
retained live bind was removed once, without a service restart.

- [Root-cause evidence](https://github.com/chrenguo-stack/HomeAssistant/blob/b726c7d14732e4a73568ada4c0ad29a59a2f8e27/docs/development/N3W_T1_KF168_MANAGER_RECURSIVE_BIND_USB_EBUSY_ROOT_CAUSE_20261120.md)
- [Exact cleanup evidence](https://github.com/chrenguo-stack/HomeAssistant/blob/b828ccab36416d3152e3a5eff85236d7810bb793/docs/development/N3W_T1_KF168_EXACT_MANAGER_RETAINED_USB_UNMOUNT_PASS_20261120.md)

## Frozen layout

| Role | Host path | Manager view |
| --- | --- | --- |
| Private OTA workspace and recovery media | `/run/n3w-t1-ota`, including `media/` | None |
| Read-only IPC export | `/run/n3w-t1-ota-ipc` | `/run/n3w/t1-ota` |
| Host compatibility socket | `/run/n3w-t1-ota/ha-ota.sock` | None |

The export contains the canonical `ha-ota.sock` and the published
`approved-homeassistant.json`. Temporary manifest files, if present
while publishing, are in that same directory so replacement is atomic.
The existing in-container client paths stay the same. The daemon retains
root:999, its socket mode 0660 and its UID 999 peer check. The compatibility
symlink points to the canonical host endpoint. The daemon refuses to
overwrite a foreign file or symlink at that legacy path.

The systemd pre-start step creates or reuses the root-owned 0750 IPC
directory before the existing Manager activation dependency is satisfied.
The directory is outside systemd's automatically removed recovery
RuntimeDirectory, so a bound Manager can see a new socket and the
atomically published manifest across a daemon restart. The post-stop
step removes only a root-owned stale socket at the canonical location.
Compose fails if systemd has not prepared the bind source.

## Validation and deployment gates

1. Validate the unit, Compose configuration and compatibility alias
   locally. In a disposable Linux mount namespace, reproduce the old
   recursive bind and verify exit 32 with a writable superblock. Verify
   that the separated export no longer pins the USB while Manager starts
   with media present. Require a strict fresh read-only ext4 mount and
   the same bound view to receive a newly created socket and atomically
   replaced manifest after daemon socket restart.
2. Bind the source, tests and dependent manifests by commit and pass
   applicable CI. The carried P3 and Phase-A manifests are for source
   verification. Their historical execution grants remain consumed.
3. Before any deployment, rebind the actual service unit, overlay, daemon,
   socket paths, candidate override, transaction and affected services.
   Stage the daemon, unit and Compose overlay as a coordinated change.
   A daemon-only replacement cannot create the new export contract, and
   an overlay-only replacement does not publish the required endpoints.
   Define the affected service operations, rollback artifacts and stop
   conditions against that exact release. Do not reuse the previous
   one-file or cleanup grants.
4. Verify Manager's mount namespace excludes the bound USB and that its
   normal IPC client can reach the new endpoint after activation. Require
   `ROLLED_BACK` with a null error, durable Host/USB agreement, and healthy
   business runtime before declaring Phase-A PASS. A rollback restores
   the prior daemon, unit and overlay together after checking that no
   recovery USB is mounted. The legacy compatibility link is owned by
   the private runtime directory lifecycle.
