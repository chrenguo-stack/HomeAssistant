# N3W R1R4 USB Console Evidence Hardening Plan

This is a host-only successor diagnostic build. It does not authorize a physical run.

```text
PARENT_R1R3_DIAGNOSTIC=56d0ec6dcc633f3966affc68a9342716490e370e
TRIGGER=TWO_PHYSICAL_R1R3_RUNS_NOT_ADJUDICABLE_DUE_TO_SERIAL_EVIDENCE_FAILURE
LATEST_CAPTURE_FACTS=
both real ports opened
both helper processes alive
both output files created
both final logs zero bytes
ROOT_CAUSE_PROVEN=false
R1R4_SCOPE=DIAGNOSTIC_CONSOLE_AND_CAPTURE_TIMING_ONLY
PRIMARY_CONSOLE=USB_SERIAL_JTAG
SECONDARY_CONSOLE=NONE
CAPTURE_HEARTBEAT=true
CAPTURE_READY_HANDSHAKE=true
PRODUCT_SOURCE_CHANGED=false
PHYSICAL_EXECUTION=false
NEXT_PHYSICAL_GATE_AUTHORIZED=false
```

The R1R4 project is copied into `diagnostics/n3w_r1r4_usb_console_evidence/` and
keeps the R1R3 ROC constants, official API calls, one-probe sequence, explicit
cancel, and home-return checks. The only functional additions are USB
Serial/JTAG primary-console selection, secondary-console disablement, a
pre-arm/armed evidence heartbeat, and a DUT capture-ready handshake that gates
the existing autonomous lifecycle.

The CI workflow builds CONTROL and DUT independently from the frozen Espressif
and pioarduino commits, checks official console Kconfig authority, verifies
generated sdkconfig and binary strings, and publishes a bound diagnostic
artifact. CI PASS is not physical-execution authorization.
