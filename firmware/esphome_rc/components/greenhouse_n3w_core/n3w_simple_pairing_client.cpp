#include "n3w_simple_pairing_client.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <utility>
#include <vector>

#include "esphome/components/json/json_util.h"
#include "mbedtls/base64.h"
#include "mbedtls/md.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr char kSimplePairingProtocol[] = "gh-n3w-simple-pairing/1";
constexpr char kPairingIdDomainV1[] = "gh.pair.simple-id/1";
constexpr char kPairingIdDomainV2[] = "gh.pair.simple-id/2";

std::string base64url_encode(const uint8_t *data, std::size_t size) {
  if (data == nullptr || size == 0) return {};
  std::vector<uint8_t> encoded(((size + 2U) / 3U) * 4U + 1U, 0);
  std::size_t written = 0;
  if (mbedtls_base64_encode(
          encoded.data(), encoded.size(), &written, data, size) != 0) {
    return {};
  }
  std::string output(reinterpret_cast<const char *>(encoded.data()), written);
  for (char &ch : output) {
    if (ch == '+') ch = '-';
    if (ch == '/') ch = '_';
  }
  while (!output.empty() && output.back() == '=') output.pop_back();
  return output;
}

template<std::size_t N>
std::string base64url_encode(const std::array<uint8_t, N> &data) {
  return base64url_encode(data.data(), data.size());
}

bool base64url_decode(
    const std::string &value,
    uint8_t *output,
    std::size_t output_size) {
  if (value.empty() || output == nullptr || output_size == 0) return false;
  std::string padded = value;
  for (char &ch : padded) {
    if (ch == '-') ch = '+';
    if (ch == '_') ch = '/';
  }
  while ((padded.size() % 4U) != 0U) padded.push_back('=');
  std::size_t written = 0;
  if (mbedtls_base64_decode(
          output,
          output_size,
          &written,
          reinterpret_cast<const uint8_t *>(padded.data()),
          padded.size()) != 0) {
    return false;
  }
  return written == output_size;
}

bool constant_time_equal(const uint8_t *left, const uint8_t *right, std::size_t size) {
  if (left == nullptr || right == nullptr) return false;
  uint8_t diff = 0;
  for (std::size_t index = 0; index < size; ++index) diff |= left[index] ^ right[index];
  return diff == 0;
}

bool valid_unicast_mac(const MacAddress &mac) {
  const bool all_zero = std::all_of(
      mac.begin(), mac.end(), [](uint8_t value) { return value == 0; });
  const bool all_ff = std::all_of(
      mac.begin(), mac.end(), [](uint8_t value) { return value == 0xff; });
  return !all_zero && !all_ff && (mac[0] & 0x01U) == 0;
}

std::string hardware_id_from_mac(const MacAddress &mac) {
  char buffer[32]{};
  std::snprintf(
      buffer,
      sizeof(buffer),
      "ghw-c6-%02x%02x%02x%02x%02x%02x",
      mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  return buffer;
}

std::string pairing_id_from_secret(
    const SetupSecret &secret,
    const MacAddress &mac,
    uint32_t pairing_epoch) {
  if (pairing_epoch == 0) return {};

  std::vector<uint8_t> input;
  if (pairing_epoch == 1) {
    input.insert(
        input.end(),
        std::begin(kPairingIdDomainV1),
        std::end(kPairingIdDomainV1) - 1);
  } else {
    input.insert(
        input.end(),
        std::begin(kPairingIdDomainV2),
        std::end(kPairingIdDomainV2) - 1);
  }
  input.insert(input.end(), secret.begin(), secret.end());
  input.insert(input.end(), mac.begin(), mac.end());
  if (pairing_epoch > 1) {
    for (int shift = 24; shift >= 0; shift -= 8) {
      input.push_back(static_cast<uint8_t>((pairing_epoch >> shift) & 0xffU));
    }
  }

  std::array<uint8_t, 32> digest{};
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr ||
      mbedtls_md(info, input.data(), input.size(), digest.data()) != 0) {
    return {};
  }
  digest[6] = static_cast<uint8_t>((digest[6] & 0x0fU) | 0x40U);
  digest[8] = static_cast<uint8_t>((digest[8] & 0x3fU) | 0x80U);
  char output[37]{};
  std::snprintf(
      output,
      sizeof(output),
      "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      digest[0], digest[1], digest[2], digest[3],
      digest[4], digest[5], digest[6], digest[7],
      digest[8], digest[9], digest[10], digest[11], digest[12], digest[13], digest[14], digest[15]);
  return output;
}

