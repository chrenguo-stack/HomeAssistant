#pragma once

#include <cstdint>
#include <vector>

#include "pairing_credential_codec.h"
#include "pairing_persistence_backend.h"
#include "pairing_persistence_crypto.h"

namespace esphome::greenhouse_pairing_client {

enum class PersistentRecoveryStatus : uint8_t {
  EMPTY = 0,
  ACTIVE = 1,
  ACTIVE_WITH_PREPARED = 2,
  ACTIVE_WITH_COMMITTED_ORPHAN = 3,
  ACTIVE_WITH_INVALID_INACTIVE = 4,
  NO_ACTIVE_PREPARED = 5,
  NO_ACTIVE_COMMITTED_ORPHAN = 6,
  INVALID_RECORD = 7,
  CONFLICT = 8,
  STORAGE_ERROR = 9,
};

struct PersistentRecoverySnapshot {
  PersistentRecoveryStatus status{PersistentRecoveryStatus::EMPTY};
  CredentialSlot active_slot{CredentialSlot::NONE};
  CredentialSlot candidate_slot{CredentialSlot::NONE};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool stale_committed_slot_present{false};
  bool active_credentials_available{false};
  bool candidate_credentials_available{false};
};

class PairingPersistentStore {
 public:
  PairingPersistentStore(PairingPersistenceBackend *backend,
                         PairingPersistenceCrypto *crypto)
      : backend_(backend), crypto_(crypto) {}

  bool recover(PersistentRecoverySnapshot *snapshot,
               RamCredentialBundle *active_credentials = nullptr,
               RamCredentialBundle *candidate_credentials = nullptr);
  bool prepare(const RamCredentialBundle &credentials);
  bool commit_prepared();
  bool rollback_prepared();
  bool discard_committed_orphan();

  static const char *status_name(PersistentRecoveryStatus status);

 private:
  enum class RecordLoadResult : uint8_t {
    ABSENT = 0,
    VALID = 1,
    INVALID = 2,
    STORAGE_ERROR = 3,
  };

  struct LoadedRecord {
    bool present{false};
    PersistenceEnvelopeMetadata metadata{};
    RamCredentialBundle credentials{};
  };

  struct ActiveMarker {
    CredentialSlot slot{CredentialSlot::NONE};
    uint32_t generation{0};
  };

  static const char *slot_key_(CredentialSlot slot);
  RecordLoadResult load_record_(CredentialSlot physical_slot,
                                LoadedRecord *record);
  bool write_record_(CredentialSlot slot, CredentialRecordState state,
                     const RamCredentialBundle &credentials);
  bool verify_record_(CredentialSlot slot, CredentialRecordState state,
                      uint32_t generation);
  bool read_marker_(bool *present, ActiveMarker *marker);
  bool write_marker_(CredentialSlot slot, uint32_t generation);
  bool verify_marker_(CredentialSlot slot, uint32_t generation);
  bool erase_slot_(CredentialSlot slot);
  static std::vector<uint8_t> encode_marker_(CredentialSlot slot,
                                              uint32_t generation);
  static bool decode_marker_(const std::vector<uint8_t> &blob,
                             ActiveMarker *marker);
  static uint32_t crc32_(const uint8_t *data, size_t length);
  static void wipe_vector_(std::vector<uint8_t> *value);

  PairingPersistenceBackend *backend_{nullptr};
  PairingPersistenceCrypto *crypto_{nullptr};
};

}  // namespace esphome::greenhouse_pairing_client
