#include "pairing_ram_credentials.h"

#include <algorithm>

#include "pairing_client_core.h"
#include "secure_pairing_channel.h"

namespace esphome::greenhouse_pairing_client {

namespace {

void secure_clear(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

}  // namespace

RamCredentialBundle::~RamCredentialBundle() { this->clear(); }

RamCredentialBundle::RamCredentialBundle(RamCredentialBundle &&other) {
  this->move_from_(&other);
}

RamCredentialBundle &RamCredentialBundle::operator=(RamCredentialBundle &&other) {
  if (this == &other)
    return *this;
  this->clear();
  this->move_from_(&other);
  return *this;
}

void RamCredentialBundle::move_from_(RamCredentialBundle *other) {
  if (other == nullptr || other == this)
    return;

  // Copy each live value, then actively wipe the source. Using the default
  // std::string move can leave short-string bytes behind in the moved-from
  // object's inline storage, which is not acceptable for RAM-only credentials.
  this->schema = other->schema;
  this->system_id = other->system_id;
  this->node_id = other->node_id;
  this->broker_host = other->broker_host;
  this->broker_port = other->broker_port;
  this->broker_tls_server_name = other->broker_tls_server_name;
  this->ca_pem = other->ca_pem;
  this->mqtt_username = other->mqtt_username;
  this->mqtt_client_id = other->mqtt_client_id;
  this->credential_generation = other->credential_generation;
  this->mqtt_password = other->mqtt_password;
  other->clear();
}

bool RamCredentialBundle::valid() const {
  return this->schema == CREDENTIALS_CONTENT_TYPE &&
         PairingClientCore::valid_identifier(this->system_id) &&
         PairingClientCore::valid_identifier(this->node_id) &&
         PairingClientCore::valid_local_host(this->broker_host) && this->broker_port != 0 &&
         PairingClientCore::valid_local_host(this->broker_tls_server_name) && !this->ca_pem.empty() &&
         this->ca_pem.size() <= 8192 && PairingClientCore::valid_identifier(this->mqtt_username) &&
         PairingClientCore::valid_identifier(this->mqtt_client_id) &&
         this->credential_generation != 0 && !this->mqtt_password.empty() &&
         this->mqtt_password.size() <= 512;
}

bool RamCredentialBundle::present() const {
  return !this->node_id.empty() || !this->mqtt_password.empty() || this->credential_generation != 0;
}

std::string RamCredentialBundle::delivery_ack_json() const {
  if (!this->valid())
    return {};
  return std::string("{\"credential_generation\":") +
         std::to_string(this->credential_generation) + ",\"node_id\":\"" +
         SecurePairingChannel::json_escape(this->node_id) +
         "\",\"schema\":\"gh.pair.delivery-ack/1\",\"stored\":true}";
}

void RamCredentialBundle::clear() {
  secure_clear(&this->schema);
  secure_clear(&this->system_id);
  secure_clear(&this->node_id);
  secure_clear(&this->broker_host);
  secure_clear(&this->broker_tls_server_name);
  secure_clear(&this->ca_pem);
  secure_clear(&this->mqtt_username);
  secure_clear(&this->mqtt_client_id);
  secure_clear(&this->mqtt_password);
  this->broker_port = 0;
  this->credential_generation = 0;
}

}  // namespace esphome::greenhouse_pairing_client
