#pragma once

#include "driver/gpio.h"
#include "esphome/components/uart/uart_component.h"
#include "esphome/core/log.h"

namespace greenhouse {

inline constexpr const char *SOIL_UART_GUARD_TAG = "soil_uart_guard";
inline constexpr gpio_num_t SOIL_UART_TX_PIN = GPIO_NUM_21;
inline constexpr gpio_num_t SOIL_UART_RX_PIN = GPIO_NUM_17;

inline bool set_gpio_input_floating(gpio_num_t pin) {
  esp_err_t result = gpio_reset_pin(pin);
  if (result != ESP_OK) {
    ESP_LOGW(SOIL_UART_GUARD_TAG, "gpio_reset_pin(%d) failed: %s", static_cast<int>(pin),
             esp_err_to_name(result));
    return false;
  }

  result = gpio_set_direction(pin, GPIO_MODE_INPUT);
  if (result != ESP_OK) {
    ESP_LOGW(SOIL_UART_GUARD_TAG, "gpio_set_direction(%d) failed: %s", static_cast<int>(pin),
             esp_err_to_name(result));
    return false;
  }

  gpio_pullup_dis(pin);
  gpio_pulldown_dis(pin);
  return true;
}

inline void set_soil_uart_high_impedance(esphome::uart::UARTComponent &uart) {
  const auto flush_result = uart.flush();
  switch (flush_result) {
    case esphome::uart::UARTFlushResult::UART_FLUSH_RESULT_SUCCESS:
    case esphome::uart::UARTFlushResult::UART_FLUSH_RESULT_ASSUMED_SUCCESS:
      break;
    case esphome::uart::UARTFlushResult::UART_FLUSH_RESULT_TIMEOUT:
      ESP_LOGW(SOIL_UART_GUARD_TAG, "UART TX flush timed out before power-down");
      break;
    case esphome::uart::UARTFlushResult::UART_FLUSH_RESULT_FAILED:
      ESP_LOGW(SOIL_UART_GUARD_TAG, "UART TX flush failed before power-down");
      break;
  }

  const bool tx_ok = set_gpio_input_floating(SOIL_UART_TX_PIN);
  const bool rx_ok = set_gpio_input_floating(SOIL_UART_RX_PIN);
  ESP_LOGI(SOIL_UART_GUARD_TAG, "RS485 UART pins set to high impedance (TX=%s RX=%s)",
           tx_ok ? "OK" : "FAIL", rx_ok ? "OK" : "FAIL");
}

inline void restore_soil_uart(esphome::uart::UARTComponent &uart) {
  // ESPHome's ESP-IDF UART implementation reinstalls the driver and reroutes
  // the configured TX/RX pins when load_settings(false) is called.
  uart.load_settings(false);
  ESP_LOGI(SOIL_UART_GUARD_TAG, "RS485 UART settings restored");
}

}  // namespace greenhouse
