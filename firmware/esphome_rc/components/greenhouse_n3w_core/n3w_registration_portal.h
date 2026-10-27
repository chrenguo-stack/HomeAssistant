#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string>

#include "esp_http_server.h"

namespace esphome::greenhouse_n3w_core {

class RegistrationPortalRandom {
 public:
  virtual ~RegistrationPortalRandom() = default;
  virtual bool fill_registration_random(uint8_t *data, std::size_t size) = 0;
};

class RegistrationPortal {
 public:
  explicit RegistrationPortal(RegistrationPortalRandom *random);
  ~RegistrationPortal();

  bool ensure_running(
      const std::string &local_ipv4,
      const std::string &subnet_mask);
  void stop();

  bool running() const { return server_ != nullptr; }
  const std::string &qr_payload() const { return qr_payload_; }
  bool scan_trigger_pending() const {
    return scan_trigger_pending_.load(std::memory_order_acquire);
  }
  bool take_scan_trigger() {
    return scan_trigger_pending_.exchange(false, std::memory_order_acq_rel);
  }

 private:
  static esp_err_t register_page_handler_(httpd_req_t *request);
  static esp_err_t start_handler_(httpd_req_t *request);
  static esp_err_t status_handler_(httpd_req_t *request);
  static esp_err_t confirm_handler_(httpd_req_t *request);
  static esp_err_t retry_handler_(httpd_req_t *request);

  esp_err_t handle_register_page_(httpd_req_t *request);
  esp_err_t handle_start_(httpd_req_t *request);
  esp_err_t handle_status_(httpd_req_t *request);
  esp_err_t handle_not_ready_(httpd_req_t *request);

  bool start_(
      const std::string &local_ipv4,
      const std::string &subnet_mask);
  bool rotate_token_();
  bool request_is_local_(httpd_req_t *request) const;
  bool request_token_valid_(httpd_req_t *request);
  bool request_rate_allowed_();
  esp_err_t send_json_(
      httpd_req_t *request,
      const char *status,
      const char *body) const;

  RegistrationPortalRandom *random_{nullptr};
  httpd_handle_t server_{nullptr};
  std::string local_ipv4_{};
  std::string subnet_mask_{};
  uint32_t local_addr_{0};
  uint32_t mask_addr_{0};
  std::string scan_token_{};
  std::string qr_payload_{};
  std::atomic<bool> scan_trigger_pending_{false};
  std::atomic<int64_t> last_dynamic_request_us_{0};
};

}  // namespace esphome::greenhouse_n3w_core
