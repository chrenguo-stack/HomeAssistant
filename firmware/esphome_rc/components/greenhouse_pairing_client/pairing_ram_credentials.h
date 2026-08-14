#pragma once

#include <cstdint>
#include <string>

namespace esphome::greenhouse_pairing_client {

struct RamCredentialBundle {
  RamCredentialBundle() = default;
  ~RamCredentialBundle();

  RamCredentialBundle(const RamCredentialBundle &) = delete;
  RamCredentialBundle &operator=(const RamCredentialBundle &) = delete;
  RamCredentialBundle(RamCredentialBundle &&other);
  RamCredentialBundle &operator=(RamCredentialBundle &&other);

  std::string schema;
  std::string system_id;
  std::string node_id;
  std::string broker_host;
  uint16_t broker_port{0};
  std::string broker_tls_server_name;
  std::string ca_pem;
  std::string mqtt_username;
  std::string mqtt_client_id;
  uint32_t credential_generation{0};
  std::string mqtt_password;

  // Product N3-W credentials are optional so the legacy pairing profile
  // remains wire/persistence compatible. They are accepted only as an exact
  // pair: a non-zero epoch plus a 32-byte base64url application key.
  uint32_t n3w_key_epoch{0};
  std::string n3w_application_key;

  bool valid() const;
  bool present() const;
  bool has_n3w_credentials() const;
  std::string delivery_ack_json() const;
  void clear();

 protected:
  void move_from_(RamCredentialBundle *other);
};

}  // namespace esphome::greenhouse_pairing_client
