#include "n3w_registration_portal.h"

#include <array>
#include <cstring>
#include <string>
#include <vector>

#include "esphome/components/json/json_util.h"
#include "esp_timer.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include "mbedtls/base64.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint16_t kRegistrationPortalPort = 47113;
constexpr std::size_t kScanTokenBytes = 16;
constexpr std::size_t kMaxActionBodyBytes = 512;
constexpr int64_t kMinDynamicRequestIntervalUs = 100000;

const char kPortalPage[] = R"HTML(<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>联机注册</title>
<style>
body{font-family:sans-serif;margin:2rem;max-width:32rem}
button{font-size:1.1rem;padding:.7rem 1rem}
#status{margin-top:1rem}
</style>
</head>
<body>
<h1>联机注册</h1>
<p id="status">正在准备联机注册…</p>
<script>
(() => {
  const out = document.getElementById("status");
  const params = new URLSearchParams(location.hash.slice(1));
  const token = params.get("t");
  history.replaceState(null, "", location.pathname);
  if (!token) {
    out.textContent = "二维码已失效，请重新扫码";
    return;
  }
  fetch("/api/v1/register/start", {
    method: "POST",
    cache: "no-store",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      schema: "gh.registration.portal-action/1",
      token: token
    })
  }).then(async response => {
    if (!response.ok) throw new Error("start rejected");
    await response.json();
    out.textContent = "正在查找主机，请查看设备屏幕";
  }).catch(() => {
    out.textContent = "二维码已失效，请重新扫码";
  });
})();
</script>
</body>
</html>)HTML";

std::string base64url_encode(const uint8_t *data, std::size_t size) {
  if (data == nullptr || size == 0) return {};
  std::vector<uint8_t> encoded(((size + 2U) / 3U) * 4U + 1U, 0);
  std::size_t written = 0;
  if (mbedtls_base64_encode(
          encoded.data(),
          encoded.size(),
          &written,
          data,
          size) != 0) {
    return {};
  }
  std::string output(
      reinterpret_cast<const char *>(encoded.data()),
      written);
  for (char &ch : output) {
    if (ch == '+') ch = '-';
    if (ch == '/') ch = '_';
  }
  while (!output.empty() && output.back() == '=') output.pop_back();
  return output;
}

bool constant_time_equal(const std::string &left, const std::string &right) {
  const std::size_t max_size =
      left.size() > right.size() ? left.size() : right.size();
  uint8_t diff = static_cast<uint8_t>(left.size() ^ right.size());
  for (std::size_t index = 0; index < max_size; ++index) {
    const uint8_t lhs =
        index < left.size() ? static_cast<uint8_t>(left[index]) : 0U;
    const uint8_t rhs =
        index < right.size() ? static_cast<uint8_t>(right[index]) : 0U;
    diff = static_cast<uint8_t>(diff | (lhs ^ rhs));
  }
  return diff == 0U;
}

bool parse_ipv4(const std::string &value, uint32_t *address) {
  if (address == nullptr || value.empty()) return false;
  in_addr parsed{};
  if (inet_pton(AF_INET, value.c_str(), &parsed) != 1 ||
      parsed.s_addr == 0U) {
    return false;
  }
  *address = parsed.s_addr;
  return true;
}

}  // namespace

RegistrationPortal::RegistrationPortal(RegistrationPortalRandom *random)
    : random_(random) {}

RegistrationPortal::~RegistrationPortal() {
  stop();
}

bool RegistrationPortal::rotate_token_() {
  if (random_ == nullptr) return false;
  std::array<uint8_t, kScanTokenBytes> raw{};
  if (!random_->fill_registration_random(raw.data(), raw.size())) {
    return false;
  }
  scan_token_ = base64url_encode(raw.data(), raw.size());
  return !scan_token_.empty();
}

