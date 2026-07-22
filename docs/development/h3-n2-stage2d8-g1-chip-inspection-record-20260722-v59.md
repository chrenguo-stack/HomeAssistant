# H3/N2 Stage 2D-8 G1 Chip Inspection Record V59

## Status

G1 read-only chip inspection completed successfully on the dedicated spare-board route on 2026-07-22.

The execution manifest remains `LOCKED`. No flash contents were read, no flash or NVS data were written or erased, no eFuse was modified, and no Wi-Fi, MQTT, Broker, test credential, or test key was started or loaded.

## Redacted board binding

- chip family: `ESP32-C6`
- package: `QFN40`
- silicon revision: `v0.2`
- crystal: `40 MHz`
- transport: native `USB-Serial/JTAG`
- detected SPI flash: `8 MB`
- flash manufacturer/device tuple: `20:4017`
- base-MAC SHA-256: `c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6`
- extended-MAC SHA-256: `6b1bd9f118c8e92f9f600d8cc28bcab8fc632da50b67db72302e9ab9ab001325`
- serial-port-path SHA-256: `3dbd58fb2a751780ce45dab2216fc0ffbcb9e70e8ff0a6fe00c85bd0055420b5`

The raw MAC addresses and exact local serial path are retained only in the private operator session and are deliberately excluded from the public repository.

## Security state

- security flags: `0x00000000`
- secure boot: disabled
- flash encryption: disabled
- SPI boot crypt count: `0x0`
- key blocks 0 through 5: user/empty
- observed key-purpose tuple: `(0,0,0,0,0,0,12)`

No eFuse programming is required or authorized for Stage 2D-8.

## G1 verdict

`PASS`

The observed chip and flash capacity match the expected ESP32-C6 / 8 MB laboratory target. Native USB enumeration and ROM read-only access are functional. The device is suitable to proceed to the next locked preparation gate after the operator confirms the exact physical board type and destructive-use boundary.

## Still not authorized

- reading existing flash contents or partition-table bytes;
- erasing or writing flash;
- opening a writable NVS namespace;
- starting Wi-Fi or MQTT;
- starting a temporary Broker;
- loading test credentials or test key material;
- `PREPARE_CANDIDATE`;
- `ACTIVATE_PROFILE`;
- `CLEANUP_TEST_STATE`.
