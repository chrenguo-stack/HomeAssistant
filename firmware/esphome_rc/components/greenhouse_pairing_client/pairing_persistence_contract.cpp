#include "pairing_persistence_contract.h"

#include <cctype>

namespace esphome::greenhouse_pairing_client {

bool CredentialPersistenceContract::configure(CredentialSlot active_slot,
                                              uint32_t active_generation) {
  if ((active_slot == CredentialSlot::NONE) != (active_generation == 0))
    return false;
  this->snapshot_ = {};
  this->candidate_record_ = {};
  this->snapshot_.active_slot = active_slot;
  this->snapshot_.active_generation = active_generation;
  return true;
}

bool CredentialPersistenceContract::prepare(uint32_t candidate_generation,
                                            const std::string &payload_digest) {
  if (this->snapshot_.prepared || candidate_generation == 0 ||
      candidate_generation <= this->snapshot_.active_generation ||
      !valid_digest(payload_digest))
    return false;
  const CredentialSlot slot =
      this->snapshot_.active_slot == CredentialSlot::NONE
          ? CredentialSlot::A
          : opposite_(this->snapshot_.active_slot);
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
      !valid_record(this->candidate_record_))
    return false;
  this->snapshot_.profile_verified = true;
  return true;
}

bool CredentialPersistenceContract::commit() {
  if (!this->snapshot_.prepared || !this->snapshot_.profile_verified ||
      this->snapshot_.committed || !valid_record(this->candidate_record_))
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

void CredentialPersistenceContract::rollback() {
  this->candidate_record_ = {};
  this->snapshot_.candidate_slot = CredentialSlot::NONE;
  this->snapshot_.candidate_generation = 0;
  this->snapshot_.prepared = false;
  this->snapshot_.profile_verified = false;
  this->snapshot_.committed = false;
}

bool CredentialPersistenceContract::valid_digest(const std::string &value) {
  if (value.size() != 64)
    return false;
  for (const unsigned char character : value) {
    if (!std::isdigit(character) && !(character >= 'a' && character <= 'f'))
      return false;
  }
  return true;
}

bool CredentialPersistenceContract::valid_record(
    const CredentialSlotRecord &record) {
  if (record.schema_version != 1 || record.slot == CredentialSlot::NONE)
    return false;
  if (record.state == CredentialRecordState::EMPTY)
    return record.generation == 0 && record.payload_digest.empty();
  if (record.state != CredentialRecordState::PREPARED &&
      record.state != CredentialRecordState::COMMITTED)
    return false;
  return record.generation != 0 && valid_digest(record.payload_digest);
}

bool CredentialPersistenceContract::recover(
    const CredentialSlotRecord &slot_a, const CredentialSlotRecord &slot_b,
    CredentialSlot marker_slot, uint32_t marker_generation,
    CredentialJournalSnapshot *output) {
  if (output == nullptr)
    return false;
  *output = {};
  const CredentialSlotRecord *marked = nullptr;
  if (marker_slot == CredentialSlot::A)
    marked = &slot_a;
  else if (marker_slot == CredentialSlot::B)
    marked = &slot_b;
  else if (marker_slot != CredentialSlot::NONE)
    return false;

  if (marker_slot == CredentialSlot::NONE)
    return marker_generation == 0;

  if (marked == nullptr || !valid_record(*marked) ||
      marked->state != CredentialRecordState::COMMITTED ||
      marked->slot != marker_slot || marked->generation != marker_generation)
    return false;

  const CredentialSlotRecord &other =
      marker_slot == CredentialSlot::A ? slot_b : slot_a;
  if (other.state == CredentialRecordState::COMMITTED &&
      valid_record(other) && other.generation >= marker_generation)
    return false;

  output->active_slot = marker_slot;
  output->active_generation = marker_generation;
  output->committed = true;
  return true;
}

CredentialSlot CredentialPersistenceContract::opposite_(CredentialSlot slot) {
  return slot == CredentialSlot::A ? CredentialSlot::B : CredentialSlot::A;
}

}  // namespace esphome::greenhouse_pairing_client
