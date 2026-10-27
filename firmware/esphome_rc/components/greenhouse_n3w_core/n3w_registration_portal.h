#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

#include "esp_http_server.h"

namespace esphome::greenhouse_n3w_core {

class RegistrationPortalRandom {
 public:
  virtual ~RegistrationPortalRandom() = default;
  virtual bool fill_registration_random(uint8_t *data, std::size_t size) = 0;
};

class RegistrationPortalState {
 public:
  virtual ~RegistrationPortalState() = default;
  virtual bool registration_portal_allowed() const = 0;
};

enum class RegistrationPortalStage : uint8_t {
  IDLE = 0,
  DISCOVERING,
  WAIT_CONFIRM,
  ERROR_NO_CANDIDATE,
  SELECTED_PENDING_BOOTSTRAP,
};

struct RegistrationPortalCandidateView {
  std::string id;
  std::string label;
  uint64_t expires_at_ms{0};
};

class RegistrationPortal {
 public:
  RegistrationPortal(
      RegistrationPortalRandom *random,
      RegistrationPortalState *state);
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

  RegistrationPortalStage discovery_stage() const;
  void set_discovery_in_progress();
  void set_node_label(const std::string &node_label);
  void set_candidates(
      const std::vector<RegistrationPortalCandidateView> &candidates);
  void set_no_candidates();
  void clear_discovery_session();
  bool take_selected_candidate_id(std::string *candidate_id);

 private:
  static esp_err_t register_page_handler_(httpd_req_t *request);
  static esp_err_t start_handler_(httpd_req_t *request);
  static esp_err_t status_handler_(httpd_req_t *request);
  static esp_err_t confirm_handler_(httpd_req_t *request);
  static esp_err_t retry_handler_(httpd_req_t *request);

  esp_err_t handle_register_page_(httpd_req_t *request);
  esp_err_t handle_start_(httpd_req_t *request);
  esp_err_t handle_status_(httpd_req_t *request);
  esp_err_t handle_confirm_(httpd_req_t *request);
  esp_err_t handle_retry_(httpd_req_t *request);

  bool start_(
      const std::string &local_ipv4,
      const std::string &subnet_mask);
  bool rotate_token_();
  bool request_is_local_(httpd_req_t *request) const;
  bool read_action_request_(
      httpd_req_t *request,
      bool require_candidate_id,
      std::string *candidate_id);
  bool request_rate_allowed_();
  esp_err_t send_json_(
      httpd_req_t *request,
      const char *status,
      const char *body) const;
  esp_err_t send_json_(
      httpd_req_t *request,
      const char *status,
      const std::string &body) const;
  static uint64_t monotonic_ms_();

  RegistrationPortalRandom *random_{nullptr};
  RegistrationPortalState *state_{nullptr};
  httpd_handle_t server_{nullptr};
  std::string local_ipv4_{};
  std::string subnet_mask_{};
  uint32_t local_addr_{0};
  uint32_t mask_addr_{0};
  std::string scan_token_{};
  std::string qr_payload_{};
  std::atomic<bool> scan_trigger_pending_{false};
  std::atomic<uint32_t> last_dynamic_request_ms_{0};

  mutable std::mutex discovery_mutex_{};
  RegistrationPortalStage discovery_stage_{RegistrationPortalStage::IDLE};
  std::string node_label_{};
  std::vector<RegistrationPortalCandidateView> candidates_{};
  std::string selected_candidate_id_{};
};

}  // namespace esphome::greenhouse_n3w_core
