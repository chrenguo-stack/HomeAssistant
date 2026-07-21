#include <cassert>
#include <iostream>

#include "pairing_async_contract.h"
#include "pairing_mqtt_activation_contract.h"
#include "pairing_persistence_contract.h"

using namespace esphome::greenhouse_pairing_client;

int main() {
  PairingClientSnapshot client{};
  PairingAsyncContract async;
  assert(async.queue(1, client));
  assert(!async.queue(2, client));
  assert(async.begin(client));
  client.state = PairingClientState::SELECTION_REQUIRED;
  client.selection_required = true;
  assert(async.finish(PairingAsyncOutcome::SELECTION_REQUIRED, client));
  assert(async.snapshot().phase == PairingAsyncPhase::WAITING_SELECTION);
  assert(!async.snapshot().active);

  client.state = PairingClientState::CLAIM_READY;
  client.selection_required = false;
  assert(async.queue(2, client));
  assert(async.publish(PairingAsyncPhase::SECURE_PAIRING, client));
  client.state = PairingClientState::CREDENTIALS_STAGED;
  client.credentials_staged = true;
  client.credential_generation = 7;
  assert(async.publish(PairingAsyncPhase::RAM_STAGED, client));
  assert(async.finish(PairingAsyncOutcome::SUCCESS, client));
  assert(async.snapshot().phase == PairingAsyncPhase::COMPLETED);
  assert(async.snapshot().credential_generation == 7);

  CredentialPersistenceContract persistence;
  assert(persistence.configure(CredentialSlot::A, 6));
  const std::string digest(64, 'a');
  assert(persistence.prepare(7, digest));
  assert(!persistence.commit());
  assert(persistence.mark_profile_verified());
  assert(persistence.commit());
  assert(persistence.snapshot().active_slot == CredentialSlot::B);
  assert(persistence.snapshot().active_generation == 7);

  CredentialJournalSnapshot recovered{};
  CredentialSlotRecord slot_a{
      .schema_version = 1,
      .slot = CredentialSlot::A,
      .state = CredentialRecordState::COMMITTED,
      .generation = 6,
      .payload_digest = std::string(64, 'b'),
  };
  CredentialSlotRecord slot_b = persistence.candidate_record();
  assert(CredentialPersistenceContract::recover(
      slot_a, slot_b, CredentialSlot::B, 7, &recovered));
  assert(recovered.active_generation == 7);
  assert(!CredentialPersistenceContract::recover(
      slot_a, slot_b, CredentialSlot::A, 6, &recovered));

  MqttActivationContract mqtt;
  assert(mqtt.configure(6));
  assert(mqtt.stage(7));
  assert(mqtt.begin_probe());
  assert(!mqtt.record_probe(true, true, false));
  assert(mqtt.snapshot().phase == MqttActivationPhase::FAILED);
  mqtt.rollback();
  assert(mqtt.stage(7));
  assert(mqtt.begin_probe());
  assert(mqtt.record_probe(true, true, true));
  assert(mqtt.activate());
  assert(mqtt.snapshot().active_generation == 7);

  std::cout << "stage2c3 async and persistence contracts passed\n";
  return 0;
}
