#include "pairing_persistence_contract.h"

namespace esphome::greenhouse_pairing_client {

bool CredentialPersistenceContract::configure(CredentialSlot active_slot,
                                              uint32_t active_generation) {
  if ((active_slot == CredentialSlot::NONE) != (active_generation == 0) ||
      (active_slot != CredentialSlot::NONE && !valid_slot(active_slot)))
    return false;
  this->snapshot_ = {};
  this->candidate_record_ = {};
  this->snapshot_.active_slot = active_slot;
  this->snapshot_.active_generation = active_generation;
  return true;
}

bool CredentialPersistenceContract::prepare(uint32_t candidate_generation,
                                            const std::string &payload_digest) {
  if (this->snapshot_.prepared || this->snapshot_.committed ||
      candidate_generation == 0 ||
      candidate_generation <= this->snapshot_.active_generation ||
      !valid_digest(payload_digest))
    return false;
  const CredentialSlot slot =
      this->snapshot_.active_slot == CredentialSlot::NONE
          ? CredentialSlot::A
          : opposite_(this->snapshot_.active_slot);
  if (!valid_slot(slot))
    return false;
  this->candidate_record_ = {
      .schema_version = 1,
      .slot = slot,
      .state = CredentialRecordState::PREPARED,
      .generation = candidate_generation,
      .payload_digest = payload_digest,
  };
  this->snapshot_.candidate_slot = slot;
  this->snapshot_.candidate_generation = candidate_generation;
  this->snapshot_.prepared = true;
  this->snapshot_.profile_verified = false;
  this->snapshot_.committed = false;
  return true;
}

bool CredentialPersistenceContract::mark_profile_verified() {
  if (!this->snapshot_.prepared || this->snapshot_.committed ||
      !record_matches_slot(this->candidate_record_, this->snapshot_.candidate_slot))
    return false;
  this->snapshot_.profile_verified = true;
  return true;
}

bool CredentialPersistenceContract::commit() {
  if (!this->snapshot_.prepared || !this->snapshot_.profile_verified ||
      this->snapshot_.committed ||
      !record_matches_slot(this->candidate_record_, this->snapshot_.candidate_slot))
    return false;
  this->candidate_record_.state = CredentialRecordState::COMMITTED;
  this->snapshot_.active_slot = this->snapshot_.candidate_slot;
  this->snapshot_.active_generation = this->snapshot_.candidate_generation;
  this->snapshot_.committed = true;
  this->snapshot_.prepared = false;
  this->snapshot_.candidate_slot = CredentialSlot::NONE;
  this->snapshot_.candidate_generation = 0;
  return true;
}

bool CredentialPersistenceContract::rollback() {
  if (!this->snapshot_.prepared || this->snapshot_.committed)
    return false;
  this->candidate_record_ = {};
  this->snapshot_.candidate_slot = CredentialSlot::NONE;
  this->snapshot_.candidate_generation = 0;
  this->snapshot_.prepared = false;
  this->snapshot_.profile_verified = false;
  return true;
}

bool CredentialPersistenceContract::valid_slot(CredentialSlot slot) {
  return slot == CredentialSlot::A || slot == CredentialSlot::B;
}

bool CredentialPersistenceContract::valid_digest(const std::string &value) {
  if (value.size() != 64)
    return false;
  for (const unsigned char character : value) {
    if (!((character >= '0' && character <= '9') ||
          (character >= 'a' && character <= 'f')))
      return false;
  }
  return true;
}

bool CredentialPersistenceContract::valid_record(
    const CredentialSlotRecord &record) {
  if (record.schema_version != 1)
    return false;
  if (record.state == CredentialRecordState::EMPTY) {
    return (record.slot == CredentialSlot::NONE || valid_slot(record.slot)) &&
           record.generation == 0 && record.payload_digest.empty();
  }
  if (!valid_slot(record.slot) ||
      (record.state != CredentialRecordState::PREPARED &&
       record.state != CredentialRecordState::COMMITTED))
    return false;
  return record.generation != 0 && valid_digest(record.payload_digest);
}

bool CredentialPersistenceContract::record_matches_slot(
    const CredentialSlotRecord &record, CredentialSlot physical_slot) {
  if (!valid_slot(physical_slot) || !valid_record(record))
    return false;
  if (record.state == CredentialRecordState::EMPTY)
    return record.slot == CredentialSlot::NONE || record.slot == physical_slot;
  return record.slot == physical_slot;
}

bool CredentialPersistenceContract::recover(
    const CredentialSlotRecord &slot_a, const CredentialSlotRecord &slot_b,
    CredentialSlot marker_slot, uint32_t marker_generation,
    CredentialJournalSnapshot *output) {
  if (output == nullptr || !record_matches_slot(slot_a, CredentialSlot::A) ||
      !record_matches_slot(slot_b, CredentialSlot::B))
    return false;
  *output = {};

  if (marker_slot == CredentialSlot::NONE) {
    if (marker_generation != 0 ||
        slot_a.state == CredentialRecordState::COMMITTED ||
        slot_b.state == CredentialRecordState::COMMITTED)
      return false;
    const bool prepared_a = slot_a.state == CredentialRecordState::PREPARED;
    const bool prepared_b = slot_b.state == CredentialRecordState::PREPARED;
    if (prepared_a && prepared_b)
      return false;
    if (prepared_a)
      return capture_prepared_(slot_a, 0, output);
    if (prepared_b)
      return capture_prepared_(slot_b, 0, output);
    return true;
  }

  if (!valid_slot(marker_slot) || marker_generation == 0)
    return false;
  const CredentialSlotRecord &marked =
      marker_slot == CredentialSlot::A ? slot_a : slot_b;
  const CredentialSlotRecord &other =
      marker_slot == CredentialSlot::A ? slot_b : slot_a;
  if (marked.state != CredentialRecordState::COMMITTED ||
      marked.slot != marker_slot || marked.generation != marker_generation)
    return false;

  output->active_slot = marker_slot;
  output->active_generation = marker_generation;
  output->committed = true;

  if (other.state == CredentialRecordState::COMMITTED)
    return other.generation < marker_generation;
  if (other.state == CredentialRecordState::PREPARED)
    return capture_prepared_(other, marker_generation, output);
  return other.state == CredentialRecordState::EMPTY;
}

CredentialSlot CredentialPersistenceContract::opposite_(CredentialSlot slot) {
  if (slot == CredentialSlot::A)
    return CredentialSlot::B;
  if (slot == CredentialSlot::B)
    return CredentialSlot::A;
  return CredentialSlot::NONE;
}

bool CredentialPersistenceContract::capture_prepared_(
    const CredentialSlotRecord &record, uint32_t active_generation,
    CredentialJournalSnapshot *output) {
  if (output == nullptr || record.state != CredentialRecordState::PREPARED ||
      !valid_slot(record.slot) || record.generation <= active_generation)
    return false;
  output->candidate_slot = record.slot;
  output->candidate_generation = record.generation;
  output->prepared = true;
  return true;
}

}  // namespace esphome::greenhouse_pairing_client
