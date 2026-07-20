# H3/N2 Stage 2C-1 节点配对核心开发说明

**基线：** `main = 4e14824c29b9456069236418dab5232a29db6e95`  
**开发分支：** `feature/h3-n2-stage2c1-node-pairing-core-20260720-v45`

## 1. 目标

在不触碰真实网络、真实凭据或实板的前提下，把 Stage 2B 已冻结的发现、候选选择和 claim 合同映射为 ESP32-C6 可编译的节点侧状态核心。

本工作包先冻结状态、输入校验、候选 TTL、显式多主机选择和 claim HMAC，避免把 UDP、HTTP、X25519、AEAD、NVS 凭据存储和 MQTT 切换一次性耦合到完整 RC2 固件。

## 2. 新组件

`firmware/esphome_rc/components/greenhouse_pairing_client`

包含：

- `pairing_client_core.h/.cpp`：不依赖 ESPHome 的状态核心；
- `greenhouse_pairing_client.h/.cpp`：ESPHome 包装、HMAC claim 和脱敏状态；
- `__init__.py`：严格 YAML schema；
- `tests/pairing_client_core_test.cpp`：主机端 C++ 状态测试。

## 3. 已实现

- unbound 到 committed 的严格状态顺序；
- request UUID 和 32 字节 nonce 绑定；
- Manager candidate 严格校验；
- 本地 `.local` 或本地 IPv4 host 限制；
- exact candidate TTL 刷新；
- 同 Manager 冲突 endpoint 保留；
- 固定候选容量；
- 单候选自动解析；
- 多候选显式选择；
- claim transcript 和 HMAC-SHA256；
- discovery query 与 claim JSON 生成；
- secure offer、channel、credentials staged、committed 状态入口；
- committed 后尽力覆盖并清除 `PAIR_SECRET`；
- dump config 不输出秘密或 proof。

## 4. 明确未实现

- UDP socket；
- mDNS browse；
- HTTP client；
- X25519；
- HKDF / ChaCha20-Poly1305；
- secure envelope 解密；
- CA、MQTT 用户名或密码写入 NVS；
- MQTT profile 切换；
- LCD 第五页状态接线；
- 恢复出厂和撤销；
- 实板测试。

以上属于 Stage 2C-2、2C-3 和 Stage 2D。

## 5. 编译目标

### 最小目标

`firmware/esphome_rc/board_lab/h3_node_pairing_core/greenhouse_pairing_client_board_lab.yml`

### 完整产品板目标

`firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_node_pairing_core_board_lab.yml`

完整目标继续保留：

- SCD30；
- SHT30；
- GY30；
- RS485 土壤温湿度和 EC；
- LCD12864 五页；
- 20 秒土壤周期；
- 11 秒 SCD30 周期；
- 本地离线运行能力。

## 6. 安全边界

- 不修改现有生产 RC2 YAML；
- 不修改 `greenhouse_mqtt_auth`；
- 不下发或保存 MQTT 凭据；
- 不连接 Stage 2B Manager runtime；
- 不修改 M401A、T1、Home Assistant、Broker 或节点；
- CI 只使用临时随机秘密并在结束时删除。

## 7. 退出门

- 主机 C++ 测试通过；
- 最小 ESP32-C6 配置和编译通过；
- 完整 RC2 配置和编译通过；
- 公共仓库安全检查通过；
- 现有 Manager、M0、M2 和板级 CI 不回归；
- PR 差异只包含 Stage 2C-1 文件。
