# N3-W T1 Home Assistant mandatory-USB OTA R7A
# KF-147 predecessor recovery release qualification source design — 2026-11-09

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_PREDECESSOR_RECOVERY_RELEASE_QUALIFICATION_20261109_01
PARENT_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01
PURPOSE=REMOVE_FAIL_PREDECESSOR_BUDGET_EVIDENCE_MISSING
LIVE_T1_ACCESS=false
LIVE_MUTATION=false
PHYSICAL_USB_MUTATION=false
OTA_ORIGIN_DEPLOYMENT=false
MERGE=false
```

The parent source-repair gate stopped correctly because an exact frozen predecessor Docker-save
artifact existed, but the product recovery compression algorithm and measured encoded size did not.

This gate does not guess a number and does not reuse the target archive size.

## 2. Frozen predecessor

```text
UPSTREAM=ghcr.io/home-assistant/home-assistant:2026.10.0
ARM64_MANIFEST_DIGEST=sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
LOCAL_IMAGE_REF=local/n3w-homeassistant:2026.10.0-0c73235a
EXPECTED_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
PLATFORM=linux/arm64
```

Historical exact Docker-save evidence remains useful identity evidence, but is not itself the
compressed recovery budget authority.

## 3. Recovery encoding decision

The product recovery representation is now frozen as:

```text
docker save <exact predecessor>
| gzip -1 -n -c
> predecessor recovery archive
```

Authority module:

```text
tools/n3w_t1_core_updater_ha_recovery_encoding.py
ENCODING_SCHEMA=gh.n3w-t1-ha-predecessor-recovery-encoding/1
```

Rationale:

- keep the existing product architecture's compressed Docker-save artifact family;
- stream from Docker to the compressed archive without requiring a second uncompressed image copy;
- use gzip level 1 to minimize host CPU/time while still reducing removable-media use;
- use `-n` to suppress gzip-layer filename/timestamp metadata; this does not claim that Docker's `docker save` tar stream is byte-deterministic;
- keep the representation directly consumable by `docker load`;
- do not change the already-approved target artifact or its SHA/size.

This is an explicit successor design choice. It is not inferred from the target workflow.

## 4. Qualification contract

GitHub CI must:

1. materialize the exact ARM64 predecessor by manifest digest;
2. verify its exact image ID;
3. execute the shared product recovery encoding twice;
4. record the exact byte size and SHA-256 of both generated archives;
5. parse both archives with the existing portable-image identity implementation;
6. require both archives to resolve to the same stable portable predecessor identity, excluding only archive-size/archive-SHA fields;
7. prove each archive can be loaded back with `docker load`;
8. verify each loaded image ID equals the frozen predecessor image ID;
9. define `MEASURED_EXPORT_BYTES=max(sample_1_size,sample_2_size)`;
10. emit only bounded evidence JSON and both portable identity JSON files as retained CI artifacts.

The large recovery archive is qualification working material only and is not committed to Git and
is not retained as the CI artifact.

## 5. Budget formula

The parent KF-147 formula remains unchanged:

```text
MEASURED_EXPORT_BYTES=max(EXACT_EXPORT_SAMPLE_1_BYTES, EXACT_EXPORT_SAMPLE_2_BYTES)

PREDECESSOR_RECOVERY_BUDGET_BYTES =
ROUND_UP_256_MiB(
  max(
    ceil(MEASURED_EXPORT_BYTES * 110%),
    MEASURED_EXPORT_BYTES + 256_MiB
  )
)
```

All arithmetic is integer-byte arithmetic. The qualification module is the single source for this
formula so the evidence workflow and later production integration cannot silently diverge.

## 6. Evidence authority

The first qualification commit intentionally does not contain a numeric measured value.

After the exact workflow reaches SUCCESS, the measured values must be read from the workflow output
or retained bounded evidence artifact and then frozen into a repository qualification record.

Required frozen fields:

```text
qualification source head
workflow run id
workflow artifact id
exact predecessor identity
encoding schema/argv
sample 1 archive size + SHA-256 + portable identity SHA-256
sample 2 archive size + SHA-256 + portable identity SHA-256
measurement method=max_of_two_exact_product_exports
selected maximum sample
MEASURED_EXPORT_BYTES
PREDECESSOR_RECOVERY_BUDGET_BYTES
```

No value may be copied from a synthetic test fixture.

### 6.1 Qualification failure repair evidence

The first exact qualification run, `42557005111`, proved:

```text
SOURCE_CONTRACT_VALIDATION=PASS
FROZEN_PREDECESSOR_MATERIALIZATION=PASS
EXACT_PREDECESSOR_IMAGE_ID=PASS
FIRST_FAILED_OPERATION=qualification_size_not_reproducible
```

This is evidence that the outer `docker save` stream itself must not be treated as a byte-stable
artifact contract. The product recovery representation remains unchanged. The qualification repair
therefore removes only the unsupported byte-identical assumption and conservatively uses the larger
of two exact product-encoder measurements. No numeric value is guessed and the parent KF-147 budget
formula is unchanged.

## 7. Parent-gate resumption rule

Only after the qualification evidence is frozen may the parent KF-147 source-repair gate resume.

```text
PREDECESSOR_BUDGET_EVIDENCE_BOUND=true
PARENT_GATE_RESUME_ALLOWED=true
```

Qualification PASS does not authorize:

```text
T1 access
service restart
real USB mutation
CONFIRM_USB_ERASE
U2+
live ota.hahub.top publication
board access
merge
```

## 8. CI hygiene

The formal handoff's two literal private-network address occurrences are a docs-only public-safety
failure. They may be replaced with non-sensitive symbolic host wording without changing any live
authority. This repair is independent of the recovery qualification result.
