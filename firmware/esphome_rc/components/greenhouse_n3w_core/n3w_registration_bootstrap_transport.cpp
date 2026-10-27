#include "n3w_registration_bootstrap_transport.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <unistd.h>

#include "esp_timer.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"
#include "mbedtls/md.h"
#include "mbedtls/net_sockets.h"
#include "mbedtls/ssl.h"
#include "mbedtls/x509_crt.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint32_t kConnectTimeoutMs = 4000;
constexpr uint32_t kTlsHandshakeTimeoutMs = 5000;
constexpr uint32_t kHttpIoTimeoutMs = 5000;
constexpr std::size_t kMaxRequestBodyBytes = 2048;
constexpr std::size_t kMaxResponseBytes = 8192;
constexpr std::size_t kMaxHeaderBytes = 4096;

uint64_t monotonic_ms() {
  const int64_t now_us = esp_timer_get_time();
  return now_us <= 0 ? 0U : static_cast<uint64_t>(now_us / 1000);
}

void secure_clear(std::string *value) {
  if (value == nullptr) return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
}

bool deadline_expired(uint64_t deadline_ms) {
  const uint64_t now = monotonic_ms();
  return now == 0U || now >= deadline_ms;
}

bool parse_hex_sha256(
    const std::string &text,
    std::array<uint8_t, 32> *digest) {
  if (digest == nullptr || text.size() != 64U) return false;
  const auto nibble = [](char ch, uint8_t *value) {
    if (value == nullptr) return false;
    if (ch >= '0' && ch <= '9') {
      *value = static_cast<uint8_t>(ch - '0');
      return true;
    }
    if (ch >= 'a' && ch <= 'f') {
      *value = static_cast<uint8_t>(10 + ch - 'a');
      return true;
    }
    return false;
  };
  for (std::size_t index = 0; index < digest->size(); ++index) {
    uint8_t high = 0;
    uint8_t low = 0;
    if (!nibble(text[index * 2U], &high) ||
        !nibble(text[index * 2U + 1U], &low)) {
      digest->fill(0);
      return false;
    }
    (*digest)[index] = static_cast<uint8_t>((high << 4U) | low);
  }
  return true;
}

bool constant_time_equal(
    const std::array<uint8_t, 32> &left,
    const std::array<uint8_t, 32> &right) {
  uint8_t diff = 0;
  for (std::size_t index = 0; index < left.size(); ++index) {
    diff = static_cast<uint8_t>(diff | (left[index] ^ right[index]));
  }
  return diff == 0U;
}

struct VerifyContext {
  std::array<uint8_t, 32> expected{};
  bool leaf_seen{false};
  bool leaf_matched{false};
  bool pin_mismatch{false};
};

int verify_pinned_leaf(
    void *context,
    mbedtls_x509_crt *certificate,
    int depth,
    uint32_t *flags) {
  auto *verify = static_cast<VerifyContext *>(context);
  if (verify == nullptr || certificate == nullptr || flags == nullptr) {
    return MBEDTLS_ERR_X509_CERT_VERIFY_FAILED;
  }

  // The selected R5 candidate is the trust authority. CA/hostname validation is
  // intentionally not substituted for it. All chain flags are ignored only
  // after the exact leaf pin has been evaluated at depth zero.
  if (depth == 0) {
    verify->leaf_seen = true;
    std::array<uint8_t, 32> observed{};
    const mbedtls_md_info_t *info =
        mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    if (info == nullptr || certificate->raw.p == nullptr ||
        certificate->raw.len == 0U ||
        mbedtls_md(
            info,
            certificate->raw.p,
            certificate->raw.len,
            observed.data()) != 0 ||
        !constant_time_equal(observed, verify->expected)) {
      observed.fill(0);
      verify->pin_mismatch = true;
      return MBEDTLS_ERR_X509_CERT_VERIFY_FAILED;
    }
    observed.fill(0);
    verify->leaf_matched = true;
  }
  *flags = 0U;
  return 0;
}

struct SocketBio {
  int fd{-1};
  uint64_t deadline_ms{0};
};

