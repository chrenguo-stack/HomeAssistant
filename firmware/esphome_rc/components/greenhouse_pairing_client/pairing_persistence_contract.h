#pragma once

#include <cstdint>
#include <string>

namespace esphome::greenhouse_pairing_client {

enum class CredentialSlot : uint8_t { NONE = 0, A = 1, B = 2 };
enum class CredentialRecordState : uint8_t {
  EMPTY = 0,
  PREPARED = 1,
  COMMITTED = 2,
  INVALID = 3,
};

struct CredentialSlotRecord {
  uint16_t schema_version{1};
  CredentialSlot slot{CredentialSlot::NONE};
  CredentialRecordState state{CredentialRecordState::EMPTY};
  uint32_t generation{0};
  std::string payload_digest;
};

struct CredentialJournalSnapshot {
  CredentialSlot active_slot{CredentialSlot::NONE};
  CredentialSlot candidate_slot{CredentialSlot::NONE};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool prepared{false};
  bool profile_verified{false};
  bool committed{false};
};

class CredentialPersistenceContract {
 public:
  bool configure(CredentialSlot active_slot, uint32_t active_generation);
  bool prepare(uint32_t candidate_generation, const std::string &payload_digest);
  bool mark_profile_verified();
  bool commit();
  void rollback();

  const CredentialJournalSnapshot &snapshot() const { return this->snapshot_; }
  const CredentialSlotRecord &candidate_record() const { return this->candidate_record_; }

  static bool valid_digest(const std::string &value);
  static bool valid_record(const CredentialSlotRecord &record);
  static bool recover(const CredentialSlotRecord &slot_a,
                      const CredentialSlotRecord &slot_b,
                      CredentialSlot marker_slot, uint32_t marker_generation,
                      CredentialJournalSnapshot *output);

 protected:
  static CredentialSlot opposite_(CredentialSlot slot);

  CredentialJournalSnapshot snapshot_{};
  CredentialSlotRecord candidate_record_{};
};

}  // namespace esphome::greenhouse_pairing_client
