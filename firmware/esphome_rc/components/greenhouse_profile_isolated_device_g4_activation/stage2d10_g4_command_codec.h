#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

namespace esphome::greenhouse_pairing_client {

enum class Stage2D10G4CommandAction : uint8_t {
  NONE = 0,
  ACTIVATE_PROFILE = 1,
  VERIFY_ACTIVE_READ_ONLY = 2,
};

enum class Stage2D10G4CommandFailure : uint8_t {
  NONE = 0,
  EMPTY = 1,
  LENGTH = 2,
  WHITESPACE = 3,
  SCHEMA = 4,
  FIELD_COUNT = 5,
  RUN_SUFFIX = 6,
  HEX_SHAPE = 7,
  UNLOCK_DIGEST = 8,
  BASE64URL = 9,
  WIFI_LENGTH = 10,
  WIFI_DIGEST = 11,
  VERIFY_MODE = 12,
};

struct Stage2D10G4CommandEnvelope {
  Stage2D10G4CommandAction action{Stage2D10G4CommandAction::NONE};
  std::string run_suffix{};
  std::array<uint8_t, 32> unlock_token{};
  std::array<uint8_t, 32> persistence_key{};
  std::string authorization_digest{};
  std::string candidate_digest{};
  std::string active_digest{};
  std::string wifi_ssid{};
  std::string wifi_password{};
  std::string wifi_profile_digest{};
  std::string broker_configuration_digest{};
  std::string raw_command_sha256{};

  void clear();
};

class Stage2D10G4CommandCodec final {
 public:
  static constexpr const char *ACTIVATE_SCHEMA = "GH2D10_ACTIVATE_V1";
  static constexpr const char *VERIFY_SCHEMA =
      "GH2D10_VERIFY_ACTIVE_V1";
  static constexpr size_t MAX_COMMAND_LENGTH = 768;

  static bool parse(const std::string &line,
                    const std::string &expected_unlock_digest,
                    Stage2D10G4CommandEnvelope *envelope,
                    Stage2D10G4CommandFailure *failure);

  static bool wifi_profile_digest(const std::string &ssid,
                                  const std::string &password,
                                  std::string *digest);
  static bool command_sha256(const std::string &line, std::string *digest);

  static const char *action_name(Stage2D10G4CommandAction action);
  static const char *failure_name(Stage2D10G4CommandFailure failure);

 protected:
  static bool parse_activate_(const std::string &line,
                              const std::string *fields,
                              size_t field_count,
                              const std::string &expected_unlock_digest,
                              Stage2D10G4CommandEnvelope *envelope,
                              Stage2D10G4CommandFailure *failure);
  static bool parse_verify_(const std::string &line,
                            const std::string *fields,
                            size_t field_count,
                            const std::string &expected_unlock_digest,
                            Stage2D10G4CommandEnvelope *envelope,
                            Stage2D10G4CommandFailure *failure);
  static bool split_exact_(const std::string &line,
                           std::array<std::string, 10> *fields,
                           size_t *field_count);
  static bool valid_lower_hex_(const std::string &value, size_t length);
  static bool valid_run_suffix_(const std::string &value);
  static bool decode_hex_32_(const std::string &value,
                             std::array<uint8_t, 32> *output);
  static bool sha256_(const uint8_t *data, size_t length,
                      std::array<uint8_t, 32> *digest);
  static std::string hex_(const std::array<uint8_t, 32> &value);
  static bool constant_equal_(const std::string &left,
                              const std::string &right);
  static void fail_(Stage2D10G4CommandFailure value,
                    Stage2D10G4CommandFailure *failure);
};

}  // namespace esphome::greenhouse_pairing_client