int tls_send(
    void *context,
    const unsigned char *buffer,
    std::size_t length) {
  auto *bio = static_cast<SocketBio *>(context);
  if (bio == nullptr || bio->fd < 0 || buffer == nullptr ||
      length == 0U || deadline_expired(bio->deadline_ms)) {
    return MBEDTLS_ERR_SSL_TIMEOUT;
  }
  const ssize_t sent = ::send(bio->fd, buffer, length, 0);
  if (sent > 0) return static_cast<int>(sent);
  if (sent == 0) return MBEDTLS_ERR_NET_CONN_RESET;
  if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
    return MBEDTLS_ERR_SSL_WANT_WRITE;
  }
  return MBEDTLS_ERR_NET_SEND_FAILED;
}

int tls_recv(
    void *context,
    unsigned char *buffer,
    std::size_t length) {
  auto *bio = static_cast<SocketBio *>(context);
  if (bio == nullptr || bio->fd < 0 || buffer == nullptr ||
      length == 0U || deadline_expired(bio->deadline_ms)) {
    return MBEDTLS_ERR_SSL_TIMEOUT;
  }
  const ssize_t received = ::recv(bio->fd, buffer, length, 0);
  if (received > 0) return static_cast<int>(received);
  if (received == 0) return 0;
  if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
    return MBEDTLS_ERR_SSL_WANT_READ;
  }
  return MBEDTLS_ERR_NET_RECV_FAILED;
}

bool connect_ipv4(
    const std::string &host,
    uint16_t port,
    int *fd) {
  if (fd == nullptr || host.empty() || port == 0U) return false;
  in_addr address{};
  if (::inet_pton(AF_INET, host.c_str(), &address) != 1) return false;

  const int socket_fd = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (socket_fd < 0) return false;

  timeval timeout{};
  timeout.tv_sec = 1;
  timeout.tv_usec = 0;
  if (::setsockopt(
          socket_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout,
          sizeof(timeout)) != 0 ||
      ::setsockopt(
          socket_fd, SOL_SOCKET, SO_SNDTIMEO, &timeout,
          sizeof(timeout)) != 0) {
    ::close(socket_fd);
    return false;
  }

  sockaddr_in target{};
  target.sin_family = AF_INET;
  target.sin_port = htons(port);
  target.sin_addr = address;

  // lwIP connect() observes SO_SNDTIMEO. Keep the call bounded and reject
  // anything that is not the exact selected IPv4 endpoint.
  const uint64_t started = monotonic_ms();
  if (started == 0U ||
      ::connect(
          socket_fd,
          reinterpret_cast<const sockaddr *>(&target),
          sizeof(target)) != 0 ||
      monotonic_ms() - started > kConnectTimeoutMs) {
    ::close(socket_fd);
    return false;
  }
  *fd = socket_fd;
  return true;
}

bool tls_write_all(
    mbedtls_ssl_context *ssl,
    SocketBio *bio,
    const std::string &request) {
  if (ssl == nullptr || bio == nullptr || request.empty()) return false;
  bio->deadline_ms = monotonic_ms() + kHttpIoTimeoutMs;
  std::size_t offset = 0;
  while (offset < request.size() && !deadline_expired(bio->deadline_ms)) {
    const int written = mbedtls_ssl_write(
        ssl,
        reinterpret_cast<const unsigned char *>(request.data() + offset),
        request.size() - offset);
    if (written > 0) {
      offset += static_cast<std::size_t>(written);
      continue;
    }
    if (written == MBEDTLS_ERR_SSL_WANT_READ ||
        written == MBEDTLS_ERR_SSL_WANT_WRITE) {
      continue;
    }
    return false;
  }
  return offset == request.size();
}

bool tls_read_bounded(
    mbedtls_ssl_context *ssl,
    SocketBio *bio,
    std::string *raw_response,
    bool *overflow) {
  if (ssl == nullptr || bio == nullptr || raw_response == nullptr ||
      overflow == nullptr) {
    return false;
  }
  raw_response->clear();
  *overflow = false;
  bio->deadline_ms = monotonic_ms() + kHttpIoTimeoutMs;
  std::array<unsigned char, 1024> buffer{};
  while (!deadline_expired(bio->deadline_ms)) {
    const int received =
        mbedtls_ssl_read(ssl, buffer.data(), buffer.size());
    if (received > 0) {
      const std::size_t incoming = static_cast<std::size_t>(received);
      if (incoming > kMaxResponseBytes ||
          raw_response->size() > kMaxResponseBytes - incoming) {
        *overflow = true;
        return false;
      }
      raw_response->append(
          reinterpret_cast<const char *>(buffer.data()), incoming);
      continue;
    }
    if (received == 0 ||
        received == MBEDTLS_ERR_SSL_PEER_CLOSE_NOTIFY) {
      return !raw_response->empty();
    }
    if (received == MBEDTLS_ERR_SSL_WANT_READ ||
        received == MBEDTLS_ERR_SSL_WANT_WRITE) {
      continue;
    }
    return false;
  }
  return false;
}

