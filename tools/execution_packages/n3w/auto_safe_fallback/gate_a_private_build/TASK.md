# N3-W auto safe fallback Gate A private build package

Status: `PREPARATION_ONLY`

This package consumes the private PASS result from the Gate A T1/Board B read-only preflight and builds one exact, private Gate A firmware bundle.

The package deliberately does not use Board B's current product provisioning state. KF-099 physical evidence shows that Board B is currently in the pairing WAIT / repair-intent-required route, so using `runtime_ready()` as a Gate A prerequisite would test an unrelated provisioning condition.

The private build therefore creates an isolated, ephemeral TLS MQTT profile:

- a temporary CA and server certificate;
- a temporary MQTT username/password/client ID;
- a fixed TLS verification name `n3w-gate-a.invalid`;
- a separate lab TCP port `18883`;
- the restore/live-alias/blackhole addresses from the private preflight result.

The temporary profile is injected only into the Gate A application image. It is not written through the N3-W product NVS store and does not change production Broker, Manager or DynSec state.

Exact public source authority:

```text
SOURCE_HEAD=8210cf7b53e9ec934d145f1c15e9619579c923be
SOURCE_TREE=5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c
TARGET_BLOB=7279271d469958940c2b51aa4a80602078470891
MQTT_PATCH_BLOB=49570a83ead08158d4d99c385740fa6d646b5e3d
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

The generated bundle is private. It contains firmware with temporary MQTT credentials and TLS material. Do not commit, upload, paste, or archive the bundle in the public repository.

This gate performs no T1 mutation, Board access, serial access or Flash write. Later T1 lab activation and Board B Flash write each require their own explicit physical authorization.
