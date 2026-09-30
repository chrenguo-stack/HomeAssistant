# N3-W Gate A Broker runtime-user forensic

## Purpose

This package is a read-only follow-up to the first failed T1 Gate A lab activation.

It exists to test one specific hypothesis without replaying the consumed activation authorization: the temporary lab files were staged as root-owned mode-0700/0600 files, while the exact Mosquitto image may execute its broker process as the non-root `mosquitto` account.

## Read-only evidence

The executor reads only:

- the exact production Broker container selected by the frozen Compose labels;
- the production Broker image metadata;
- `/proc/1/status` inside the running Broker container;
- `/etc/passwd` inside the running Broker container;
- production Broker and Manager running/restart-count state.

`docker exec` is used only for `cat` reads. It does not edit files, restart services, publish MQTT messages or change network state.

## Prohibited operations

The forensic must not:

- start, stop, remove or restart containers;
- add or remove addresses;
- edit T1 files;
- touch the production Broker configuration;
- touch Manager, Home Assistant or Dynamic Security state;
- access or flash Board B.

## Interpretation

If all of the following are proven on the exact production Broker image used by the failed lab attempt:

- `BROKER_PID1_UID == MOSQUITTO_ACCOUNT_UID`;
- `BROKER_PID1_GID == MOSQUITTO_ACCOUNT_GID`;
- the process is the Mosquitto broker;
- the Gate A activation source staged `/run/n3w-gate-a-77b0fd6a` as root-owned `0700` and its TLS/password/config files as root-owned `0600`;

then the activation failure has a concrete permission incompatibility that must be repaired before another live activation attempt.

This package does not itself claim the root cause until the real T1 output is observed.