std::string lower_ascii(std::string value) {
  std::transform(
      value.begin(), value.end(), value.begin(),
      [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
      });
  return value;
}

bool parse_decimal_size(
    const std::string &text,
    std::size_t *value) {
  if (value == nullptr || text.empty()) return false;
  std::size_t parsed = 0;
  for (char ch : text) {
    if (ch < '0' || ch > '9') return false;
    const std::size_t digit = static_cast<std::size_t>(ch - '0');
    if (parsed > (std::numeric_limits<std::size_t>::max() - digit) / 10U) {
      return false;
    }
    parsed = parsed * 10U + digit;
  }
  *value = parsed;
  return true;
}

bool parse_http_response(
    const std::string &raw,
    RegistrationBootstrapHttpResponse *response) {
  if (response == nullptr || raw.empty() || raw.size() > kMaxResponseBytes) {
    return false;
  }
  const std::size_t header_end = raw.find("\r\n\r\n");
  if (header_end == std::string::npos || header_end > kMaxHeaderBytes) {
    return false;
  }
  const std::size_t first_line_end = raw.find("\r\n");
  if (first_line_end == std::string::npos || first_line_end >= header_end) {
    return false;
  }
  const std::string status_line = raw.substr(0, first_line_end);
  if (status_line.rfind("HTTP/1.", 0) != 0U || status_line.size() < 12U ||
      status_line[8] != ' ') {
    return false;
  }
  int status = 0;
  for (std::size_t index = 9; index < 12U; ++index) {
    const char ch = status_line[index];
    if (ch < '0' || ch > '9') return false;
    status = status * 10 + static_cast<int>(ch - '0');
  }
  if (status < 100 || status > 599 ||
      (status >= 300 && status <= 399)) {
    return false;
  }

  bool content_length_seen = false;
  bool content_type_seen = false;
  std::size_t content_length = 0;
  std::size_t cursor = first_line_end + 2U;
  while (cursor < header_end) {
    const std::size_t line_end = raw.find("\r\n", cursor);
    if (line_end == std::string::npos || line_end > header_end) return false;
    const std::string line = raw.substr(cursor, line_end - cursor);
    const std::size_t separator = line.find(':');
    if (separator == std::string::npos) return false;
    const std::string key = lower_ascii(line.substr(0, separator));
    std::string value = line.substr(separator + 1U);
    while (!value.empty() && value.front() == ' ') value.erase(value.begin());
    while (!value.empty() && value.back() == ' ') value.pop_back();

    if (key == "content-length") {
      if (content_length_seen ||
          !parse_decimal_size(value, &content_length) ||
          content_length > kMaxResponseBytes) {
        return false;
      }
      content_length_seen = true;
    } else if (key == "content-type") {
      if (content_type_seen) return false;
      const std::size_t semicolon = value.find(';');
      const std::string media = lower_ascii(
          value.substr(0, semicolon));
      if (media != "application/json") return false;
      content_type_seen = true;
    } else if (key == "transfer-encoding" || key == "location") {
      return false;
    }
    cursor = line_end + 2U;
  }

  if (!content_length_seen || !content_type_seen) return false;
  const std::size_t body_start = header_end + 4U;
  if (body_start > raw.size() ||
      raw.size() - body_start != content_length) {
    return false;
  }

  response->status_code = status;
  response->body.assign(raw.data() + body_start, content_length);
  return true;
}

}  // namespace

void RegistrationBootstrapHttpResponse::clear() {
  status_code = 0;
  secure_clear(&body);
}

