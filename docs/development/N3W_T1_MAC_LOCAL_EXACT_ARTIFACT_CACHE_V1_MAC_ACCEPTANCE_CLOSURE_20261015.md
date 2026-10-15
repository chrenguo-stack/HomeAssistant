# N3-W T1 Mac 本地 exact artifact cache V1 Mac acceptance closure
# 2026-10-15

## 0. 结论

```text
TASK=N3W_T1_MAC_LOCAL_EXACT_ARTIFACT_CACHE_V1_MAC_ACCEPTANCE_20261015_01
RESULT=CLOSED_PASS

PR=545
PR_STATE=OPEN_DRAFT_UNMERGED
REPAIRED_EXECUTABLE_SOURCE_HEAD=13b08208c91400a7e6a91ddbc47620a6146eb2a1
SOURCE_CI=14_SUCCESS_0_FAILURE_0_PENDING

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
EXPLICIT_DEVICE_PROVISIONING=false
F4=false
BOARD_ACCESS=false
MERGE=false
```

真实 Mac acceptance 已完成。第一次 exact artifact 获取走 GitHub -> Mac durable store，
第二次 exact artifact 获取严格走本地 cache-only path，并在第二次获取前把 GitHub metadata/download
函数替换为 hard-fail sentinel。第二次仍然成功，因此证明 cache hit 路径没有访问 GitHub。

## 1. Exact artifact authority

```text
WORKFLOW_RUN_ID=38696945364
ARTIFACT_ID=11954286988
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-13b08208c91400a7e6a91ddbc47620a6146eb2a1
ARTIFACT_SIZE_BYTES=2535589326
ARTIFACT_ZIP_SHA256=047a40ed640bc1bfcbc8adb7007da2a4eea1f8abedffbc3cb2e2a4d9f6817928
RUNTIME_PAYLOAD_SHA256=bc884befe99d223ce39788bab0b5555ff34faebd050c0dffbeebc77c523f7097
PAYLOAD_MANIFEST_SHA256=10c4f298c1034694a93d260970dac09c1a495f7d0b337922de0ba48698874a6c
```

GitHub-side artifact identity remained unexpired and exact-bound at closure.

## 2. Real Mac evidence

Operator-side final result:

```text
MAC_FREE_BYTES=26488848384

FIRST_ACQUISITION=MISS_POPULATED
FIRST_INNER_BINDING=PASS

SECOND_ACQUISITION=HIT
SECOND_INNER_BINDING=PASS

STATUS=PASS
SECOND_HIT_GITHUB_ACCESS=false
PERSISTENT_STORE=true
```

Persistent exact entry, normalized relative to the user home directory:

```text
~/Documents/N3W/exact-artifacts/
  11954286988/
    047a40ed640bc1bfcbc8adb7007da2a4eea1f8abedffbc3cb2e2a4d9f6817928/
      artifact.zip
      binding.json
```

The persistent ZIP SHA-256 equals the exact GitHub artifact digest.

## 3. Proven behavior

This live Mac acceptance proves:

1. cache miss performs one exact GitHub acquisition and populates the durable Mac store;
2. the populated ZIP passes exact SHA-256;
3. runtime payload, manifest, capacity, host wrapper, and all three image artifact bindings pass;
4. a second exact use returns `HIT`;
5. the second use succeeds while GitHub metadata and download functions are hard-disabled;
6. therefore a verified local hit does not re-download the large GitHub artifact;
7. the durable store survives outside temporary working directories.

## 4. Acceptance-discovered repair

The first two attempts stopped before cache population because the Mac's `gh api` path produced:

```text
attempt_1=EOF
attempt_2=TLS_HANDSHAKE_TIMEOUT
```

The repair replaced artifact metadata lookup with authenticated `curl` and added bounded IPv4/HTTP1.1 retries
to metadata, redirect lookup, and large artifact transfer. Exact SHA/binding checks were not weakened.

The repaired source head `13b08208...` passed 14/14 CI before this final acceptance.

## 5. Product boundary

```text
R4_AUTHORIZATION=CONSUMED_NO_REPLAY
R4_REPLAY_PERMITTED=false

PUBLIC_PRODUCT_STAGED=true
EXPLICIT_DEVICE_PROVISIONING_EXECUTED=false
PRODUCTION_SERVICE_START=false
F4_ENTERED=false
BOARD_ACCESS=false

MAC_EXACT_ARTIFACT_CACHE_V1=CLOSED_PASS
```

The Mac cache Gate did not access T1 and did not alter the staged public product.

## 6. Stop point

```text
CURRENT_STOP_POINT=AFTER_MAC_CACHE_ACCEPTANCE_BEFORE_EXPLICIT_DEVICE_PROVISIONING
NEXT_ONE_GATE=NONE:EXPLICIT_DEVICE_PROVISIONING_REQUIRES_SEPARATE_AUTHORIZATION
AUTO_EXECUTE_NEXT_GATE=false
```

The next product step remains explicit per-device provisioning. It is outside this Gate and requires a separate
decision/authorization. F4 service activation/end-to-end acceptance remains later and separately authorized.