bool RegistrationPortal::start_(
    const std::string &local_ipv4,
    const std::string &subnet_mask) {
  uint32_t local_addr = 0;
  uint32_t mask_addr = 0;
  if (!parse_ipv4(local_ipv4, &local_addr) ||
      !parse_ipv4(subnet_mask, &mask_addr) ||
      mask_addr == 0U ||
      random_ == nullptr) {
    return false;
  }
  if (!rotate_token_()) return false;

  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = kRegistrationPortalPort;
  config.max_uri_handlers = 8;
  config.lru_purge_enable = true;
  config.stack_size = 6144;

  httpd_handle_t server = nullptr;
  if (httpd_start(&server, &config) != ESP_OK || server == nullptr) {
    scan_token_.clear();
    return false;
  }

  const auto register_uri = [&](const char *uri, httpd_method_t method,
                                esp_err_t (*handler)(httpd_req_t *)) {
    httpd_uri_t route{};
    route.uri = uri;
    route.method = method;
    route.handler = handler;
    route.user_ctx = this;
    return httpd_register_uri_handler(server, &route) == ESP_OK;
  };

  if (!register_uri(
          "/register",
          HTTP_GET,
          &RegistrationPortal::register_page_handler_) ||
      !register_uri(
          "/api/v1/register/start",
          HTTP_POST,
          &RegistrationPortal::start_handler_) ||
      !register_uri(
          "/api/v1/register/status",
          HTTP_POST,
          &RegistrationPortal::status_handler_) ||
      !register_uri(
          "/api/v1/register/confirm",
          HTTP_POST,
          &RegistrationPortal::confirm_handler_) ||
      !register_uri(
          "/api/v1/register/retry",
          HTTP_POST,
          &RegistrationPortal::retry_handler_)) {
    httpd_stop(server);
    scan_token_.clear();
    return false;
  }

  server_ = server;
  local_ipv4_ = local_ipv4;
  subnet_mask_ = subnet_mask;
  local_addr_ = local_addr;
  mask_addr_ = mask_addr;
  scan_trigger_pending_.store(false, std::memory_order_release);
  last_dynamic_request_us_.store(0, std::memory_order_release);
  qr_payload_ =
      "http://" + local_ipv4_ + ":" +
      std::to_string(kRegistrationPortalPort) +
      "/register#t=" + scan_token_;
  return true;
}

bool RegistrationPortal::ensure_running(
    const std::string &local_ipv4,
    const std::string &subnet_mask) {
  if (server_ != nullptr &&
      local_ipv4 == local_ipv4_ &&
      subnet_mask == subnet_mask_) {
    return true;
  }
  stop();
  return start_(local_ipv4, subnet_mask);
}

void RegistrationPortal::stop() {
  if (server_ != nullptr) {
    httpd_stop(server_);
    server_ = nullptr;
  }
  local_ipv4_.clear();
  subnet_mask_.clear();
  local_addr_ = 0U;
  mask_addr_ = 0U;
  if (!scan_token_.empty()) {
    std::fill(scan_token_.begin(), scan_token_.end(), '\0');
    scan_token_.clear();
  }
  qr_payload_.clear();
  scan_trigger_pending_.store(false, std::memory_order_release);
  last_dynamic_request_us_.store(0, std::memory_order_release);
}

bool RegistrationPortal::request_is_local_(httpd_req_t *request) const {
  if (request == nullptr || local_addr_ == 0U || mask_addr_ == 0U) {
    return false;
  }
  const int socket_fd = httpd_req_to_sockfd(request);
  if (socket_fd < 0) return false;
  sockaddr_in peer{};
  socklen_t peer_length = sizeof(peer);
  if (getpeername(
          socket_fd,
          reinterpret_cast<sockaddr *>(&peer),
          &peer_length) != 0 ||
      peer.sin_family != AF_INET ||
      peer.sin_addr.s_addr == 0U) {
    return false;
  }
  return (peer.sin_addr.s_addr & mask_addr_) ==
         (local_addr_ & mask_addr_);
}

bool RegistrationPortal::request_rate_allowed_() {
  const int64_t now = esp_timer_get_time();
  if (now <= 0) return false;
  const int64_t previous =
      last_dynamic_request_us_.exchange(now, std::memory_order_acq_rel);
  return previous == 0 ||
         now - previous >= kMinDynamicRequestIntervalUs;
}

bool RegistrationPortal::request_token_valid_(httpd_req_t *request) {
  if (request == nullptr ||
      request->content_len <= 0 ||
      static_cast<std::size_t>(request->content_len) >
          kMaxActionBodyBytes) {
    return false;
  }

  std::string body(
      static_cast<std::size_t>(request->content_len),
      '\0');
  std::size_t offset = 0;
  while (offset < body.size()) {
    const int received = httpd_req_recv(
        request,
        body.data() + offset,
        body.size() - offset);
    if (received <= 0) return false;
    offset += static_cast<std::size_t>(received);
  }

  JsonDocument document = json::parse_json(body);
  JsonObjectConst root = document.as<JsonObjectConst>();
  if (root.isNull() ||
      root.size() != 2U ||
      !root["schema"].is<const char *>() ||
      !root["token"].is<const char *>()) {
    return false;
  }
  const char *schema = root["schema"].as<const char *>();
  const char *token = root["token"].as<const char *>();
  if (schema == nullptr || token == nullptr ||
      std::strcmp(
          schema,
          "gh.registration.portal-action/1") != 0) {
    return false;
  }
  return constant_time_equal(token, scan_token_);
}

esp_err_t RegistrationPortal::send_json_(
    httpd_req_t *request,
    const char *status,
    const char *body) const {
  if (request == nullptr || status == nullptr || body == nullptr) {
    return ESP_FAIL;
  }
  httpd_resp_set_status(request, status);
  httpd_resp_set_type(request, "application/json; charset=utf-8");
  httpd_resp_set_hdr(request, "Cache-Control", "no-store");
  httpd_resp_set_hdr(request, "Pragma", "no-cache");
  return httpd_resp_sendstr(request, body);
}