std::string uuid_from_random(const std::array<uint8_t, 16> &random) {
  std::array<uint8_t, 16> value = random;
  value[6] = static_cast<uint8_t>((value[6] & 0x0fU) | 0x40U);
  value[8] = static_cast<uint8_t>((value[8] & 0x3fU) | 0x80U);
  char output[37]{};
  std::snprintf(
      output,
      sizeof(output),
      "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      value[0], value[1], value[2], value[3],
      value[4], value[5], value[6], value[7],
      value[8], value[9], value[10], value[11], value[12], value[13], value[14], value[15]);
  return output;
}

bool read_string(JsonObjectConst object, const char *key, std::string *value) {
  if (value == nullptr || !object[key].is<const char *>()) return false;
  const char *raw = object[key].as<const char *>();
  if (raw == nullptr || raw[0] == '\0') return false;
  *value = raw;
  return true;
}

bool parse_candidate(
    const std::string &response,
    const std::string &request_id,
    const std::string &nonce,
    SimpleManagerCandidateV2 *candidate) {
  if (candidate == nullptr) return false;
  JsonDocument document = json::parse_json(response);
  JsonObjectConst root = document.as<JsonObjectConst>();
  if (root.isNull() || std::string(root["schema"] | "") != "gh.discovery.response/1" ||
      std::string(root["request_id"] | "") != request_id ||
      std::string(root["nonce"] | "") != nonce || !root["candidate"].is<JsonObjectConst>()) {
    return false;
  }
  JsonObjectConst value = root["candidate"].as<JsonObjectConst>();
  std::string schema;
  std::string protocol;
  std::string scheme;
  if (!read_string(value, "schema", &schema) || schema != "gh.manager.candidate/1" ||
      !read_string(value, "protocol", &protocol) || protocol != kSimplePairingProtocol ||
      !read_string(value, "scheme", &scheme) || scheme != "http" ||
      !read_string(value, "manager_id", &candidate->manager_id) ||
      !read_string(value, "system_id", &candidate->system_id) ||
      !read_string(value, "host", &candidate->host) ||
      !read_string(value, "pairing_path", &candidate->pairing_path) ||
      !value["port"].is<uint16_t>()) {
    return false;
  }
  candidate->port = value["port"].as<uint16_t>();
  return candidate->valid();
}

bool parse_offer(
    const std::string &response,
    const SimpleManagerCandidateV2 &candidate,
    const std::string &hardware_id,
    const std::string &pairing_id,
    std::string *session_id,
    HandshakeNonce *manager_nonce,
    PeerProof *manager_proof) {
  if (session_id == nullptr || manager_nonce == nullptr || manager_proof == nullptr) return false;
  JsonDocument document = json::parse_json(response);
  JsonObjectConst root = document.as<JsonObjectConst>();
  std::string schema;
  std::string response_hardware;
  std::string response_pairing;
  std::string manager_id;
  std::string manager_nonce_text;
  std::string manager_proof_text;
  if (root.isNull() || !read_string(root, "schema", &schema) ||
      schema != "gh.pair.simple-offer/1" || !read_string(root, "session_id", session_id) ||
      !read_string(root, "hardware_id", &response_hardware) || response_hardware != hardware_id ||
      !read_string(root, "pairing_id", &response_pairing) || response_pairing != pairing_id ||
      !read_string(root, "manager_id", &manager_id) || manager_id != candidate.manager_id ||
      !read_string(root, "manager_nonce", &manager_nonce_text) ||
      !read_string(root, "manager_proof", &manager_proof_text)) {
    return false;
  }
  return base64url_decode(manager_nonce_text, manager_nonce->data(), manager_nonce->size()) &&
         base64url_decode(manager_proof_text, manager_proof->data(), manager_proof->size());
}

