# H3/N2 Stage 2D-9R private PKI U1 review V1

## 1. Proposed next decision

Proposed authorization ID:

```text
U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01
```

This is not a D2 and does not authorize any board or network execution.

The proposed U1 authorizes exactly one offline generation and private-custody installation of the Stage 2D-9R test PKI and isolated Broker material set.

## 2. Allowed operation

After the source SHA, generator SHA-256, OpenSSL executable SHA-256 and custody root have been frozen, the authorized host operation may:

1. create one new private directory with mode `0700` outside the repository;
2. generate one RSA-2048 test root CA;
3. generate one RSA-2048 Broker key and leaf certificate for exactly `stage2d9r.local`;
4. generate one random test-only MQTT password;
5. create one Mosquitto password file, isolated configuration and exact ACL;
6. create one private custody descriptor containing hashes, modes and private paths but no raw key/password values;
7. create one redacted public descriptor containing only public certificates, identity fields and SHA-256 bindings;
8. validate certificate roles, chain, validity, exact DNS SAN, file modes and public/private leakage boundary;
9. consume the one-shot U1 authorization and stop.

## 3. Explicitly prohibited

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

The private package may contain a Mosquitto configuration file, but the U1 run must not start Mosquitto or open a listening socket.

## 4. Exact identity and cryptographic contract

```text
root_CA_CN=Stage2D9R Test Root CA
broker_CN=stage2d9r.local
broker_DNS_SAN=[stage2d9r.local]
broker_port=8883
mqtt_username=stage2d9r-test
credential_generation=1
key_algorithm=RSA
key_size_bits=2048
signature_digest=SHA-256
leaf_EKU=serverAuth
```

No alias, wildcard, IP SAN, alternate host, clientAuth-only leaf or TLS bypass is permitted.

## 5. One-shot and change handling

The future U1 authorization must bind:

- exact PR/source SHA;
- exact reviewed generator SHA-256;
- exact generator command-group SHA-256;
- exact private custody template SHA-256;
- exact OpenSSL version and executable SHA-256;
- exact candidate run suffix;
- exact custody root selection rule;
- maximum one generation attempt;
- issuance and expiry no longer than two hours;
- one consumed-marker path.

Any change to source SHA, generator code, OpenSSL executable, identity, SAN, cryptographic profile, material set, custody rule or requested retry retires the authorization and requires a fresh U1.

## 6. Required result before immutable firmware freeze

A successful U1 result must provide, without exposing secret values:

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
U1_authorization_consumed=true
board_operation=false
network_operation=false
Broker_started=false
```

Only after that result may the project replace the all-zero `ca_pem_sha256` and unlock/build placeholders, perform two clean deterministic firmware builds, and freeze a new immutable Artifact. Physical recovery and PREPARE remain a later independent exact D2.

## 7. Approval text template

The future operator approval should explicitly state:

```text
同意授权 U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01：
仅允许按已冻结 source SHA、生成器 SHA、OpenSSL 摘要、私密保管模板和候选身份，
离线生成并安装一次 Stage 2D-9R 测试专用私密 PKI/隔离 Broker 材料包；
允许写入唯一私密保管目录并生成红acted public descriptor；
禁止启动 Broker、连接网络、访问实板/串口/Flash/NVS，禁止 PREPARE、VERIFY、ACTIVATE、CLEANUP，
禁止生产环境和 Ready/merge/release；授权一次性、不得重放，任何绑定变化必须重新授权。
```

The final authorization text will replace the placeholders with exact current hashes and expiry times after all source CI is green.
