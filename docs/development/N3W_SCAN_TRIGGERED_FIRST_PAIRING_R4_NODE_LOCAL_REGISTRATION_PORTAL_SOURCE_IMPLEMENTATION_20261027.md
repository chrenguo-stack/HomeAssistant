# N3-W scan-triggered first registration — R4 node-local registration portal source implementation

Date: 2026-10-27

## Scope

This gate starts from merged PR #692 / main `336835454211257f997d86d9c2f3208acbd7c03f`.

R3 T1-side identity-bound first-registration transaction is treated as closed source authority and is not redesigned here.

R4 implements only the next frozen node-side layer:

- narrow node-local HTTP registration portal on TCP/47113;
- RAM-only 128-bit scan token;
- actionable QR URL using the current STA IPv4;
- scan-trigger admission from the phone-local page;
- removal of idle automatic Manager discovery from a fresh unregistered node;
- preservation of pending final-ACK recovery;
- production-only compatibility mapping for the existing display/transport API, so historical package-level Stage2D protection does not need to be weakened.

R4 deliberately does **not** implement:

- T1 discovery or multi-T1 selection (R5);
- node-to-T1 TLS bootstrap (R6);
- full LCD state/error mapping (R7);
- simulated end-to-end closure (R8);
- artifact/exact build closure (R9);
- T1 or board physical acceptance (R10).

## Product behavior after R4 source

When Wi-Fi is connected and the node is unregistered, the product QR is:

`http://<current-node-ip>:47113/register#t=<ram-only-token>`

The QR carries no Setup Secret, hardware ID, pairing ID, Manager locator or long-lived credential.

The local page has no external resources, cookies or local storage. Its first valid `/start` request records a bounded in-memory scan trigger for R5 to consume. Until R5 exists, confirm/retry fail closed with `discovery_stage_pending`.

The existing product YAML interface remains unchanged. Under the production de-harness build only, `pairing_handoff_ready()` and `pairing_qr_payload()` are compatibility wrappers for the registration portal. Non-production lab builds keep the legacy engineering pairing handoff/payload behavior.

A fresh unregistered node no longer calls the legacy automatic `discover -> hello -> pair` loop by itself. The only exception retained in R4 is a durable pending final acknowledgement from an already delivered credential bundle; that recovery continues through the existing pairing client.

## Safety / claim boundary

No T1 access, live deployment, board access, flash, NVS mutation or physical acceptance is performed by this gate.

This document records source intent only. R4 is not a full user-flow acceptance claim until R5-R9 are completed.