bool parse_encrypted_credentials(
    const std::string &response,
    const std::string &session_id,
    std::string *node_id,
    SimpleAeadNonce *nonce,
    std::vector<uint8_t> *ciphertext,
    std::array<uint8_t, 32> *delivery_digest) {
  if (node_id == nullptr || nonce == nullptr || ciphertext == nullptr || delivery_digest == nullptr) {
    return false;
  }
  JsonDocument document = json::parse_json(response);
  JsonObjectConst root = document.as<JsonObjectConst>();
  std::string schema;
  std::string response_session;
  std::string nonce_text;
  std::string ciphertext_text;
  std::string digest_text;
  if (root.isNull() || !read_string(root, "schema", &schema) ||
      schema != "gh.pair.simple-credentials/1" ||
      !read_string(root, "session_id", &response_session) || response_session != session_id ||
      !read_string(root, "node_id", node_id) || !read_string(root, "nonce", &nonce_text) ||
      !read_string(root, "ciphertext", &ciphertext_text) ||
      !read_string(root, "delivery_digest", &digest_text) ||
      !base64url_decode(nonce_text, nonce->data(), nonce->size()) ||
      !base64url_decode(digest_text, delivery_digest->data(), delivery_digest->size())) {
    return false;
  }
  std::string padded = ciphertext_text;
  for (char &ch : padded) {
    if (ch == '-') ch = '+';
    if (ch == '_') ch = '/';
  }
  while ((padded.size() % 4U) != 0U) padded.push_back('=');
  ciphertext->assign((padded.size() / 4U) * 3U + 1U, 0);
  std::size_t written = 0;
  if (mbedtls_base64_decode(
          ciphertext->data(),
          ciphertext->size(),
          &written,
          reinterpret_cast<const uint8_t *>(padded.data()),
          padded.size()) != 0 || written < 16U) {
    ciphertext->clear();
    return false;
  }
  ciphertext->resize(written);
  return true;
}

bool parse_bundle(
    const std::vector<uint8_t> &plaintext,
    const SimpleManagerCandidateV2 &candidate,
    const std::string &expected_node_id,
    ProvisionedPeerStateV2 *peer,
    ProvisionedBrokerStateV2 *broker) {
  if (plaintext.empty() || peer == nullptr || broker == nullptr) return false;
  JsonDocument document = json::parse_json(plaintext.data(), plaintext.size());
  JsonObjectConst root = document.as<JsonObjectConst>();
  std::string schema;
  std::string application_key;
  std::string system_peer_key;
  if (root.isNull() || !read_string(root, "schema", &schema) ||
      schema != "gh.pair.credentials/2" || !read_string(root, "system_id", &peer->system_id) ||
      peer->system_id != candidate.system_id || !read_string(root, "node_id", &peer->node_id) ||
      peer->node_id != expected_node_id || !root["peer_trust_generation"].is<uint32_t>() ||
      !root["n3w_key_epoch"].is<uint32_t>() ||
      !read_string(root, "n3w_application_key", &application_key) ||
      !read_string(root, "system_peer_key", &system_peer_key)) {
    return false;
  }
  peer->peer_trust_generation = root["peer_trust_generation"].as<uint32_t>();
  peer->n3w_key_epoch = root["n3w_key_epoch"].as<uint32_t>();
  if (!base64url_decode(
          application_key,
          peer->n3w_application_key.data(),
          peer->n3w_application_key.size()) ||
      !base64url_decode(
          system_peer_key,
          peer->system_peer_key.data(),
          peer->system_peer_key.size())) {
    peer->clear();
    return false;
  }

  broker->system_id = peer->system_id;
  broker->node_id = peer->node_id;
  if (!read_string(root, "broker_host", &broker->broker_host) ||
      !root["broker_port"].is<uint16_t>() ||
      !read_string(root, "broker_tls_server_name", &broker->broker_tls_server_name) ||
      !read_string(root, "ca_pem", &broker->ca_pem) ||
      !read_string(root, "mqtt_username", &broker->mqtt_username) ||
      !read_string(root, "mqtt_password", &broker->mqtt_password) ||
      !read_string(root, "mqtt_client_id", &broker->mqtt_client_id) ||
      !root["credential_generation"].is<uint32_t>()) {
    peer->clear();
    broker->clear();
    return false;
  }
  broker->broker_port = root["broker_port"].as<uint16_t>();
  broker->credential_generation = root["credential_generation"].as<uint32_t>();
  return peer->valid() && broker->valid();
}

}  // namespace

