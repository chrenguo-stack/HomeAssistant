#include "pairing_persistent_store.h"

#include <algorithm>
#include <array>

namespace esphome::greenhouse_pairing_client {
namespace {

constexpr const char *SLOT_A_KEY = "slot_a";
constexpr const char *SLOT_B_KEY = "slot_b";
constexpr const char *ACTIVE_KEY = "active";
constexpr std::array<uint8_t, 4> MARKER_MAGIC = {'G', 'H', 'M', '1'};
constexpr uint16_t MARKER_VERSION = 1;
constexpr size_t MARKER_PLAINTEXT_BYTES = 12;

void put_u16(std::vector<uint8_t> *output, uint16_t value) {
  output->push_back(static_cast<uint8_t>((value >> 8) & 0xffU));
  output->push_back(static_cast<uint8_t>(value & 0xffU));
}

void put_u32(std::vector<uint8_t> *output, uint32_t value) {
  output->push_back(static_cast<uint8_t>((value >> 24) & 0xffU));
  output->push_back(static_cast<uint8_t>((value >> 16) & 0xffU));
  output->push_back(static_cast<uint8_t>((value >> 8) & 0xffU));
  output->push_back(static_cast<uint8_t>(value & 0xffU));
}

uint16_t read_u16(const uint8_t *data) {
  return static_cast<uint16_t>(
      (static_cast<uint16_t>(data[0]) << 8) |
      static_cast<uint16_t>(data[1]));
}

uint32_t read_u32(const uint8_t *data) {
  return (static_cast<uint32_t>(data[0]) << 24) |
         (static_cast<uint32_t>(data[1]) << 16) |
         (static_cast<uint32_t>(data[2]) << 8) |
         static_cast<uint32_t>(data[3]);
}

CredentialSlot opposite(CredentialSlot slot) {
  return slot == CredentialSlot::A ? CredentialSlot::B : CredentialSlot::A;
}

bool valid_slot(CredentialSlot slot) {
  return slot == CredentialSlot::A || slot == CredentialSlot::B;
}

void copy_bundle(const RamCredentialBundle &source,
                 RamCredentialBundle *destination) {
  if (destination == nullptr)
    return;
  destination->clear();
  destination->schema = source.schema;
  destination->system_id = source.system_id;
  destination->node_id = source.node_id;
  destination->broker_host = source.broker_host;
  destination->broker_port = source.broker_port;
  destination->broker_tls_server_name = source.broker_tls_server_name;
  destination->ca_pem = source.ca_pem;
  destination->mqtt_username = source.mqtt_username;
  destination->mqtt_client_id = source.mqtt_client_id;
  destination->credential_generation = source.credential_generation;
  destination->mqtt_password = source.mqtt_password;
}

}  // namespace

bool PairingPersistentStore::recover(
    PersistentRecoverySnapshot *snapshot,
    RamCredentialBundle *active_credentials,
    RamCredentialBundle *candidate_credentials) {
  if (snapshot == nullptr || this->backend_ == nullptr ||
      this->crypto_ == nullptr)
    return false;
  *snapshot = {};
  if (active_credentials != nullptr)
    active_credentials->clear();
  if (candidate_credentials != nullptr)
    candidate_credentials->clear();

  const auto set_conflict = [&]() -> bool {
    *snapshot = {};
    snapshot->status = PersistentRecoveryStatus::CONFLICT;
    if (active_credentials != nullptr)
      active_credentials->clear();
    if (candidate_credentials != nullptr)
      candidate_credentials->clear();
    return true;
  };

  bool marker_present = false;
  ActiveMarker marker{};
  if (!this->read_marker_(&marker_present, &marker)) {
    snapshot->status = PersistentRecoveryStatus::STORAGE_ERROR;
    return false;
  }

  LoadedRecord slot_a;
  LoadedRecord slot_b;
  const RecordLoadResult result_a =
      this->load_record_(CredentialSlot::A, &slot_a);
  const RecordLoadResult result_b =
      this->load_record_(CredentialSlot::B, &slot_b);
  if (result_a == RecordLoadResult::STORAGE_ERROR ||
      result_b == RecordLoadResult::STORAGE_ERROR) {
    snapshot->status = PersistentRecoveryStatus::STORAGE_ERROR;
    return false;
  }

  if (!marker_present) {
    if (result_a == RecordLoadResult::INVALID ||
        result_b == RecordLoadResult::INVALID) {
      snapshot->status = PersistentRecoveryStatus::INVALID_RECORD;
      return false;
    }
    const size_t present_count =
        static_cast<size_t>(result_a == RecordLoadResult::VALID) +
        static_cast<size_t>(result_b == RecordLoadResult::VALID);
    if (present_count == 0) {
      snapshot->status = PersistentRecoveryStatus::EMPTY;
      return true;
    }
    if (present_count != 1)
      return set_conflict();

    const LoadedRecord &record =
        result_a == RecordLoadResult::VALID ? slot_a : slot_b;
    snapshot->candidate_slot = record.metadata.slot;
    snapshot->candidate_generation = record.metadata.generation;
    snapshot->candidate_credentials_available = true;
    copy_bundle(record.credentials, candidate_credentials);
    if (record.metadata.state == CredentialRecordState::PREPARED) {
      snapshot->status = PersistentRecoveryStatus::NO_ACTIVE_PREPARED;
    } else {
      snapshot->status =
          PersistentRecoveryStatus::NO_ACTIVE_COMMITTED_ORPHAN;
    }
    return true;
  }

  const RecordLoadResult marked_result =
      marker.slot == CredentialSlot::A ? result_a : result_b;
  const RecordLoadResult other_result =
      marker.slot == CredentialSlot::A ? result_b : result_a;
  const LoadedRecord &marked =
      marker.slot == CredentialSlot::A ? slot_a : slot_b;
  const LoadedRecord &other =
      marker.slot == CredentialSlot::A ? slot_b : slot_a;
  if (marked_result == RecordLoadResult::INVALID) {
    snapshot->status = PersistentRecoveryStatus::INVALID_RECORD;
    return false;
  }
  if (marked_result != RecordLoadResult::VALID ||
      marked.metadata.slot != marker.slot ||
      marked.metadata.state != CredentialRecordState::COMMITTED ||
      marked.metadata.generation != marker.generation)
    return set_conflict();

  snapshot->active_slot = marker.slot;
  snapshot->active_generation = marker.generation;
  snapshot->active_credentials_available = true;
  copy_bundle(marked.credentials, active_credentials);

  if (other_result == RecordLoadResult::ABSENT) {
    snapshot->status = PersistentRecoveryStatus::ACTIVE;
    return true;
  }
  if (other_result == RecordLoadResult::INVALID) {
    snapshot->status =
        PersistentRecoveryStatus::ACTIVE_WITH_INVALID_INACTIVE;
    snapshot->candidate_slot = opposite(marker.slot);
    return true;
  }
  if (other.metadata.generation == marker.generation ||
      other.metadata.slot == marker.slot)
    return set_conflict();

  if (other.metadata.state == CredentialRecordState::PREPARED) {
    if (other.metadata.generation <= marker.generation)
      return set_conflict();
    snapshot->status = PersistentRecoveryStatus::ACTIVE_WITH_PREPARED;
    snapshot->candidate_slot = other.metadata.slot;
    snapshot->candidate_generation = other.metadata.generation;
    snapshot->candidate_credentials_available = true;
    copy_bundle(other.credentials, candidate_credentials);
    return true;
  }

  if (other.metadata.state != CredentialRecordState::COMMITTED)
    return set_conflict();
  if (other.metadata.generation < marker.generation) {
    snapshot->status = PersistentRecoveryStatus::ACTIVE;
    snapshot->stale_committed_slot_present = true;
    return true;
  }

  snapshot->status =
      PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN;
  snapshot->candidate_slot = other.metadata.slot;
  snapshot->candidate_generation = other.metadata.generation;
  snapshot->candidate_credentials_available = true;
  copy_bundle(other.credentials, candidate_credentials);
  return true;
}

bool PairingPersistentStore::prepare(
    const RamCredentialBundle &credentials) {
  if (!credentials.valid())
    return false;

  PersistentRecoverySnapshot recovery{};
  RamCredentialBundle active;
  RamCredentialBundle candidate;
  if (!this->recover(&recovery, &active, &candidate))
    return false;
  if (recovery.status != PersistentRecoveryStatus::EMPTY &&
      recovery.status != PersistentRecoveryStatus::ACTIVE &&
      recovery.status !=
          PersistentRecoveryStatus::ACTIVE_WITH_INVALID_INACTIVE)
    return false;
  if (credentials.credential_generation <= recovery.active_generation)
    return false;

  const CredentialSlot slot =
      recovery.active_slot == CredentialSlot::NONE
          ? CredentialSlot::A
          : opposite(recovery.active_slot);
  if (!this->write_record_(slot, CredentialRecordState::PREPARED,
                           credentials))
    return false;
  return this->verify_record_(slot, CredentialRecordState::PREPARED,
                              credentials.credential_generation);
}

bool PairingPersistentStore::commit_prepared() {
  PersistentRecoverySnapshot recovery{};
  RamCredentialBundle active;
  RamCredentialBundle candidate;
  if (!this->recover(&recovery, &active, &candidate))
    return false;
  if (recovery.status !=
          PersistentRecoveryStatus::ACTIVE_WITH_PREPARED &&
      recovery.status != PersistentRecoveryStatus::NO_ACTIVE_PREPARED)
    return false;
  if (!candidate.valid() ||
      candidate.credential_generation != recovery.candidate_generation)
    return false;

  if (!this->write_record_(recovery.candidate_slot,
                           CredentialRecordState::COMMITTED, candidate) ||
      !this->verify_record_(recovery.candidate_slot,
                            CredentialRecordState::COMMITTED,
                            recovery.candidate_generation))
    return false;

  if (!this->write_marker_(recovery.candidate_slot,
                           recovery.candidate_generation))
    return false;
  return this->verify_marker_(recovery.candidate_slot,
                              recovery.candidate_generation);
}

bool PairingPersistentStore::rollback_prepared() {
  PersistentRecoverySnapshot recovery{};
  if (!this->recover(&recovery))
    return false;
  if (recovery.status !=
          PersistentRecoveryStatus::ACTIVE_WITH_PREPARED &&
      recovery.status != PersistentRecoveryStatus::NO_ACTIVE_PREPARED)
    return false;
  return this->erase_slot_(recovery.candidate_slot);
}

bool PairingPersistentStore::discard_committed_orphan() {
  PersistentRecoverySnapshot recovery{};
  if (!this->recover(&recovery) ||
      (recovery.status !=
           PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN &&
       recovery.status !=
           PersistentRecoveryStatus::NO_ACTIVE_COMMITTED_ORPHAN))
    return false;
  return this->erase_slot_(recovery.candidate_slot);
}

const char *PairingPersistentStore::status_name(
    PersistentRecoveryStatus status) {
  switch (status) {
    case PersistentRecoveryStatus::EMPTY:
      return "empty";
    case PersistentRecoveryStatus::ACTIVE:
      return "active";
    case PersistentRecoveryStatus::ACTIVE_WITH_PREPARED:
      return "active_with_prepared";
    case PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN:
      return "active_with_committed_orphan";
    case PersistentRecoveryStatus::ACTIVE_WITH_INVALID_INACTIVE:
      return "active_with_invalid_inactive";
    case PersistentRecoveryStatus::NO_ACTIVE_PREPARED:
      return "no_active_prepared";
    case PersistentRecoveryStatus::NO_ACTIVE_COMMITTED_ORPHAN:
      return "no_active_committed_orphan";
    case PersistentRecoveryStatus::INVALID_RECORD:
      return "invalid_record";
    case PersistentRecoveryStatus::CONFLICT:
      return "conflict";
    case PersistentRecoveryStatus::STORAGE_ERROR:
      return "storage_error";
  }
  return "unknown";
}

const char *PairingPersistentStore::slot_key_(CredentialSlot slot) {
  if (slot == CredentialSlot::A)
    return SLOT_A_KEY;
  if (slot == CredentialSlot::B)
    return SLOT_B_KEY;
  return nullptr;
}

PairingPersistentStore::RecordLoadResult
PairingPersistentStore::load_record_(CredentialSlot physical_slot,
                                     LoadedRecord *record) {
  if (record == nullptr || !valid_slot(physical_slot))
    return RecordLoadResult::STORAGE_ERROR;
  *record = {};
  std::vector<uint8_t> envelope;
  const PersistenceReadResult read =
      this->backend_->read_blob(slot_key_(physical_slot), &envelope);
  if (read == PersistenceReadResult::NOT_FOUND)
    return RecordLoadResult::ABSENT;
  if (read != PersistenceReadResult::OK)
    return RecordLoadResult::STORAGE_ERROR;

  std::vector<uint8_t> plaintext;
  PersistenceEnvelopeMetadata metadata{};
  const bool opened = this->crypto_->open(envelope, &metadata, &plaintext);
  wipe_vector_(&envelope);
  if (!opened || metadata.slot != physical_slot) {
    wipe_vector_(&plaintext);
    return RecordLoadResult::INVALID;
  }

  RamCredentialBundle credentials;
  const bool decoded =
      PairingCredentialCodec::decode(plaintext, &credentials) &&
      credentials.credential_generation == metadata.generation;
  wipe_vector_(&plaintext);
  if (!decoded)
    return RecordLoadResult::INVALID;

  record->present = true;
  record->metadata = metadata;
  copy_bundle(credentials, &record->credentials);
  return RecordLoadResult::VALID;
}

bool PairingPersistentStore::write_record_(
    CredentialSlot slot, CredentialRecordState state,
    const RamCredentialBundle &credentials) {
  if (!valid_slot(slot) ||
      (state != CredentialRecordState::PREPARED &&
       state != CredentialRecordState::COMMITTED))
    return false;

  std::vector<uint8_t> plaintext;
  std::vector<uint8_t> envelope;
  const bool success =
      PairingCredentialCodec::encode(credentials, &plaintext) &&
      this->crypto_->seal(slot, state, credentials.credential_generation,
                          plaintext, &envelope) &&
      this->backend_->write_blob(slot_key_(slot), envelope.data(),
                                 envelope.size()) &&
      this->backend_->commit();
  wipe_vector_(&plaintext);
  wipe_vector_(&envelope);
  return success;
}

bool PairingPersistentStore::verify_record_(
    CredentialSlot slot, CredentialRecordState state, uint32_t generation) {
  LoadedRecord record;
  return this->load_record_(slot, &record) == RecordLoadResult::VALID &&
         record.present && record.metadata.slot == slot &&
         record.metadata.state == state &&
         record.metadata.generation == generation &&
         record.credentials.credential_generation == generation &&
         record.credentials.valid();
}

bool PairingPersistentStore::read_marker_(bool *present,
                                          ActiveMarker *marker) {
  if (present == nullptr || marker == nullptr)
    return false;
  *present = false;
  *marker = {};
  std::vector<uint8_t> blob;
  const PersistenceReadResult read =
      this->backend_->read_blob(ACTIVE_KEY, &blob);
  if (read == PersistenceReadResult::NOT_FOUND)
    return true;
  if (read != PersistenceReadResult::OK)
    return false;
  const bool decoded = this->decode_marker_(blob, marker);
  wipe_vector_(&blob);
  if (!decoded)
    return false;
  *present = true;
  return true;
}

bool PairingPersistentStore::write_marker_(CredentialSlot slot,
                                            uint32_t generation) {
  std::vector<uint8_t> blob = this->encode_marker_(slot, generation);
  if (blob.empty())
    return false;
  const bool success =
      this->backend_->write_blob(ACTIVE_KEY, blob.data(), blob.size()) &&
      this->backend_->commit();
  wipe_vector_(&blob);
  return success;
}

bool PairingPersistentStore::verify_marker_(CredentialSlot slot,
                                             uint32_t generation) {
  bool present = false;
  ActiveMarker marker{};
  return this->read_marker_(&present, &marker) && present &&
         marker.slot == slot && marker.generation == generation;
}

bool PairingPersistentStore::erase_slot_(CredentialSlot slot) {
  const char *key = slot_key_(slot);
  if (key == nullptr || !this->backend_->erase_key(key) ||
      !this->backend_->commit())
    return false;
  std::vector<uint8_t> verify;
  const PersistenceReadResult result =
      this->backend_->read_blob(key, &verify);
  wipe_vector_(&verify);
  return result == PersistenceReadResult::NOT_FOUND;
}

std::vector<uint8_t> PairingPersistentStore::encode_marker_(
    CredentialSlot slot, uint32_t generation) {
  if (!valid_slot(slot) || generation == 0 || this->crypto_ == nullptr)
    return {};

  std::vector<uint8_t> plaintext;
  plaintext.reserve(MARKER_PLAINTEXT_BYTES);
  plaintext.insert(plaintext.end(), MARKER_MAGIC.begin(), MARKER_MAGIC.end());
  put_u16(&plaintext, MARKER_VERSION);
  plaintext.push_back(static_cast<uint8_t>(slot));
  plaintext.push_back(0);
  put_u32(&plaintext, generation);
  if (plaintext.size() != MARKER_PLAINTEXT_BYTES) {
    wipe_vector_(&plaintext);
    return {};
  }

  std::vector<uint8_t> envelope;
  const bool sealed = this->crypto_->seal(
      slot, CredentialRecordState::COMMITTED, generation, plaintext,
      &envelope);
  wipe_vector_(&plaintext);
  if (!sealed) {
    wipe_vector_(&envelope);
    return {};
  }
  return envelope;
}

bool PairingPersistentStore::decode_marker_(
    const std::vector<uint8_t> &blob, ActiveMarker *marker) {
  if (marker == nullptr || this->crypto_ == nullptr)
    return false;
  *marker = {};

  PersistenceEnvelopeMetadata metadata{};
  std::vector<uint8_t> plaintext;
  const bool opened = this->crypto_->open(blob, &metadata, &plaintext);
  const bool valid =
      opened && valid_slot(metadata.slot) &&
      metadata.state == CredentialRecordState::COMMITTED &&
      metadata.generation != 0 &&
      plaintext.size() == MARKER_PLAINTEXT_BYTES &&
      std::equal(MARKER_MAGIC.begin(), MARKER_MAGIC.end(),
                 plaintext.begin()) &&
      read_u16(plaintext.data() + 4) == MARKER_VERSION &&
      plaintext[6] == static_cast<uint8_t>(metadata.slot) &&
      plaintext[7] == 0 &&
      read_u32(plaintext.data() + 8) == metadata.generation;
  if (valid) {
    marker->slot = metadata.slot;
    marker->generation = metadata.generation;
  }
  wipe_vector_(&plaintext);
  return valid;
}

void PairingPersistentStore::wipe_vector_(std::vector<uint8_t> *value) {
  if (value == nullptr)
    return;
  PairingPersistenceCrypto::zeroize(value->data(), value->size());
  value->clear();
  value->shrink_to_fit();
}

}  // namespace esphome::greenhouse_pairing_client
