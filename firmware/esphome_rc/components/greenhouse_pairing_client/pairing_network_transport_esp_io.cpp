#include "pairing_network_transport.h"

#ifdef USE_ESP32

#include <algorithm>
#include <array>
#include <cerrno>
#include <cctype>
#include <cstring>

#include <arpa/inet.h>
#include <strings.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include "esp_http_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mdns.h"

namespace esphome::greenhouse_pairing_client {

namespace {

void secure_clear(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

const char *txt_value(const mdns_result_t *result, const char *key) {
  if (result == nullptr || key == nullptr)
    return nullptr;
  for (size_t index = 0; index < result->txt_count; index++) {
    const mdns_txt_item_t &item = result->txt[index];
    if (item.key != nullptr && std::strcmp(item.key, key) == 0)
      return item.value;
  }
  return nullptr;
}

bool exact_mdns_txt(const mdns_result_t *result) {
  static constexpr std::array<const char *, 8> REQUIRED = {
      "schema", "manager_id", "system_id", "scheme", "pairing_path", "protocol", "priority", "ttl_s"};
  if (result == nullptr || result->txt_count != REQUIRED.size())
    return false;
  for (const char *key : REQUIRED) {
    if (txt_value(result, key) == nullptr)
      return false;
  }
  for (size_t index = 0; index < result->txt_count; index++) {
    bool known = false;
    for (const char *key : REQUIRED)
      known = known || (result->txt[index].key != nullptr &&
                        std::strcmp(result->txt[index].key, key) == 0);
    if (!known)
      return false;
  }
  return true;
}

struct HttpCollector {
  std::string body;
  std::string content_type;
  size_t maximum{HTTP_RESPONSE_MAX_BYTES};
  bool overflow{false};
  bool redirect{false};
};

esp_err_t http_event(esp_http_client_event_t *event) {
  if (event == nullptr || event->user_data == nullptr)
    return ESP_FAIL;
  auto *collector = static_cast<HttpCollector *>(event->user_data);
  if (event->event_id == HTTP_EVENT_ON_HEADER && event->header_key != nullptr &&
      event->header_value != nullptr) {
    if (strcasecmp(event->header_key, "Content-Type") == 0) {
      collector->content_type = event->header_value;
      const size_t separator = collector->content_type.find(';');
      if (separator != std::string::npos)
        collector->content_type.erase(separator);
      while (!collector->content_type.empty() && collector->content_type.back() == ' ')
        collector->content_type.pop_back();
      size_t start = 0;
      while (start < collector->content_type.size() && collector->content_type[start] == ' ')
        start++;
      if (start != 0)
        collector->content_type.erase(0, start);
      std::transform(collector->content_type.begin(), collector->content_type.end(),
                     collector->content_type.begin(), [](unsigned char value) {
                       return static_cast<char>(std::tolower(value));
                     });
    } else if (strcasecmp(event->header_key, "Location") == 0) {
      collector->redirect = true;
    } else if (strcasecmp(event->header_key, "Content-Length") == 0) {
      uint32_t content_length = 0;
      if (!PairingTransportCore::parse_uint32(event->header_value, &content_length) ||
          content_length > collector->maximum) {
        collector->overflow = true;
        return ESP_FAIL;
      }
    }
  } else if (event->event_id == HTTP_EVENT_ON_DATA && event->data != nullptr &&
             event->data_len > 0) {
    const size_t incoming = static_cast<size_t>(event->data_len);
    if (incoming > collector->maximum || collector->body.size() > collector->maximum - incoming) {
      collector->overflow = true;
      return ESP_FAIL;
    }
    collector->body.append(static_cast<const char *>(event->data), incoming);
  }
  return ESP_OK;
}

}  // namespace

bool PairingNetworkTransport::browse_mdns_(PairingClientCore *core, uint32_t now_ms) {
  mdns_result_t *results = nullptr;
  const esp_err_t status = mdns_query_ptr("_greenhouse", "_tcp",
                                          this->options_.limits.mdns_timeout_ms, 16,
                                          &results);
  if (status != ESP_OK || results == nullptr) {
    if (results != nullptr)
      mdns_query_results_free(results);
    return false;
  }
  bool observed = false;
  for (mdns_result_t *result = results; result != nullptr; result = result->next) {
    if (!exact_mdns_txt(result) || result->hostname == nullptr || result->port == 0)
      continue;
    uint16_t priority = 0;
    uint16_t ttl_s = 0;
    const char *priority_text = txt_value(result, "priority");
    const char *ttl_text = txt_value(result, "ttl_s");
    const char *pairing_path = txt_value(result, "pairing_path");
    if (priority_text == nullptr || ttl_text == nullptr || pairing_path == nullptr ||
        !PairingTransportCore::parse_uint16(priority_text, &priority) ||
        !PairingTransportCore::parse_uint16(ttl_text, &ttl_s) ||
        !PairingTransportCore::validate_pairing_path(pairing_path))
      continue;
    ManagerCandidate candidate{
        .schema = txt_value(result, "schema"),
        .manager_id = txt_value(result, "manager_id"),
        .system_id = txt_value(result, "system_id"),
        .host = std::string(result->hostname) + ".local",
        .scheme = txt_value(result, "scheme"),
        .port = result->port,
        .pairing_path = pairing_path,
        .protocol = txt_value(result, "protocol"),
        .priority = priority,
        .ttl_s = ttl_s,
    };
    observed = core->observe_candidate(core->request_id(), core->nonce(), candidate, now_ms) ||
               observed;
  }
  mdns_query_results_free(results);
  return observed;
}

bool PairingNetworkTransport::discover_udp_(PairingClientCore *core,
                                             const std::string &query_json,
                                             uint32_t now_ms) {
  if (!PairingTransportCore::validate_udp_target(this->options_.udp_target))
    return false;
  sockaddr_in target{};
  target.sin_family = AF_INET;
  target.sin_port = htons(this->options_.limits.udp_port);
  if (inet_pton(AF_INET, this->options_.udp_target.c_str(), &target.sin_addr) != 1)
    return false;

  const int descriptor = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  if (descriptor < 0)
    return false;
  int enabled = 1;
  timeval timeout{
      .tv_sec = 0,
      .tv_usec = 250000,
  };
  const bool configured =
      setsockopt(descriptor, SOL_SOCKET, SO_BROADCAST, &enabled, sizeof(enabled)) == 0 &&
      setsockopt(descriptor, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) == 0;
  if (!configured) {
    close(descriptor);
    return false;
  }

  bool observed = false;
  std::array<char, UDP_DISCOVERY_MAX_DATAGRAM + 1> buffer{};
  for (uint8_t attempt = 0; attempt < this->options_.limits.udp_attempts && !observed; attempt++) {
    const ssize_t sent = sendto(descriptor, query_json.data(), query_json.size(), 0,
                                reinterpret_cast<const sockaddr *>(&target), sizeof(target));
    if (sent != static_cast<ssize_t>(query_json.size()))
      continue;

    size_t responses = 0;
    while (responses < UDP_DISCOVERY_MAX_RESPONSES_PER_ATTEMPT) {
      responses++;
      sockaddr_in source{};
      socklen_t source_length = sizeof(source);
      const ssize_t received = recvfrom(descriptor, buffer.data(), UDP_DISCOVERY_MAX_DATAGRAM, 0,
                                        reinterpret_cast<sockaddr *>(&source), &source_length);
      if (received < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK)
          break;
        break;
      }
      if (received == 0 || received > static_cast<ssize_t>(UDP_DISCOVERY_MAX_DATAGRAM))
        continue;
      char address[INET_ADDRSTRLEN]{};
      if (inet_ntop(AF_INET, &source.sin_addr, address, sizeof(address)) == nullptr ||
          !PairingClientCore::valid_local_host(address))
        continue;
      buffer[static_cast<size_t>(received)] = '\0';
      observed = this->parse_discovery_response_(
                     std::string(buffer.data(), static_cast<size_t>(received)), core, now_ms) ||
                 observed;
    }
    if (!observed && attempt + 1 < this->options_.limits.udp_attempts) {
      const uint32_t delay = PairingTransportCore::retry_delay_ms(this->options_.limits, attempt);
      if (delay != 0)
        vTaskDelay(pdMS_TO_TICKS(delay));
    }
  }
  std::fill(buffer.begin(), buffer.end(), '\0');
  close(descriptor);
  return observed;
}

bool PairingNetworkTransport::post_json_(const std::string &url, const std::string &body,
                                         HttpResponse *response) {
  if (response == nullptr)
    return false;
  secure_clear(&response->body);
  secure_clear(&response->content_type);
  response->status_code = 0;
  response->redirect_observed = false;
  if (url.empty() || body.empty() || body.size() > HTTP_RESPONSE_MAX_BYTES)
    return false;

  HttpCollector collector{
      .body = {},
      .content_type = {},
      .maximum = this->options_.limits.response_max_bytes,
      .overflow = false,
      .redirect = false,
  };
  esp_http_client_config_t config{};
  config.url = url.c_str();
  config.event_handler = http_event;
  config.user_data = &collector;
  config.timeout_ms = static_cast<int>(this->options_.limits.http_timeout_ms);
  config.disable_auto_redirect = true;
  config.max_redirection_count = 0;
  config.keep_alive_enable = false;
  config.buffer_size = 1024;
  config.buffer_size_tx = 1024;

  esp_http_client_handle_t client = esp_http_client_init(&config);
  if (client == nullptr)
    return false;
  bool success = esp_http_client_set_method(client, HTTP_METHOD_POST) == ESP_OK &&
                 esp_http_client_set_header(client, "Content-Type", "application/json") == ESP_OK &&
                 esp_http_client_set_header(client, "Accept", "application/json") == ESP_OK &&
                 esp_http_client_set_header(client, "Cache-Control", "no-store") == ESP_OK &&
                 esp_http_client_set_header(client, "Connection", "close") == ESP_OK &&
                 esp_http_client_set_post_field(client, body.data(),
                                                static_cast<int>(body.size())) == ESP_OK &&
                 esp_http_client_perform(client) == ESP_OK;
  const int status_code = esp_http_client_get_status_code(client);
  if (status_code >= 300 && status_code <= 399)
    collector.redirect = true;
  esp_http_client_cleanup(client);

  const HttpResponseMetadata metadata{
      .status_code = status_code,
      .content_type = collector.content_type,
      .body_size = collector.body.size(),
      .redirect_observed = collector.redirect,
  };
  success = success && !collector.overflow &&
            collector.body.size() <= this->options_.limits.response_max_bytes &&
            PairingTransportCore::validate_http_response(metadata);
  if (!success) {
    secure_clear(&collector.body);
    secure_clear(&collector.content_type);
    return false;
  }
  response->status_code = status_code;
  response->content_type = std::move(collector.content_type);
  response->body = std::move(collector.body);
  response->redirect_observed = collector.redirect;
  return true;
}

}  // namespace esphome::greenhouse_pairing_client

#endif