bool SimpleManagerCandidateV2::valid() const {
  return valid_simple_identity_v2(manager_id) && valid_simple_identity_v2(system_id) &&
         !host.empty() && host.size() <= 253 && port > 0 && !pairing_path.empty() &&
         pairing_path.size() <= 255 && pairing_path.front() == '/';
}

SimplePairingClient::SimplePairingClient(
    SimplePairingClientNetwork *network,
    SimplePairingClientRandom *random,
    NvsSetupSecretStore *setup_secret_store,
    NvsProvisionedPeerStoreV2 *peer_store,
    NvsProvisionedBrokerStoreV2 *broker_store,
    NvsPendingPairingAckStoreV2 *ack_store)
    : network_(network),
      random_(random),
      setup_secret_store_(setup_secret_store),
      peer_store_(peer_store),
      broker_store_(broker_store),
      ack_store_(ack_store) {}

SimplePairingClientError SimplePairingClient::initialize(const MacAddress &local_mac) {
  if (initialized_ || network_ == nullptr || random_ == nullptr || setup_secret_store_ == nullptr ||
      peer_store_ == nullptr || broker_store_ == nullptr || ack_store_ == nullptr ||
      !valid_unicast_mac(local_mac)) {
    return SimplePairingClientError::NOT_READY;
  }
  local_mac_ = local_mac;
  hardware_id_ = hardware_id_from_mac(local_mac_);
  initialized_ = true;
  const SimplePairingClientError existing = load_existing_();
  if (existing == SimplePairingClientError::ALREADY_PROVISIONED ||
      existing == SimplePairingClientError::ACK_PENDING) {
    return existing;
  }
  if (existing != SimplePairingClientError::NONE) return existing;
  return prepare_bootstrap_();
}

SimplePairingClientError SimplePairingClient::load_existing_() {
  uint32_t stored_pairing_epoch = 0;
  const SimpleNvsStatus epoch_status =
      pairing_epoch_store_.load(&stored_pairing_epoch);
  if (epoch_status != SimpleNvsStatus::OK &&
      epoch_status != SimpleNvsStatus::MISSING) {
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }

  ProvisionedPeerStateV2 peer;
  ProvisionedBrokerStateV2 broker;
  const SimpleNvsStatus peer_status = peer_store_->load(&peer);
  const SimpleNvsStatus broker_status = broker_store_->load(&broker);
  PendingPairingAckV2 pending;
  const SimpleNvsStatus ack_status = ack_store_->load(&pending);

  const bool credentials_present = peer_status == SimpleNvsStatus::OK &&
                                   broker_status == SimpleNvsStatus::OK && peer.valid() &&
                                   broker.valid() && peer.system_id == broker.system_id &&
                                   peer.node_id == broker.node_id;
  if (credentials_present) {
    // A legacy provisioned identity with no durable pairing epoch must not keep
    // operating under its old key. Explicit repair recovery materializes a
    // higher pairing epoch and removes the old credential blobs first.
    if (epoch_status != SimpleNvsStatus::OK ||
        peer.n3w_key_epoch < stored_pairing_epoch ||
        broker.credential_generation != stored_pairing_epoch) {
      return SimplePairingClientError::PERSISTENCE_FAILED;
    }
    pairing_epoch_ = stored_pairing_epoch;
    if (ack_status == SimpleNvsStatus::OK && pending.valid()) {
      return SimplePairingClientError::ACK_PENDING;
    }
    if (ack_status == SimpleNvsStatus::MISSING) {
      provisioned_ = true;
      return SimplePairingClientError::ALREADY_PROVISIONED;
    }
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }

  if ((peer_status == SimpleNvsStatus::OK) != (broker_status == SimpleNvsStatus::OK) ||
      peer_status == SimpleNvsStatus::CORRUPT || broker_status == SimpleNvsStatus::CORRUPT ||
      ack_status != SimpleNvsStatus::MISSING) {
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }
  if (epoch_status == SimpleNvsStatus::OK) pairing_epoch_ = stored_pairing_epoch;
  return SimplePairingClientError::NONE;
}