bool Esp32RegistrationBootstrapTransport::post_json(
    const std::string &host,
    uint16_t port,
    const std::string &leaf_sha256,
    const std::string &path,
    const std::string &request_json,
    RegistrationBootstrapHttpResponse *response,
    RegistrationBootstrapTransportError *error) {
  if (response == nullptr || error == nullptr) return false;
  response->clear();
  *error = RegistrationBootstrapTransportError::INVALID_ARGUMENT;

  std::array<uint8_t, 32> expected_pin{};
  if (host.empty() || port == 0U || path.empty() || path.front() != '/' ||
      request_json.empty() || request_json.size() > kMaxRequestBodyBytes ||
      !parse_hex_sha256(leaf_sha256, &expected_pin)) {
    return false;
  }

  int fd = -1;
  if (!connect_ipv4(host, port, &fd)) {
    expected_pin.fill(0);
    *error = RegistrationBootstrapTransportError::CONNECT_FAILED;
    return false;
  }

  mbedtls_entropy_context entropy;
  mbedtls_ctr_drbg_context ctr_drbg;
  mbedtls_ssl_context ssl;
  mbedtls_ssl_config config;
  mbedtls_entropy_init(&entropy);
  mbedtls_ctr_drbg_init(&ctr_drbg);
  mbedtls_ssl_init(&ssl);
  mbedtls_ssl_config_init(&config);

  bool success = false;
  const char personalization[] = "n3w-r6-bootstrap";
  VerifyContext verify;
  verify.expected = expected_pin;
  SocketBio bio{fd, monotonic_ms() + kTlsHandshakeTimeoutMs};

  int result = mbedtls_ctr_drbg_seed(
      &ctr_drbg,
      mbedtls_entropy_func,
      &entropy,
      reinterpret_cast<const unsigned char *>(personalization),
      sizeof(personalization) - 1U);
  if (result == 0) {
    result = mbedtls_ssl_config_defaults(
        &config,
        MBEDTLS_SSL_IS_CLIENT,
        MBEDTLS_SSL_TRANSPORT_STREAM,
        MBEDTLS_SSL_PRESET_DEFAULT);
  }
  if (result == 0) {
    mbedtls_ssl_conf_rng(
        &config, mbedtls_ctr_drbg_random, &ctr_drbg);
    mbedtls_ssl_conf_authmode(&config, MBEDTLS_SSL_VERIFY_REQUIRED);
    mbedtls_ssl_conf_verify(&config, verify_pinned_leaf, &verify);
    result = mbedtls_ssl_setup(&ssl, &config);
  }
  if (result == 0) {
    mbedtls_ssl_set_bio(&ssl, &bio, tls_send, tls_recv, nullptr);
    do {
      result = mbedtls_ssl_handshake(&ssl);
    } while ((result == MBEDTLS_ERR_SSL_WANT_READ ||
              result == MBEDTLS_ERR_SSL_WANT_WRITE) &&
             !deadline_expired(bio.deadline_ms));
  }

  if (result != 0 || !verify.leaf_seen || !verify.leaf_matched) {
    *error = verify.pin_mismatch
                 ? RegistrationBootstrapTransportError::PIN_MISMATCH
                 : RegistrationBootstrapTransportError::TLS_FAILED;
  } else {
    // Security invariant: the HTTP request (and therefore every Setup Secret
    // byte in its JSON body) is constructed only after exact leaf pin success.
    std::string request =
        "POST " + path + " HTTP/1.1\r\n" +
        "Host: " + host + ":" + std::to_string(port) + "\r\n" +
        "Content-Type: application/json\r\n" +
        "Accept: application/json\r\n" +
        "Cache-Control: no-store\r\n" +
        "Connection: close\r\n" +
        "Content-Length: " + std::to_string(request_json.size()) + "\r\n\r\n" +
        request_json;

    if (!tls_write_all(&ssl, &bio, request)) {
      *error = RegistrationBootstrapTransportError::IO_FAILED;
    } else {
      std::string raw_response;
      bool overflow = false;
      if (!tls_read_bounded(
              &ssl, &bio, &raw_response, &overflow)) {
        *error = overflow
                     ? RegistrationBootstrapTransportError::RESPONSE_TOO_LARGE
                     : RegistrationBootstrapTransportError::IO_FAILED;
      } else if (!parse_http_response(raw_response, response)) {
        *error = RegistrationBootstrapTransportError::PROTOCOL_FAILED;
      } else {
        *error = RegistrationBootstrapTransportError::NONE;
        success = true;
      }
      secure_clear(&raw_response);
    }
    secure_clear(&request);
  }

  (void) mbedtls_ssl_close_notify(&ssl);
  mbedtls_ssl_free(&ssl);
  mbedtls_ssl_config_free(&config);
  mbedtls_ctr_drbg_free(&ctr_drbg);
  mbedtls_entropy_free(&entropy);
  ::close(fd);
  verify.expected.fill(0);
  expected_pin.fill(0);
  return success;
}

}  // namespace esphome::greenhouse_n3w_core
