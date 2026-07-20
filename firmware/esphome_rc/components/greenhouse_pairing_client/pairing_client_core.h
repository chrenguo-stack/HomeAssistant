#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace esphome::greenhouse_pairing_client {

static constexpr const char *SECURE_PAIRING_PROTOCOL = "gh-h3-secure-pairing/1";
static constexpr const char *DISCOVERY_QUERY_SCHEMA = "gh.discovery.query/1";
static constexpr const char *DISCOVERY_RESPONSE_SCHEMA = "gh.discovery.response/1";
static constexpr const char *MANAGER_CANDIDATE_SCHEMA = "gh.manager.candidate/1";
static constexpr const char *CLAIM_SCHEMA = "gh.pair.claim/1";


enum class PairingClientState : uint8_t {
  UNBOUND = 0,
  DISCOVERING = 1,
  CANDIDATE_READY = 2,
  SELECTION_REQUIRED = 3,
  CLAIM_READY = 4,
  CLAIM_SENT = 5,
  SECURE_OFFER_RECEIVED = 6,
  CHANNEL_ESTABLISHED = 7,
  CREDENTIALS_STAGED = 8,
  COMMITTED = 9,
  RECOVERABLE_FAILURE = 10,
  TERMINAL_FAILURE = 11,
};


enum class PairingClientError : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  INVALID_DISCOVERY_CONTEXT = 2,
  INVALID_CANDIDATE = 3,
  CANDIDATE_CAPACITY_REACHED = 4,
  CANDIDATE_SELECTION_REQUIRED = 5,
  CANDIDATE_NOT_AVAILABLE = 6,
  INVALID_STATE_TRANSITION = 7,
  SECURE_OFFER_REJECTED = 8,
  CREDENTIALS_REJECTED = 9,
  STORAGE_FAILED = 10,
  TRANSPORT_FAILED = 11,
};


struct ManagerCandidate {
  std::string schema;
  std::string manager_id;
  std::string system_id;
  std::string host;
  std::string scheme;
  uint16_t port{0};
  std::string pairing_path;
  std::string protocol;
  uint16_t priority{0};
  uint16_t ttl_s{0};
};


struct CandidateObservation {
  ManagerCandidate candidate;
  uint32_t observed_at_ms{0};
};


struct PairingClientSnapshot {
  PairingClientState state{PairingClientState::UNBOUND};
  PairingClientError error{PairingClientError::NONE};
  size_t candidate_count{0};
  bool selection_required{false};
  bool candidate_selected{false};
  bool secure_offer_present{false};
  bool credentials_staged{false};
  bool committed{false};
  uint32_t credential_generation{0};
};


class PairingClientCore {
 public:
  bool configure(const std::string &hardware_id, const std::string &pairing_id, size_t max_candidates,
                 uint16_t candidate_ttl_cap_s);

  bool start_discovery(const std::string &request_id, const std::string &nonce, uint32_t now_ms);
  bool observe_candidate(const std::string &request_id, const std::string &nonce,
                         const ManagerCandidate &candidate, uint32_t now_ms);
  void prune_candidates(uint32_t now_ms);

  bool select_candidate(size_t index);
  bool mark_claim_sent();
  bool accept_secure_offer(const std::string &session_id, const std::string &manager_nonce,
                           const std::string &manager_public_key, const std::string &cipher_suite);
  bool mark_channel_established();
  bool stage_credentials(const std::string &node_id, uint32_t credential_generation);
  bool commit_credentials();
  void fail(PairingClientError error, bool recoverable);
  void reset_unbound();

  PairingClientSnapshot snapshot() const;

  const std::string &hardware_id() const { return this->hardware_id_; }
  const std::string &pairing_id() const { return this->pairing_id_; }
  const std::string &request_id() const { return this->request_id_; }
  const std::string &nonce() const { return this->nonce_; }
  const std::string &session_id() const { return this->session_id_; }
  const std::string &manager_nonce() const { return this->manager_nonce_; }
  const std::string &manager_public_key() const { return this->manager_public_key_; }
  const std::string &node_id() const { return this->node_id_; }
  const std::vector<CandidateObservation> &candidates() const { return this->candidates_; }
  const ManagerCandidate *selected_candidate() const;

  const char *state_name() const;
  const char *error_name() const;

  static bool valid_candidate(const ManagerCandidate &candidate);
  static bool valid_identifier(const std::string &value);
  static bool valid_request_id(const std::string &value);
  static bool valid_base64url_32(const std::string &value);
  static bool valid_local_host(const std::string &value);
  static bool same_candidate(const ManagerCandidate &left, const ManagerCandidate &right);
  static std::string build_claim_transcript(const std::string &manager_id, const std::string &hardware_id,
                                            const std::string &pairing_id);

 protected:
  void set_state_(PairingClientState state);
  void set_error_(PairingClientError error);
  void resolve_selection_state_();
  bool selected_index_valid_() const;

  std::string hardware_id_;
  std::string pairing_id_;
  size_t max_candidates_{4};
  uint16_t candidate_ttl_cap_s_{120};

  PairingClientState state_{PairingClientState::UNBOUND};
  PairingClientError error_{PairingClientError::NONE};
  std::string request_id_;
  std::string nonce_;
  uint32_t discovery_started_at_ms_{0};
  std::vector<CandidateObservation> candidates_;
  size_t selected_index_{static_cast<size_t>(-1)};
  bool selection_explicit_{false};

  std::string session_id_;
  std::string manager_nonce_;
  std::string manager_public_key_;
  std::string node_id_;
  uint32_t credential_generation_{0};
};

}  // namespace esphome::greenhouse_pairing_client