SimplePairingClientError SimplePairingClient::prepare_bootstrap_() {
  if (pairing_epoch_ == 0) {
    uint32_t stored_pairing_epoch = 0;
    const SimpleNvsStatus epoch_status =
        pairing_epoch_store_.load(&stored_pairing_epoch);
    if (epoch_status == SimpleNvsStatus::MISSING) {
      if (pairing_epoch_store_.save(1) != SimpleNvsStatus::OK ||
          pairing_epoch_store_.load(&stored_pairing_epoch) != SimpleNvsStatus::OK ||
          stored_pairing_epoch != 1) {
        return SimplePairingClientError::PERSISTENCE_FAILED;
      }
    } else if (epoch_status != SimpleNvsStatus::OK) {
      return SimplePairingClientError::PERSISTENCE_FAILED;
    }
    pairing_epoch_ = stored_pairing_epoch;
  }

  const SimpleNvsStatus status = setup_secret_store_->load_or_create(&setup_secret_);
  if (status != SimpleNvsStatus::OK && status != SimpleNvsStatus::CREATED) {
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }
  setup_secret_ready_ = true;
  pairing_id_ = pairing_id_from_secret(setup_secret_, local_mac_, pairing_epoch_);
  return pairing_id_.empty() ? SimplePairingClientError::CRYPTO_FAILED
                             : SimplePairingClientError::NONE;
}

SimplePairingClientError SimplePairingClient::run_once(uint64_t now_ms) {
  if (!initialized_) return SimplePairingClientError::NOT_READY;
  if (provisioned_) return SimplePairingClientError::ALREADY_PROVISIONED;
  PendingPairingAckV2 pending;
  const SimpleNvsStatus pending_status = ack_store_->load(&pending);
  if (pending_status == SimpleNvsStatus::OK) return resume_pending_ack();
  if (pending_status != SimpleNvsStatus::MISSING) {
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }
  if (!setup_secret_ready_) {
    const SimplePairingClientError prepared = prepare_bootstrap_();
    if (prepared != SimplePairingClientError::NONE) return prepared;
  }
  (void) now_ms;
  SimpleManagerCandidateV2 candidate;
  SimplePairingClientError result = discover_(&candidate);
  if (result != SimplePairingClientError::NONE) return result;
  result = send_hello_(candidate);
  if (result != SimplePairingClientError::NONE) return result;
  return pair_with_(candidate);
}

SimplePairingClientError SimplePairingClient::resume_pending_ack() {
  if (!initialized_) return SimplePairingClientError::NOT_READY;
  PendingPairingAckV2 pending;
  const SimpleNvsStatus status = ack_store_->load(&pending);
  if (status == SimpleNvsStatus::MISSING) return SimplePairingClientError::NONE;
  if (status != SimpleNvsStatus::OK || !pending.valid()) {
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }
  return acknowledge_(pending);
}

SimplePairingClientError SimplePairingClient::discover_(SimpleManagerCandidateV2 *candidate) {
  std::array<uint8_t, 16> request_random{};
  std::array<uint8_t, 32> nonce{};
  if (!fill_(request_random.data(), request_random.size()) ||
      !fill_(nonce.data(), nonce.size())) {
    return SimplePairingClientError::IO_FAILED;
  }
  const std::string request_id = uuid_from_random(request_random);
  const std::string nonce_text = base64url_encode(nonce);
  const std::string request = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.discovery.query/1";
    root["request_id"] = request_id;
    root["nonce"] = nonce_text;
    root["hardware_id"] = hardware_id_;
    JsonArray protocols = root["protocols"].to<JsonArray>();
    protocols.add(kSimplePairingProtocol);
  });
  std::string response;
  if (!network_->discover_manager(request, &response) ||
      !parse_candidate(response, request_id, nonce_text, candidate)) {
    return SimplePairingClientError::DISCOVERY_FAILED;
  }
  return SimplePairingClientError::NONE;
}

