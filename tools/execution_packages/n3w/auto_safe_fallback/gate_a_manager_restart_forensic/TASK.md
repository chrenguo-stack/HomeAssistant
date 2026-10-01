# N3-W Gate A Manager restart forensic

## Purpose

This package is a read-only follow-up to the Gate A T1 lab permission forensic.

The first failed Gate A activation was already proven to have cleaned up all temporary lab state while the Manager restart count was still zero. A later read-only permission forensic observed `MANAGER_RESTART_COUNT=1`. Therefore this later Manager restart must be treated as a separate event until evidence shows otherwise.

## Read-only evidence

The executor reads only:

- `docker inspect greenhouse-manager`;
- the exact production Broker selected by frozen Compose labels;
- recent Docker events for `greenhouse-manager` over the last 72 hours;
- `/proc/uptime`.

It reports current running state, restart count, start/finish timestamps, OOM flag, current exit code, restart policy, bounded recent container lifecycle events, Broker continuity, and host uptime.

## Prohibited operations

The forensic must not:

- start, stop, restart, remove, or create containers;
- add or remove IP addresses;
- edit T1 files;
- read or print MQTT credentials;
- mutate Broker, Manager, Dynamic Security, or Home Assistant state;
- access or flash Board B.

## Interpretation

The result may establish when the Manager restart occurred and whether Docker recorded a die/restart/start sequence, OOM event, exit code, or signal. If the event history is unavailable or incomplete, the package must not invent a cause.
