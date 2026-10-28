# N3W Scan-Triggered First Pairing R10 — Physical Acceptance Execution Progress

Date: 2026-10-28

Gate:

\`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_EXECUTION_20261028_01\`

## Authorization

The user explicitly authorized the R10 physical acceptance gate after the R10 design/read-only preflight passed.

The authorization permits entering T1/board physical work only through the frozen sequence:
1. T1 + target-board read-only preflight;
2. only after all read-only preconditions pass, enter the separately protected write phase;
3. then perform the real scan-triggered first-registration acceptance.

No write authorization has yet been consumed.

## Current physical state

At this progress point:
- T1 has not been accessed in this R10 execution gate;
- no board serial port has been opened in this R10 execution gate;
- no flash write has occurred;
- no NVS write/erase has occurred;
- no T1 runtime mutation has occurred;
- no Manager/Broker/Home Assistant restart/recreate has occurred.

## Additional write-route safety finding

The R9 exact \`firmware.factory.bin\` is a merged image from offset 0 with size 1,525,680 bytes.

Fresh byte-level review before the first physical write found:
- it reaches through the PHY-init sector at \`0x00b000\`;
- the factory image contains all-\`FF\` bytes for that PHY sector;
- it contains the app0 R9 application;
- it does not reach app1 at \`0x3d0000\`;
- it does not reach NVS at \`0x790000\`.

Therefore a direct factory write is safe only if fresh target evidence proves:
- the current PHY sector is already all-\`FF\`; and
- app1 already contains the R9 application.

Otherwise direct factory writing could either erase non-empty PHY data or leave stale application bytes in app1.

This is not yet a proven board defect. It is a prewrite route-admission condition.

## R10 read-only execution package

A dedicated repository-owned read-only executor is being used instead of the historical manual onboarding tool.

The executor:
- binds the exact R9 artifact and member hashes;
- checks T1 services/containers without restarting them;
- checks trusted-product-LAN state;
- requires 47110/tcp and 47111/udp ready and 47112/tcp idle closed;
- checks the Manager has the R1-R3 first-registration capability;
- queries the Manager DB read-only for unresolved first-registration predecessors;
- checks the Manager pairing window is CLOSED;
- observes ESP32-C6/8MB/security state;
- hashes the board identity without publishing the raw ROM MAC;
- validates the live partition table before wider reads;
- privately backs up the factory-covered range, full app1 slot and complete NVS;
- checks the live PHY/app0/app1 disposition;
- contains no flash-write or erase command;
- leaves write authorization unconsumed.

If the direct factory route is not eligible, the executor stops before mutation and requires a reviewed write-route decision.

## Current route

Continue with:
- source/test/CI review of the read-only executor;
- then one operator-run Mac/T1/board read-only preflight;
- archive only public-safe results.

Do not enter flashing until that fresh preflight result is known.
