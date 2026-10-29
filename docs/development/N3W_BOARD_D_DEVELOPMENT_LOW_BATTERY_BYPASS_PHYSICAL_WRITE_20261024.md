# N3-W Board D development low-battery bypass physical write — 2026-10-24

## Result

~~~text
TASK=N3W_BOARD_D_DEVELOPMENT_LOW_BATTERY_BYPASS_WRITE_20261024_01
RESULT=CLOSED_PASS

BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

DEV_SOURCE_HEAD=a15daad779adde74cdead4702f017553118321f8
DEV_ARTIFACT_RUN_ID=40039280572
DEV_ARTIFACT_ID=12538399121
DEV_FIRMWARE_SHA256=da17489dd1ba4fdc13d52b88c03812cbc5a26d23ac2a57e2da5ab1c59a014e95
DEV_NORMALIZED_SLOT_SHA256=c50e71ad3842bb2aa041896442ec4fb64f8326826086c06ba6d09a6a9aedef6d

BOOTLOADER_SHA256=ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
APP0_FULL_SLOT_SHA256=c50e71ad3842bb2aa041896442ec4fb64f8326826086c06ba6d09a6a9aedef6d
APP1_FULL_SLOT_SHA256=c50e71ad3842bb2aa041896442ec4fb64f8326826086c06ba6d09a6a9aedef6d

PHY_INIT_SHA256=f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6
PREWRITE_NVS_SHA256=58e8bf9eadf5988f0bdc1d913e392418d393eb63d8a91307b955b0d12a58ba5f
POSTWRITE_NVS_SHA256=58e8bf9eadf5988f0bdc1d913e392418d393eb63d8a91307b955b0d12a58ba5f

LOW_BATTERY_PROTECTION_BYPASSED=true
DEVELOPMENT_ONLY=true
PRODUCTION_ELIGIBLE=false
NVS_UNCHANGED=true
PHY_INIT_UNCHANGED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
~~~

## Write scope

Only these regions were written:

~~~text
0x009000  OTA data
0x010000  app0 full normalized slot
0x3D0000  app1 full normalized slot
~~~

The exact-R4 bootloader, partition table, phy_init and NVS were not written. Post-write readback proved those protected regions remained unchanged.

## Next gate

The board remains in the flasher stub after the successful write. The next step is a separately observed normal DEV application boot followed by at least eight minutes of runtime observation, which crosses the former approximately 390-second low-battery protection entry window.

Acceptance requires:
- one normal application boot;
- LCD readable and five-page progression continues;
- status LED remains on past the previous low-battery entry window;
- no low-battery-induced restart/protection behavior;
- no additional flash write or direct NVS write.

The DEV image remains explicitly non-production.
