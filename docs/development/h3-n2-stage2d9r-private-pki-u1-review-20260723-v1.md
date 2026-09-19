# H3/N2 Stage 2D-9R private PKI U1 review V1

## 1. Proposed next decision

Proposed authorization ID:

```text
U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01
```

This is not a D2 and does not authorize any board, serial, network or firmware execution.

The proposed U1 may authorize exactly one offline generation and private-custody installation of the Stage 2D-9R test PKI and isolated Broker material set. It is **not yet granted**.

```text
U1_AUTHORIZATION_GRANTED=false
PRIVATE_PKI_GENERATION_AUTHORIZED=false
```

## 2. Frozen generator source contract

```text
generator_path=tools/h3_n2_stage2d9r_private_pki_generator_20260723_v1.py
generator_sha256=a9be0c96fd58882b3778886515076f6aae5940c0ac195fc629ed1ebe708265d0
generator_contract_test_sha256=6063bdba137f703b967bbc6324bafeda73e990978cdeba1968cc3d4fd08fba6d
default_mode=read_only_toolchain_probe
execute_mode=explicit_--execute_only
custody_root_selection_rule=HOME_LOCAL_STATE_STAGE2D9R_PRIVATE_PKI_V1
test_run_suffix=tlsvalid01
```

The default invocation cannot generate private material. Before a U1 authorization can be issued, a host-only read-only probe must freeze:

- Python executable SHA-256 and version;
- OpenSSL executable SHA-256 and version;
- `mosquitto_passwd` executable SHA-256 and version;
- exact generator SHA-256;
- selected custody-root digest and confirmation that the target directory is absent.

The probe output must contain no absolute private paths or secret values and must state that board, network and Broker operations were not performed.

## 3. Allowed operation after exact U1

After the final source SHA, generator SHA-256, complete host toolchain and custody-root digest have been frozen, one authorized host operation may:

1. claim the exact one-shot U1 authorization before generating material;
2. create one new private directory with mode `0700` outside the repository and shared temporary locations;
3. generate one RSA-2048 test root CA;
4. generate one RSA-2048 Broker key and leaf certificate for exactly `stage2d9r.local`;
5. generate one random test-only MQTT password;
6. convert it into one Mosquitto `sha512-pbkdf2` password-file record;
7. create one loopback-only Broker configuration and exact test-only ACL;
8. create one private custody descriptor containing hashes, modes and private paths but no raw key/password values;
9. create one redacted public descriptor containing public certificate identity and SHA-256 bindings only;
10. validate certificate roles, chain, validity, exact DNS SAN, file modes and public/private leakage boundary;
11. finalize the consumed marker and stop.

## 4. Explicitly prohibited

The proposed U1 does not authorize:

```text
board access
serial access
chip identification
Flash read/write/erase
physical NVS access
Wi-Fi connection
MQTT connection
Broker startup or listener creation
PREPARE_CANDIDATE
VERIFY
ACTIVATE_PROFILE
CLEANUP_TEST_STATE
eFuse
Secure Boot
Flash Encryption
M401A
T1
Home Assistant
Mosquitto service changes
greenhouse-manager
production credentials or production topics
Ready / merge / release / deployment
```

The generated private package may contain a Mosquitto configuration file, but the U1 run must not start Mosquitto, invoke a service manager or open a listening socket.

## 5. Exact identity and cryptographic contract

```text
root_CA_CN=Stage2D9R Test Root CA
root_validity_days=365
broker_CN=stage2d9r.local
broker_DNS_SAN=[stage2d9r.local]
broker_validity_days=30
broker_port=8883
broker_bind=127.0.0.1
mqtt_username=stage2d9r-test
credential_generation=1
key_algorithm=RSA
key_size_bits=2048
signature_digest=SHA-256
leaf_EKU=serverAuth
```

No alias, wildcard, IP SAN, alternate host, clientAuth-only leaf or TLS bypass is permitted.

## 6. Exact authorization binding

The final U1 record must bind:

- exact current PR/source SHA;
- exact generator SHA-256;
- exact Python executable SHA-256;
- exact OpenSSL executable SHA-256;
- exact `mosquitto_passwd` executable SHA-256;
- exact private custody template and custody gate SHA-256;
- exact candidate run suffix and identity;
- exact custody-root selection rule and selected-root digest;
- maximum one generation attempt;
- issuance and expiry no longer than two hours;
- canonical authorization-record SHA-256;
- unique consumed-marker path derived from the authorization ID;
- replay forbidden.

Any change to any bound value, expired authorization, existing consumed marker, existing custody root, or requested retry retires the authorization and requires a fresh U1.

## 7. Required successful result

A successful U1 result must provide, without exposing secret values or private paths:

```text
private_custody_gate=PASS
root_CA_role_valid=true
broker_leaf_role_valid=true
certificate_chain_valid=true
hostname_valid=true
private_modes_valid=true
public_private_leakage_scan_passed=true
private_package_sha256=<bound>
CA_PEM_sha256=<bound>
broker_certificate_sha256=<bound>
broker_SPKI_sha256=<bound>
public_descriptor_sha256=<bound>
candidate_digest_sha256=<bound>
U1_authorization_consumed=true
private_paths_included=false
secret_values_included=false
board_operation=false
network_operation=false
Broker_started=false
```

Only after that result may the project replace the all-zero CA/build placeholders, perform two clean deterministic firmware builds, and freeze a new immutable Artifact. Physical recovery and PREPARE remain a later independent exact D2.

## 8. Approval text template

The final approval text must replace every placeholder with the current exact values and validity window:

```text
同意授权 U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01：
仅允许按已冻结 source SHA、生成器 SHA、Python/OpenSSL/mosquitto_passwd 可执行文件摘要、
私密保管模板、保管目录摘要和候选身份，离线生成并安装一次 Stage 2D-9R 测试专用私密 PKI/隔离 Broker 材料包；
允许写入唯一私密保管目录并生成脱敏公开描述符；
禁止启动 Broker、连接网络、访问实板/串口/Flash/NVS，禁止 PREPARE、VERIFY、ACTIVATE、CLEANUP，
禁止生产环境和 Ready/merge/release；授权一次性、不得重放，任何绑定变化必须重新授权。
```

The approval must not be requested until all source CI is green and the read-only host toolchain probe has been reviewed.