SimplePairingClientError SimplePairingClient::send_hello_(
    const SimpleManagerCandidateV2 &candidate) {
  if (pairing_epoch_ == 0) return SimplePairingClientError::PERSISTENCE_FAILED;
  std::array<uint8_t, 32> hello_nonce{};
  if (!fill_(hello_nonce.data(), hello_nonce.size())) return SimplePairingClientError::IO_FAILED;
  const std::string request = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.pair.hello/1";
    root["pairing_id"] = pairing_id_;
    root["pairing_epoch"] = pairing_epoch_;
    root["hardware_id"] = hardware_id_;
    root["model"] = "greenhouse-wifi-c6";
    root["fw_version"] = "phase4-simple";
    root["node_nonce"] = base64url_encode(hello_nonce);
    JsonArray capabilities = root["capabilities"].to<JsonArray>();
    capabilities.add("simple-setup-secret");
    capabilities.add("long-lived-peer-trust");
    root["sent_at_ms"] = 0;
  });
  int status = 0;
  std::string response;
  const std::string path = candidate.pairing_path + "/hello";
  if (!network_->post_json(candidate, path, request, &status, &response) || status != 200) {
    return SimplePairingClientError::HTTP_FAILED;
  }
  return SimplePairingClientError::NONE;
}

SimplePairingClientError SimplePairingClient::pair_with_(
    const SimpleManagerCandidateV2 &candidate) {
  HandshakeNonce node_nonce{};
  if (!fill_(node_nonce.data(), node_nonce.size())) return SimplePairingClientError::IO_FAILED;
  const std::string begin_request = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.pair.simple-begin/1";
    root["hardware_id"] = hardware_id_;
    root["pairing_id"] = pairing_id_;
    root["node_nonce"] = base64url_encode(node_nonce);
  });
  int status = 0;
  std::string response;
  if (!network_->post_json(
          candidate,
          candidate.pairing_path + "/begin",
          begin_request,
          &status,
          &response)) {
    return SimplePairingClientError::HTTP_FAILED;
  }
  if (status != 200) return SimplePairingClientError::NOT_READY;

  std::string session_id;
  HandshakeNonce manager_nonce{};
  PeerProof supplied_manager_proof{};
  if (!parse_offer(
          response,
          candidate,
          hardware_id_,
          pairing_id_,
          &session_id,
          &manager_nonce,
          &supplied_manager_proof)) {
    return SimplePairingClientError::RESPONSE_REJECTED;
  }
  SimplePairingTranscript transcript{
      .pairing_id = pairing_id_,
      .hardware_id = hardware_id_,
      .manager_id = candidate.manager_id,
      .node_nonce = node_nonce,
      .manager_nonce = manager_nonce,
  };
  PeerProof expected_manager_proof{};
  if (build_setup_proof(
          setup_secret_, transcript, PairingRole::MANAGER,
          &expected_manager_proof) != SimpleCryptoError::NONE ||
      !constant_time_equal(
          expected_manager_proof.data(),
          supplied_manager_proof.data(),
          supplied_manager_proof.size())) {
    return SimplePairingClientError::CRYPTO_FAILED;
  }
  PeerProof node_proof{};
  if (build_setup_proof(
          setup_secret_, transcript, PairingRole::NODE,
          &node_proof) != SimpleCryptoError::NONE) {
    return SimplePairingClientError::CRYPTO_FAILED;
  }
  const std::string establish_request = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.pair.simple-establish/1";
    root["node_proof"] = base64url_encode(node_proof);
  });
  response.clear();
  if (!network_->post_json(
          candidate,
          candidate.pairing_path + "/sessions/" + session_id + "/establish",
          establish_request,
          &status,
          &response) || status != 200) {
    return SimplePairingClientError::HTTP_FAILED;
  }

  std::string node_id;
  SimpleAeadNonce aead_nonce{};
  std::vector<uint8_t> ciphertext;
  std::array<uint8_t, 32> delivery_digest{};
  if (!parse_encrypted_credentials(
          response,
          session_id,
          &node_id,
          &aead_nonce,
          &ciphertext,
          &delivery_digest)) {
    return SimplePairingClientError::RESPONSE_REJECTED;
  }
  std::array<uint8_t, 32> bootstrap_key{};
  if (derive_bootstrap_key(setup_secret_, transcript, &bootstrap_key) != SimpleCryptoError::NONE) {
    return SimplePairingClientError::CRYPTO_FAILED;
  }
  std::vector<uint8_t> plaintext;
  const SimpleCryptoError decrypt_result = decrypt_simple_credential_bundle(
      bootstrap_key, transcript, aead_nonce, ciphertext, &plaintext);
  bootstrap_key.fill(0);
  if (decrypt_result != SimpleCryptoError::NONE) return SimplePairingClientError::CRYPTO_FAILED;

  ProvisionedPeerStateV2 peer;
  ProvisionedBrokerStateV2 broker;
  if (!parse_bundle(plaintext, candidate, node_id, &peer, &broker) ||
      pairing_epoch_ == 0 || broker.credential_generation != pairing_epoch_ ||
      peer.n3w_key_epoch < pairing_epoch_) {
    std::fill(plaintext.begin(), plaintext.end(), 0);
    peer.clear();
    broker.clear();
    return SimplePairingClientError::RESPONSE_REJECTED;
  }
  std::fill(plaintext.begin(), plaintext.end(), 0);
  const SimplePairingClientError persisted = persist_bundle_(
      candidate, session_id, delivery_digest, peer, broker);
  peer.clear();
  broker.clear();
  if (persisted != SimplePairingClientError::NONE) return persisted;
  return resume_pending_ack();
}

