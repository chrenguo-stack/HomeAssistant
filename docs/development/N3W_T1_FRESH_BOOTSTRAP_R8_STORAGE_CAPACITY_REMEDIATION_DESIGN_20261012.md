> **2026-10-12 architecture alignment update / HOLD**：ADR-0009 已冻结黄金母盘 + 每机 firstboot 量产生命周期。本文的 streaming transport 设计不再是当前下一门 source repair；其定位收窄为 `MASTER_BUILD_WORKSPACE_REQUIREMENT` 的可选优化。正常量产 clone 不重复执行三镜像 docker load。当前 `STREAMING_SOURCE_REPAIR_NOW=HOLD`；5 GiB 只保留为 R8 单机安装工具历史保守策略，不得等同于 `PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT`。Authority: `docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md` and `docs/development/N3W_T1_GOLDEN_MASTER_FIRSTBOOT_ARCHITECTURE_CONTRACT_AND_ADR_DESIGN_FREEZE_20261012.md`.

# N3-W T1 fresh bootstrap R8 — storage capacity remediation design

Date: 2026-10-12
Gate: N3W_T1_FRESH_BOOTSTRAP_R8_STORAGE_CAPACITY_REMEDIATION_DESIGN
Scope: source/design/test planning only. No T1 mutation, no R3 cleanup, no production service start, no board access, no PR merge.

## 1. Trigger evidence

Fresh T1 read-only evidence:

- containers=0
- images=0
- volumes=0
- networks=bridge/host/none
- DockerRootDir=/var/lib/docker
- external containerd root=/var/lib/containerd by default config
- containerd imports absent
- /var/tmp, /var/lib/docker and /var/lib/containerd share device 45826
- current free bytes=9,229,160,448
- R3 retained payload=/var/tmp/n3w-fresh-bootstrap.EOmzn8
- R3 retained payload size≈2.4 GiB; three retained image tars are present
- production roots absent
- _08 not granted

Exact replacement artifact integrity:

- source head=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
- artifact id=11746610745
- payload archive SHA256=896d8eff51e21c4686283afc4701b9b32f87a56b32f3b9243c26508003f316ec
- payload manifest SHA256=36048d1cb77e4ee6a4aaf0bbc2019f434133b8ab0a210960e30ba9d4d53ea8ad
- archive/manifest local revalidation=PASS

Exact current capacity result:

~~~text
ARCHIVE_BYTES=814703743
PAYLOAD_BYTES=2535561761
EXTRACTION_PEAK_BYTES=3350265504
IMAGE_LOAD_PEAK_BYTES=7302675327
REQUIRED_PEAK_BYTES=7302675327
RESERVE_BYTES=5368709120
REQUIRED_FREE_BYTES=12671384447
T1_AVAILABLE_BYTES=9229160448
CAPACITY_MARGIN_BYTES=-3442223999
CAPACITY_RESULT=FAIL
~~~

This is a capacity-policy blocker, not an artifact-integrity failure and not evidence that the product cannot physically fit on the disk.

## 2. Why the current peak is high

Current host-wrapper sequence:

~~~text
download exact GitHub artifact to Mac
→ verify outer ZIP / archive / manifest
→ read-only storage preflight
→ scp complete payload-archive.tar.gz to T1
→ fully extract entire payload under /var/tmp
→ delete compressed archive
→ bootstrap preflight
→ claim one-shot authorization
→ docker load HA tar
→ verify image
→ delete HA tar
→ docker load Manager tar
→ verify image
→ delete Manager tar
→ docker load Broker tar
→ verify image
→ delete Broker tar
~~~

The peak model deliberately counts simultaneous copies:

~~~text
remaining extracted image tar payload
+ containerd content-store estimate
+ unpacked snapshot estimate
~~~

The source additionally requires a fixed post-peak reserve:

~~~text
MIN_POST_PEAK_FREE_BYTES = 5 * 1024 * 1024 * 1024
~~~