esp_err_t RegistrationPortal::handle_register_page_(
    httpd_req_t *request) {
  if (!request_is_local_(request)) {
    return send_json_(
        request,
        "403 Forbidden",
        "{\"schema\":\"gh.registration.portal-error/1\","
        "\"reason\":\"source_not_local\"}");
  }
  httpd_resp_set_type(request, "text/html; charset=utf-8");
  httpd_resp_set_hdr(request, "Cache-Control", "no-store");
  httpd_resp_set_hdr(request, "Pragma", "no-cache");
  httpd_resp_set_hdr(
      request,
      "Content-Security-Policy",
      "default-src 'none'; script-src 'unsafe-inline'; "
      "style-src 'unsafe-inline'; connect-src 'self'; "
      "base-uri 'none'; form-action 'none'");
  return httpd_resp_send(
      request,
      kPortalPage,
      HTTPD_RESP_USE_STRLEN);
}

esp_err_t RegistrationPortal::handle_start_(httpd_req_t *request) {
  if (!request_is_local_(request) ||
      !request_token_valid_(request)) {
    return send_json_(
        request,
        "403 Forbidden",
        "{\"schema\":\"gh.registration.portal-error/1\","
        "\"reason\":\"scan_session_invalid\"}");
  }
  if (!request_rate_allowed_()) {
    return send_json_(
        request,
        "429 Too Many Requests",
        "{\"schema\":\"gh.registration.portal-error/1\","
        "\"reason\":\"rate_limited\"}");
  }
  scan_trigger_pending_.store(true, std::memory_order_release);
  return send_json_(
      request,
      "202 Accepted",
      "{\"schema\":\"gh.registration.portal-result/1\","
      "\"status\":\"accepted\",\"next\":\"discovery\"}");
}

esp_err_t RegistrationPortal::handle_status_(httpd_req_t *request) {
  if (!request_is_local_(request) ||
      !request_token_valid_(request)) {
    return send_json_(
        request,
        "403 Forbidden",
        "{\"schema\":\"gh.registration.portal-error/1\","
        "\"reason\":\"scan_session_invalid\"}");
  }
  if (!request_rate_allowed_()) {
    return send_json_(
        request,
        "429 Too Many Requests",
        "{\"schema\":\"gh.registration.portal-error/1\","
        "\"reason\":\"rate_limited\"}");
  }
  return send_json_(
      request,
      "200 OK",
      scan_trigger_pending()
          ? "{\"schema\":\"gh.registration.portal-status/1\","
            "\"status\":\"scan_triggered\"}"
          : "{\"schema\":\"gh.registration.portal-status/1\","
            "\"status\":\"idle\"}");
}

esp_err_t RegistrationPortal::handle_not_ready_(
    httpd_req_t *request) {
  if (!request_is_local_(request) ||
      !request_token_valid_(request)) {
    return send_json_(
        request,
        "403 Forbidden",
        "{\"schema\":\"gh.registration.portal-error/1\","
        "\"reason\":\"scan_session_invalid\"}");
  }
  if (!request_rate_allowed_()) {
    return send_json_(
        request,
        "429 Too Many Requests",
        "{\"schema\":\"gh.registration.portal-error/1\","
        "\"reason\":\"rate_limited\"}");
  }
  return send_json_(
      request,
      "409 Conflict",
      "{\"schema\":\"gh.registration.portal-result/1\","
      "\"status\":\"not_ready\","
      "\"reason\":\"discovery_stage_pending\"}");
}

esp_err_t RegistrationPortal::register_page_handler_(
    httpd_req_t *request) {
  auto *self =
      static_cast<RegistrationPortal *>(request->user_ctx);
  return self == nullptr
             ? ESP_FAIL
             : self->handle_register_page_(request);
}

esp_err_t RegistrationPortal::start_handler_(
    httpd_req_t *request) {
  auto *self =
      static_cast<RegistrationPortal *>(request->user_ctx);
  return self == nullptr ? ESP_FAIL : self->handle_start_(request);
}

esp_err_t RegistrationPortal::status_handler_(
    httpd_req_t *request) {
  auto *self =
      static_cast<RegistrationPortal *>(request->user_ctx);
  return self == nullptr ? ESP_FAIL : self->handle_status_(request);
}

esp_err_t RegistrationPortal::confirm_handler_(
    httpd_req_t *request) {
  auto *self =
      static_cast<RegistrationPortal *>(request->user_ctx);
  return self == nullptr
             ? ESP_FAIL
             : self->handle_not_ready_(request);
}

esp_err_t RegistrationPortal::retry_handler_(
    httpd_req_t *request) {
  auto *self =
      static_cast<RegistrationPortal *>(request->user_ctx);
  return self == nullptr
             ? ESP_FAIL
             : self->handle_not_ready_(request);
}

}  // namespace esphome::greenhouse_n3w_core