SimplePairingClientError SimplePairingClient::persist_bundle_(
    const SimpleManagerCandidateV2 &candidate,
    const std::string &session_id,
    const std::array<uint8_t, 32> &delivery_digest,
    const ProvisionedPeerStateV2 &peer,
    const ProvisionedBrokerStateV2 &broker) {
  if (peer_store_->save(peer) != SimpleNvsStatus::OK) {
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }
  if (broker_store_->save(broker) != SimpleNvsStatus::OK) {
    (void) peer_store_->erase();
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }
  PendingPairingAckV2 pending;
  pending.manager_host = candidate.host;
  pending.manager_port = candidate.port;
  pending.pairing_path = candidate.pairing_path;
  pending.session_id = session_id;
  pending.delivery_digest = delivery_digest;
  if (ack_store_->save(pending) != SimpleNvsStatus::OK) {
    (void) broker_store_->erase();
    (void) peer_store_->erase();
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }
  return SimplePairingClientError::NONE;
}

SimplePairingClientError SimplePairingClient::acknowledge_(const PendingPairingAckV2 &pending) {
  const std::string request = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.pair.simple-ack/1";
    root["delivery_digest"] = base64url_encode(pending.delivery_digest);
  });
  int status = 0;
  std::string response;
  const std::string path = pending.pairing_path + "/sessions/" + pending.session_id + "/ack";
  if (!network_->post_json(pending, path, request, &status, &response) || status != 200) {
    return SimplePairingClientError::ACK_PENDING;
  }
  if (setup_secret_store_->erase() != SimpleNvsStatus::OK ||
      ack_store_->erase() != SimpleNvsStatus::OK) {
    return SimplePairingClientError::PERSISTENCE_FAILED;
  }
  setup_secret_.fill(0);
  setup_secret_ready_ = false;
  provisioned_ = true;
  return SimplePairingClientError::NONE;
}

bool SimplePairingClient::fill_(uint8_t *data, std::size_t size) {
  if (data == nullptr || size == 0 || !random_->fill_pairing_random(data, size)) return false;
  return std::any_of(data, data + size, [](uint8_t value) { return value != 0; });
}

std::string SimplePairingClient::setup_secret_base64url() const {
  return setup_secret_ready_ ? base64url_encode(setup_secret_) : std::string{};
}

std::string SimplePairingClient::pairing_qr_payload() const {
  if (!setup_secret_ready_ || hardware_id_.empty() || pairing_id_.empty()) return {};
  return "GHN3W2:" + hardware_id_ + ":" + pairing_id_ + ":" + setup_secret_base64url();
}

}  // namespace esphome::greenhouse_n3w_core