The repository documents call this a conservative 5 GiB post-peak reserve. No quantitative derivation for exactly 5 GiB was found in the reviewed R6/R7/R8 source/design authority. Therefore the value is a safety-policy constant, not a measured T1 physical minimum.

## 3. Frozen constraints

The remediation must not weaken these contracts:

1. exact source/artifact/manifest/hash binding remains mandatory;
2. F5 actual containerd image-store authority remains fail-closed;
3. non-empty containerd imports remain fail-closed;
4. preflight remains Docker-mutation-free;
5. one-shot authorization must still be claimed before the first Docker mutation;
6. authorization is permanently consumed after claim; no replay on postclaim failure;
7. images remain offline/exact; no registry pull on T1;
8. every loaded image is verified by the existing portable RootFS/config contract;
9. no production service starts during fresh staging;
10. no board access;
11. R3 retained payload is not deleted as part of this source repair.

## 4. Design decision

### 4.1 Do not lower the 5 GiB reserve in the first repair

Do not change two safety variables at once.

The first repair keeps the existing 5 GiB reserve unchanged and attacks the avoidable staging duplication that creates the current 7.30 GB peak.

Only if the new streaming model still cannot pass after a separately authorized R3 evidence cleanup should the project open a distinct reserve-policy review based on measured long-term runtime growth and rollback requirements.

### 4.2 Stream image tar members directly from the verified compressed payload archive

Keep one exact compressed payload archive on T1, but do not materialize the three large image tar files under /var/tmp.

New remote layout:

~~~text
remote payload root/
  payload.tar.gz
  payload-manifest.json
  tools/
  contract/
  runtime-source/
  artifact image tar files: NOT materialized
~~~

The archive remains exact and SHA-bound.

After authorization claim, bootstrap opens each image member from payload.tar.gz and streams the member bytes directly into docker load.

Order remains:

~~~text
homeassistant
manager
broker
~~~

After all three exact images are verified, payload.tar.gz may be deleted by the transaction owner to release staging space.

### 4.3 Preserve the authorization boundary

The existing contract claims authorization immediately before load_images.

That ordering remains:

~~~text
host/read-only capacity preflight
→ transfer and integrity-check payload archive
→ extract only non-image runtime files
→ bootstrap preflight
→ validate archive/member inventory
→ claim _08
→ first docker load
~~~

No docker load may occur before claim.

### 4.4 New conservative streaming capacity model

Let:

- A = compressed payload archive bytes
- N = extracted non-image payload bytes
- T_i = tar size estimate for image i
- L_i = loaded snapshot-size estimate for image i
- R = post-peak reserve (initially unchanged at 5 GiB)

Preclaim predicted peak:

~~~text
stream_peak_0 = A + N
stream_peak_after_i =
  A + N + Σ(T_loaded) + Σ(L_loaded)

required_peak = max(stream_peak_after_i)
required_free = required_peak + R
~~~

The model intentionally continues to treat each loaded image tar size as containerd content-store cost and loaded_size as snapshot cost.

It no longer counts the same image tar both as a fully materialized /var/tmp file and as containerd content.

The manifest transport contract should be bumped from gh.n3w-t1-fresh-transport/1 to /2 because staging semantics change.

Suggested new fields:

~~~json
{
  "schema": "gh.n3w-t1-fresh-transport/2",
  "image_transport": "verified_archive_member_stream",
  "remote_archive_name": "payload.tar.gz",
  "image_tar_materialization": false,
  "dynamic_capacity_gate": true
}
~~~

## 5. Dynamic capacity gate

Preclaim admission remains conservative and must PASS before authorization claim.

After each successful image load and runtime identity verification, bootstrap re-reads actual free bytes on the already-authorized same filesystem.

For each step:

~~~text
free_now = min(
  staging filesystem free,
  DockerRootDir filesystem free,
  actual image_store_root filesystem free
)

remaining_growth_estimate =
  Σ(T_remaining + L_remaining)

require:
free_now >= R + remaining_growth_estimate
~~~

After the last image:

~~~text
free_now >= R
~~~

A dynamic failure after claim is a normal postclaim STOP_PARTIAL:

- authorization consumed
- replay forbidden
- loaded transaction-owned images cleaned up
- production services remain stopped
- retained payload/evidence preserved according to existing postclaim policy

The initial conservative admission should make such a failure exceptional; the dynamic gate protects against real containerd usage materially exceeding the manifest estimate.

## 6. Minimal source delta

Expected production-source changes:

1. tools/n3w_t1_fresh_product_staging_host.py
   - transport schema /2
   - streaming capacity model
   - selective remote extraction
   - keep payload.tar.gz
   - pass exact storage authority + archive SHA into bootstrap apply

2. tools/n3w_t1_fresh_product_bootstrap.py
   - allow image tar records to remain archive-backed rather than disk-materialized
   - require verified payload archive
   - stream exact archive members into docker load
   - preserve HA → Manager → Broker ordering
   - dynamic free-space checks after each image
   - delete archive only after successful image loading/verification
   - preserve existing cleanup/no-replay semantics

3. .github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
   - emit transport schema /2 and streaming-mode contract fields
   - retain exact archive/member provenance
   - add streaming rehearsal

Expected tests:

4. tests/tools/test_n3w_t1_fresh_product_staging_host.py
5. tests/tools/test_n3w_t1_fresh_product_bootstrap.py

No change should be required to greenhouse_manager.bootstrap.fresh_installer.run_fresh_staging; before_mutation remains immediately before adapters.load_images().

## 7. Required regression coverage

At minimum:

1. exact artifact/manifest hashes remain enforced;
2. path traversal/symlink/special-member rejection remains;
3. image members are not materialized into /var/tmp;
4. absent/duplicate/wrong-size image member fails before claim;
5. transport schema /1 is rejected by /2 executor unless explicitly compatibility-supported;
6. streaming order is HA → Manager → Broker;
7. claim event occurs before first docker load;
8. no docker mutation during preflight;
9. each image runtime binding is verified after load;
10. dynamic capacity gate runs after every image;
11. dynamic gate failure yields consumed/no-replay STOP_PARTIAL and cleanup;
12. outer payload archive is deleted only after all image loads succeed;
13. F5 direct containerd root execution regression remains PASS;
14. non-empty containerd imports fail closed;
15. Docker/storage roots must remain same-filesystem before apply;
16. no registry pull;
17. no production service start;
18. no board access.

## 8. R3 handling

R3 is historical forensic evidence, not a runtime dependency.

Do not delete it in this design/source-repair gate.

Separate future bounded cleanup prerequisites:

1. archive exact R3 file inventory and hashes needed for forensic provenance;
2. preserve authorization-claimed evidence;
3. prove R3 directory is not an active runtime source;
4. exact single-directory cleanup authorization;
5. delete only /var/tmp/n3w-fresh-bootstrap.EOmzn8;
6. immediately re-read free bytes.

R3 cleanup is expected to recover about 2.4 GiB, but no capacity PASS may be claimed until the new streaming model is calculated against exact manifest image values and fresh post-cleanup free bytes.

## 9. Decision / next gate

~~~text
CURRENT_CAPACITY=FAIL
ARTIFACT_INTEGRITY=PASS
ROOT_CAUSE_CLASS=INFRASTRUCTURE_DEPLOYMENT_STAGING_PEAK
LOWER_5_GIB_RESERVE_NOW=NO
STREAMING_IMAGE_IMPORT_DESIGN=ACCEPTED
DYNAMIC_CAPACITY_GATE_DESIGN=ACCEPTED
R3_CLEANUP_NOW=NO
AUTHORIZATION_08_GRANTED=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

Next source gate:

~~~text
N3W_T1_FRESH_BOOTSTRAP_R8_STORAGE_CAPACITY_STREAMING_SOURCE_REPAIR
~~~

Before declaring the design numerically sufficient for this exact T1, extract the exact transport.images tar_size_bytes and loaded_size_bytes from the already-downloaded R8 manifest and calculate the /2 streaming peak. This is a Mac-local read-only calculation and does not modify T1.
