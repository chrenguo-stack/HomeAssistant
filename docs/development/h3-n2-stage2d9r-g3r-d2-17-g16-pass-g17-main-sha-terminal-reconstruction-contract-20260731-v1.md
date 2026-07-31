# H3/N2 Stage2D-9R G3R D2-17 G16 pass and G17 terminal reconstruction contract

## Frozen facts

G16 completed with `PASS` and a self-bound terminal record. The authenticated G14 inner marker is `CONSUMED_PASS`; PREPARE and VERIFY were each delivered exactly once; PREPARE evidence is `PREPARE_PASS`; and no reset loop was observed. The G14 outer terminal is `CONSUMED_FAILED` only because the frozen base result generator raised `KeyError('main_sha')` after the executor had completed.

The active authorization family uses `repository_head_sha`. The frozen base result generator directly indexes `authorization['main_sha']`. The missing compatibility alias is therefore a reporting/terminalization defect, not a board, Flash, PREPARE, VERIFY, or firmware failure.

## G16 acceptance

The G16 acceptance binding covers the frozen load-bearing forensic subset, not every descriptive field in the acceptance document:

`9be11c054d84fb7db1a0a23eddc3f5735d5d660c6e1d2b1263634629938c0714`

The accepted conclusion is:

- physical execution reached `CONSUMED_PASS` internally;
- the outer `CONSUMED_FAILED` state is a post-execution terminalization defect;
- no physical rerun is required or authorized.

## G17 repair

The result compatibility repair operates only in memory:

1. require a valid 40-hex `repository_head_sha` when `main_sha` is absent;
2. copy it into a shallow authorization copy as `main_sha`;
3. reject invalid values or conflicting aliases;
4. never mutate the persisted authorization record;
5. call the already installed result generator with the repaired copy.

The host-only reconstruction validates the self-bound G16 terminal and the exact inner marker, delivery, PREPARE, and reset evidence. It emits a new reconstructed physical terminal stating that the D2-17 physical execution outcome was `CONSUMED_PASS` and that the outer failure was terminalization-only.

## Safety boundary

G17 source is inert without a separately approved one-shot host-only closure package. It does not authorize or perform board access, USB enumeration, serial access, esptool, Flash/NVS, network, Broker, PREPARE, VERIFY, recovery, ACTIVATE, CLEANUP, Ready, merge, release, tag, or deployment.

G14, G15, and G16 packages remain retired. No predecessor package, authorization, marker, or private runtime may be replayed or modified.

## Pending binding and next gate

Pending binding:

`903e5547c551c8fffdfe62dfce3b33ea2406bd16df16cbcb3d04867e88074317`

Next exact gate:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G17-PRIVATE-TERMINAL-RECONSTRUCTION-AND-TARGET-MAC-HOST-ONLY-CLOSURE-AUTHORIZATION-CREATION-20260731-01`
