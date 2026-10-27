#include "n3w_registration_portal.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <string>
#include <utility>
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
constexpr uint32_t kMinDynamicRequestIntervalMs = 100;

const char kPortalPage[] = R"HTML(<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>联机注册</title>
<style>
body{font-family:sans-serif;margin:2rem;max-width:32rem}
button{display:block;font-size:1.05rem;padding:.7rem 1rem;margin:.6rem 0;max-width:100%}
#status{margin-top:1rem}
</style>
</head>
<body>
<h1>联机注册</h1>
<p id="node"></p>
<p id="status">正在准备联机注册…</p>
<div id="choices"></div>
<script>
(() => {
  const node = document.getElementById("node");
  const out = document.getElementById("status");
  const choices = document.getElementById("choices");
  const params = new URLSearchParams(location.hash.slice(1));
  const token = params.get("t");
  history.replaceState(null, "", location.pathname);
  let stopped = false;

  if (!token) {
    out.textContent = "二维码已失效，请重新扫码";
    return;
  }

  const post = async (path, extra = {}) => {
    const response = await fetch(path, {
      method: "POST",
      cache: "no-store",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(Object.assign({
        schema: "gh.registration.portal-action/1",
        token: token
      }, extra))
    });
    const body = await response.json();
    return {response, body};
  };

  const clearChoices = () => {
    while (choices.firstChild) choices.removeChild(choices.firstChild);
  };

  const confirmCandidate = async (candidateId) => {
    clearChoices();
    out.textContent = "正在联机注册，请查看设备屏幕";
    try {
      const result = await post("/api/v1/register/confirm", {
        candidate_id: candidateId
      });
      if (result.body.reason === "candidate_stale") {
        out.textContent = "主机信息已失效，请重试";
        stopped = false;
        await showRetry();
      }
    } catch (_) {
      out.textContent = "操作失败，请重试";
      stopped = false;
      await showRetry();
    }
  };

  const showRetry = async () => {
    clearChoices();
    const button = document.createElement("button");
    button.textContent = "重新查找";
    button.onclick = async () => {
      button.disabled = true;
      try {
        await post("/api/v1/register/retry");
        out.textContent = "正在查找主机";
        stopped = false;
        setTimeout(poll, 250);
      } catch (_) {
        button.disabled = false;
      }
    };
    choices.appendChild(button);
  };

  const render = async (body) => {
    clearChoices();
    if (typeof body.node_label === "string") {
      node.textContent = body.node_label;
    }
    if (body.status === "discovering") {
      out.textContent = "正在查找主机";
      return;
    }
    if (body.status === "wait_confirm") {
      out.textContent = "请选择要连接的温室主机";
      const list = Array.isArray(body.candidates) ? body.candidates : [];
      list.forEach(candidate => {
        const button = document.createElement("button");
        button.textContent = candidate.label;
        button.onclick = () => confirmCandidate(candidate.id);
        choices.appendChild(button);
      });
      return;
    }
    if (body.status === "no_candidate") {
      out.textContent = "未找到主机，请查看设备屏幕";
      stopped = true;
      await showRetry();
      return;
    }
    if (body.status === "selected_pending_bootstrap") {
      out.textContent = "正在联机注册，请查看设备屏幕";
      stopped = true;
      return;
    }
    out.textContent = "正在准备联机注册…";
  };

  const poll = async () => {
    if (stopped) return;
    try {
      const result = await post("/api/v1/register/status");
      if (result.response.status === 429) {
        setTimeout(poll, 500);
        return;
      }
      if (!result.response.ok) throw new Error("status rejected");
      await render(result.body);
      if (!stopped) setTimeout(poll, 750);
    } catch (_) {
      out.textContent = "连接中断，请重新扫码";
      stopped = true;
    }
  };

  post("/api/v1/register/start").then(result => {
    if (!result.response.ok) throw new Error("start rejected");
    out.textContent = "正在查找主机";
    setTimeout(poll, 250);
  }).catch(() => {
    out.textContent = "二维码已失效，请重新扫码";
    stopped = true;
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

const char *stage_name(RegistrationPortalStage stage) {
  switch (stage) {
    case RegistrationPortalStage::DISCOVERING:
      return "discovering";
    case RegistrationPortalStage::WAIT_CONFIRM:
      return "wait_confirm";
    case RegistrationPortalStage::ERROR_NO_CANDIDATE:
      return "no_candidate";
    case RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP:
      return "selected_pending_bootstrap";
    case RegistrationPortalStage::IDLE:
    default:
      return "idle";
  }
}

}  // namespace

RegistrationPortal::RegistrationPortal(
    RegistrationPortalRandom *random,
    RegistrationPortalState *state)
    : random_(random), state_(state) {}

RegistrationPortal::~RegistrationPortal() {
  stop();
}

uint64_t RegistrationPortal::monotonic_ms_() {
  const int64_t now_us = esp_timer_get_time();
  return now_us <= 0 ? 0U : static_cast<uint64_t>(now_us / 1000);
}

RegistrationPortalStage RegistrationPortal::discovery_stage() const {
  std::lock_guard<std::mutex> lock(discovery_mutex_);
  return discovery_stage_;
}

void RegistrationPortal::set_discovery_in_progress() {
  std::lock_guard<std::mutex> lock(discovery_mutex_);
  candidates_.clear();
  selected_candidate_id_.clear();
  discovery_stage_ = RegistrationPortalStage::DISCOVERING;
}

void RegistrationPortal::set_node_label(const std::string &node_label) {
  std::lock_guard<std::mutex> lock(discovery_mutex_);
  node_label_ = node_label;
}

void RegistrationPortal::set_candidates(
    const std::vector<RegistrationPortalCandidateView> &candidates) {
  std::lock_guard<std::mutex> lock(discovery_mutex_);
  candidates_ = candidates;
  selected_candidate_id_.clear();
  discovery_stage_ = candidates_.empty()
                         ? RegistrationPortalStage::ERROR_NO_CANDIDATE
                         : RegistrationPortalStage::WAIT_CONFIRM;
}

void RegistrationPortal::set_no_candidates() {
  std::lock_guard<std::mutex> lock(discovery_mutex_);
  candidates_.clear();
  selected_candidate_id_.clear();
  discovery_stage_ = RegistrationPortalStage::ERROR_NO_CANDIDATE;
}

void RegistrationPortal::clear_discovery_session() {
  std::lock_guard<std::mutex> lock(discovery_mutex_);
  candidates_.clear();
  selected_candidate_id_.clear();
  discovery_stage_ = RegistrationPortalStage::IDLE;
  scan_trigger_pending_.store(false, std::memory_order_release);
}

bool RegistrationPortal::take_selected_candidate_id(
    std::string *candidate_id) {
  if (candidate_id == nullptr) return false;
  std::lock_guard<std::mutex> lock(discovery_mutex_);
  if (selected_candidate_id_.empty()) return false;
  *candidate_id = selected_candidate_id_;
  selected_candidate_id_.clear();
  return true;
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
  last_dynamic_request_ms_.store(0, std::memory_order_release);
  candidate_stale_event_pending_.store(false, std::memory_order_release);
  candidate_list_expired_event_pending_.store(false, std::memory_order_release);
  clear_discovery_session();
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
  last_dynamic_request_ms_.store(0, std::memory_order_release);
  candidate_stale_event_pending_.store(false, std::memory_order_release);
  candidate_list_expired_event_pending_.store(false, std::memory_order_release);
  clear_discovery_session();
}

bool RegistrationPortal::request_is_local_(httpd_req_t *request) const {
  if (request == nullptr || local_addr_ == 0U || mask_addr_ == 0U ||
      state_ == nullptr || !state_->registration_portal_allowed()) {
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
  const int64_t now_us = esp_timer_get_time();
  if (now_us <= 0) return false;
  const uint32_t now_ms =
      static_cast<uint32_t>(now_us / 1000);
  const uint32_t previous =
      last_dynamic_request_ms_.exchange(
          now_ms, std::memory_order_acq_rel);
  return previous == 0U ||
         static_cast<uint32_t>(now_ms - previous) >=
             kMinDynamicRequestIntervalMs;
}

bool RegistrationPortal::read_action_request_(
    httpd_req_t *request,
    bool require_candidate_id,
    std::string *candidate_id) {
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
  const std::size_t expected_fields = require_candidate_id ? 3U : 2U;
  if (root.isNull() ||
      root.size() != expected_fields ||
      !root["schema"].is<const char *>() ||
      !root["token"].is<const char *>()) {
    return false;
  }
  const char *schema = root["schema"].as<const char *>();
  const char *token = root["token"].as<const char *>();
  if (schema == nullptr || token == nullptr ||
      std::strcmp(
          schema,
          "gh.registration.portal-action/1") != 0 ||
      !constant_time_equal(token, scan_token_)) {
    return false;
  }

  if (!require_candidate_id) {
    if (candidate_id != nullptr) candidate_id->clear();
    return true;
  }
  if (candidate_id == nullptr ||
      !root["candidate_id"].is<const char *>()) {
    return false;
  }
  const char *raw_candidate_id =
      root["candidate_id"].as<const char *>();
  if (raw_candidate_id == nullptr ||
      raw_candidate_id[0] == '\0' ||
      std::strlen(raw_candidate_id) > 16U) {
    return false;
  }
  *candidate_id = raw_candidate_id;
  return true;
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

esp_err_t RegistrationPortal::send_json_(
    httpd_req_t *request,
    const char *status,
    const std::string &body) const {
  return send_json_(request, status, body.c_str());
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
      !read_action_request_(request, false, nullptr)) {
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

  {
    std::lock_guard<std::mutex> lock(discovery_mutex_);
    if (discovery_stage_ == RegistrationPortalStage::IDLE ||
        discovery_stage_ == RegistrationPortalStage::ERROR_NO_CANDIDATE) {
      candidates_.clear();
      selected_candidate_id_.clear();
      discovery_stage_ = RegistrationPortalStage::DISCOVERING;
      scan_trigger_pending_.store(true, std::memory_order_release);
    }
  }

  return send_json_(
      request,
      "202 Accepted",
      "{\"schema\":\"gh.registration.portal-result/1\","
      "\"status\":\"accepted\",\"next\":\"discovery\"}");
}

esp_err_t RegistrationPortal::handle_status_(httpd_req_t *request) {
  if (!request_is_local_(request) ||
      !read_action_request_(request, false, nullptr)) {
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

  RegistrationPortalStage stage;
  std::string node_label;
  std::vector<RegistrationPortalCandidateView> candidates;
  const uint64_t now_ms = monotonic_ms_();
  {
    std::lock_guard<std::mutex> lock(discovery_mutex_);
    if (discovery_stage_ == RegistrationPortalStage::WAIT_CONFIRM) {
      candidates_.erase(
          std::remove_if(
              candidates_.begin(),
              candidates_.end(),
              [&](const RegistrationPortalCandidateView &candidate) {
                return candidate.expires_at_ms == 0U ||
                       now_ms == 0U ||
                       now_ms >= candidate.expires_at_ms;
              }),
          candidates_.end());
      if (candidates_.empty()) {
        discovery_stage_ = RegistrationPortalStage::ERROR_NO_CANDIDATE;
        candidate_list_expired_event_pending_.store(
            true, std::memory_order_release);
      }
    }
    stage = discovery_stage_;
    node_label = node_label_;
    candidates = candidates_;
  }

  const std::string body = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.registration.portal-status/1";
    root["status"] = stage_name(stage);
    root["node_label"] = node_label;
    if (stage == RegistrationPortalStage::WAIT_CONFIRM) {
      JsonArray values = root["candidates"].to<JsonArray>();
      for (const RegistrationPortalCandidateView &candidate : candidates) {
        JsonObject item = values.add<JsonObject>();
        item["id"] = candidate.id;
        item["label"] = candidate.label;
      }
    }
  });
  return send_json_(request, "200 OK", body);
}

esp_err_t RegistrationPortal::handle_confirm_(httpd_req_t *request) {
  std::string candidate_id;
  if (!request_is_local_(request) ||
      !read_action_request_(request, true, &candidate_id)) {
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

  const uint64_t now_ms = monotonic_ms_();
  bool accepted = false;
  {
    std::lock_guard<std::mutex> lock(discovery_mutex_);
    if (discovery_stage_ == RegistrationPortalStage::WAIT_CONFIRM &&
        now_ms != 0U) {
      const auto found = std::find_if(
          candidates_.begin(),
          candidates_.end(),
          [&](const RegistrationPortalCandidateView &candidate) {
            return candidate.id == candidate_id &&
                   candidate.expires_at_ms > now_ms;
          });
      if (found != candidates_.end()) {
        selected_candidate_id_ = candidate_id;
        discovery_stage_ =
            RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP;
        accepted = true;
      }
    }
  }

  if (!accepted) {
    candidate_stale_event_pending_.store(true, std::memory_order_release);
    return send_json_(
        request,
        "409 Conflict",
        "{\"schema\":\"gh.registration.portal-result/1\","
        "\"status\":\"not_ready\","
        "\"reason\":\"candidate_stale\"}");
  }

  return send_json_(
      request,
      "202 Accepted",
      "{\"schema\":\"gh.registration.portal-result/1\","
      "\"status\":\"accepted\",\"next\":\"bootstrap\"}");
}

esp_err_t RegistrationPortal::handle_retry_(httpd_req_t *request) {
  if (!request_is_local_(request) ||
      !read_action_request_(request, false, nullptr)) {
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

  {
    std::lock_guard<std::mutex> lock(discovery_mutex_);
    if (discovery_stage_ != RegistrationPortalStage::DISCOVERING) {
      candidates_.clear();
      selected_candidate_id_.clear();
      discovery_stage_ = RegistrationPortalStage::DISCOVERING;
      scan_trigger_pending_.store(true, std::memory_order_release);
    }
  }

  return send_json_(
      request,
      "202 Accepted",
      "{\"schema\":\"gh.registration.portal-result/1\","
      "\"status\":\"accepted\",\"next\":\"discovery\"}");
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
  return self == nullptr ? ESP_FAIL : self->handle_confirm_(request);
}

esp_err_t RegistrationPortal::retry_handler_(
    httpd_req_t *request) {
  auto *self =
      static_cast<RegistrationPortal *>(request->user_ctx);
  return self == nullptr ? ESP_FAIL : self->handle_retry_(request);
}

}  // namespace esphome::greenhouse_n3w_core
