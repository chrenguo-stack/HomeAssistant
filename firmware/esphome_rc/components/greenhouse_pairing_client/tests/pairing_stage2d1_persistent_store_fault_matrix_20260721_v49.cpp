#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "pairing_persistent_store.h"

using namespace esphome::greenhouse_pairing_client;

class MemoryBackend final : public PairingPersistenceBackend {
 public:
  struct Pending {
    bool erase{false};
    std::vector<uint8_t> value;
  };

  PersistenceReadResult read_blob(const char *key,
                                  std::vector<uint8_t> *value) override {
    if (poisoned_ || key == nullptr || value == nullptr)
      return PersistenceReadResult::ERROR;
    auto pending = pending_.find(key);
    if (pending != pending_.end()) {
      if (pending->second.erase)
        return PersistenceReadResult::NOT_FOUND;
      *value = pending->second.value;
      return PersistenceReadResult::OK;
    }
    auto found = durable_.find(key);
    if (found == durable_.end())
      return PersistenceReadResult::NOT_FOUND;
    *value = found->second;
    return PersistenceReadResult::OK;
  }

  bool write_blob(const char *key, const uint8_t *value,
                  size_t length) override {
    if (poisoned_ || should_fail_() || key == nullptr || value == nullptr ||
        length == 0)
      return false;
    pending_[key] = Pending{false, std::vector<uint8_t>(value, value + length)};
    return true;
  }

  bool erase_key(const char *key) override {
    if (poisoned_ || should_fail_() || key == nullptr)
      return false;
    pending_[key] = Pending{true, {}};
    return true;
  }

  bool commit() override {
    if (poisoned_ || should_fail_())
      return false;
    for (const auto &[key, pending] : pending_) {
      if (pending.erase)
        durable_.erase(key);
      else
        durable_[key] = pending.value;
    }
    pending_.clear();
    return true;
  }

  void power_cycle() {
    pending_.clear();
    poisoned_ = false;
  }
  void fail_on_mutation(size_t mutation) {
    mutation_ = 0;
    fail_on_ = mutation;
    poisoned_ = false;
  }
  void clear_failure() {
    mutation_ = 0;
    fail_on_.reset();
  }
  std::map<std::string, std::vector<uint8_t>> &durable() { return durable_; }

 private:
  bool should_fail_() {
    mutation_++;
    if (fail_on_.has_value() && mutation_ == *fail_on_) {
      poisoned_ = true;
      return true;
    }
    return false;
  }

  std::map<std::string, std::vector<uint8_t>> durable_;
  std::map<std::string, Pending> pending_;
  size_t mutation_{0};
  std::optional<size_t> fail_on_;
  bool poisoned_{false};
};

RamCredentialBundle make_credentials(uint32_t generation) {
  RamCredentialBundle bundle;
  bundle.schema = "gh.pair.credentials/1";
  bundle.system_id = "greenhouse";
  bundle.node_id = "node-" + std::to_string(generation);
  bundle.broker_host = "broker.local";
  bundle.broker_port = 8883;
  bundle.broker_tls_server_name = "broker.local";
  bundle.ca_pem = "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n";
  bundle.mqtt_username = "node_user_" + std::to_string(generation);
  bundle.mqtt_client_id = "node_client_" + std::to_string(generation);
  bundle.credential_generation = generation;
  bundle.mqtt_password = "test-value-" + std::to_string(generation);
  assert(bundle.valid());
  return bundle;
}

std::vector<uint8_t> make_record(PairingPersistenceCrypto *crypto,
                                 CredentialSlot slot,
                                 CredentialRecordState state,
                                 const RamCredentialBundle &credentials) {
  std::vector<uint8_t> plaintext;
  std::vector<uint8_t> envelope;
  assert(PairingCredentialCodec::encode(credentials, &plaintext));
  assert(crypto->seal(slot, state, credentials.credential_generation,
                      plaintext, &envelope));
  std::fill(plaintext.begin(), plaintext.end(), 0);
  return envelope;
}

void assert_active(PairingPersistentStore *store, uint32_t generation,
                   PersistentRecoveryStatus allowed =
                       PersistentRecoveryStatus::ACTIVE) {
  PersistentRecoverySnapshot snapshot{};
  RamCredentialBundle active;
  assert(store->recover(&snapshot, &active));
  assert(snapshot.status == allowed);
  assert(snapshot.active_credentials_available);
  assert(snapshot.active_generation == generation);
  assert(active.credential_generation == generation);
  assert(active.valid());
}

void assert_poisoned(PairingPersistentStore *store) {
  PersistentRecoverySnapshot immediate{};
  assert(!store->recover(&immediate));
  assert(immediate.status == PersistentRecoveryStatus::STORAGE_ERROR);
}

int main() {
  std::array<uint8_t, 32> root_key{};
  for (size_t i = 0; i < root_key.size(); i++)
    root_key[i] = static_cast<uint8_t>(i + 1);
  FixedPersistenceKeyProvider key_provider(root_key);
  PairingPersistenceCrypto crypto(&key_provider);

  // Codec failure always clears caller-owned output buffers.
  {
    std::vector<uint8_t> encoded = {1, 2, 3};
    RamCredentialBundle invalid;
    assert(!PairingCredentialCodec::encode(invalid, &encoded));
    assert(encoded.empty());

    RamCredentialBundle stale = make_credentials(99);
    const std::vector<uint8_t> invalid_payload = {'b', 'a', 'd'};
    assert(!PairingCredentialCodec::decode(invalid_payload, &stale));
    assert(!stale.valid());
    assert(stale.mqtt_password.empty());
  }

  // The envelope binds slot, state and generation and cannot be opened with a
  // different device root key.
  {
    const std::vector<uint8_t> plaintext = {'c', 'r', 'e', 'd'};
    std::vector<uint8_t> envelope;
    assert(crypto.seal(CredentialSlot::A, CredentialRecordState::PREPARED,
                       1, plaintext, &envelope));
    PersistenceEnvelopeMetadata metadata{};
    std::vector<uint8_t> recovered;
    assert(crypto.open(envelope, &metadata, &recovered));
    assert(recovered == plaintext);
    assert(metadata.slot == CredentialSlot::A);
    assert(metadata.generation == 1);

    auto slot_tampered = envelope;
    slot_tampered[6] = static_cast<uint8_t>(CredentialSlot::B);
    assert(!crypto.open(slot_tampered, &metadata, &recovered));
    assert(recovered.empty());

    auto generation_tampered = envelope;
    generation_tampered[11] ^= 0x01;
    assert(!crypto.open(generation_tampered, &metadata, &recovered));
    assert(recovered.empty());

    std::array<uint8_t, 32> other_root{};
    other_root.fill(0xa5);
    FixedPersistenceKeyProvider other_provider(other_root);
    PairingPersistenceCrypto other_crypto(&other_provider);
    assert(!other_crypto.open(envelope, &metadata, &recovered));
    assert(recovered.empty());
  }

  MemoryBackend backend;
  PairingPersistentStore store(&backend, &crypto);

  PersistentRecoverySnapshot snapshot{};
  assert(store.recover(&snapshot));
  assert(snapshot.status == PersistentRecoveryStatus::EMPTY);

  // First-enrollment power cuts never create an unverified active marker.
  for (size_t cut = 1; cut <= 4; cut++) {
    MemoryBackend trial;
    PairingPersistentStore initial(&trial, &crypto);
    auto candidate = make_credentials(1);
    assert(initial.prepare(candidate));
    trial.fail_on_mutation(cut);
    assert(!initial.commit_prepared());
    assert_poisoned(&initial);
    trial.power_cycle();
    trial.clear_failure();
    PairingPersistentStore rebooted(&trial, &crypto);
    assert(rebooted.recover(&snapshot));
    assert(snapshot.active_generation == 0);
    if (cut <= 2) {
      assert(snapshot.status ==
             PersistentRecoveryStatus::NO_ACTIVE_PREPARED);
    } else {
      assert(snapshot.status ==
             PersistentRecoveryStatus::NO_ACTIVE_COMMITTED_ORPHAN);
      assert(rebooted.discard_committed_orphan());
      assert(rebooted.recover(&snapshot));
      assert(snapshot.status == PersistentRecoveryStatus::EMPTY);
    }
  }

  auto first = make_credentials(1);
  assert(store.prepare(first));
  assert(store.recover(&snapshot));
  assert(snapshot.status == PersistentRecoveryStatus::NO_ACTIVE_PREPARED);
  assert(store.commit_prepared());
  assert_active(&store, 1);

  auto second = make_credentials(2);
  assert(store.prepare(second));
  assert(store.recover(&snapshot));
  assert(snapshot.status == PersistentRecoveryStatus::ACTIVE_WITH_PREPARED);
  assert(store.rollback_prepared());
  assert_active(&store, 1);

  assert(store.prepare(second));
  assert(store.commit_prepared());
  assert_active(&store, 2);
  const auto generation_two_marker = backend.durable().at("active");
  assert(generation_two_marker.size() > 16);

  // The active marker is an authenticated encrypted envelope, not a CRC-only
  // selector. Any bit change is rejected before credentials are returned.
  {
    auto saved = backend.durable().at("active");
    backend.durable().at("active")[3] ^= 0x01;
    RamCredentialBundle stale = make_credentials(90);
    assert(!store.recover(&snapshot, &stale));
    assert(snapshot.status == PersistentRecoveryStatus::STORAGE_ERROR);
    assert(!stale.valid());
    backend.durable()["active"] = saved;
  }

  // Corrupting the inactive slot never activates it and does not discard the
  // marker-selected active credentials. The next prepare may overwrite it.
  {
    auto saved = backend.durable().at("slot_a");
    backend.durable().at("slot_a")[20] ^= 0x80;
    RamCredentialBundle active;
    assert(store.recover(&snapshot, &active));
    assert(snapshot.status ==
           PersistentRecoveryStatus::ACTIVE_WITH_INVALID_INACTIVE);
    assert(snapshot.active_generation == 2);
    assert(active.credential_generation == 2);
    auto repair = make_credentials(3);
    assert(store.prepare(repair));
    assert(store.rollback_prepared());
    backend.durable()["slot_a"] = saved;
  }

  // Prepare power-cut matrix: old active generation must remain usable after a
  // reboot, while the live handle is poisoned immediately after mutation error.
  for (size_t cut = 1; cut <= 2; cut++) {
    MemoryBackend trial = backend;
    trial.fail_on_mutation(cut);
    PairingPersistentStore trial_store(&trial, &crypto);
    auto third = make_credentials(3);
    assert(!trial_store.prepare(third));
    assert_poisoned(&trial_store);
    trial.power_cycle();
    trial.clear_failure();
    PairingPersistentStore rebooted(&trial, &crypto);
    assert_active(&rebooted, 2);
  }

  // Commit power-cut matrix after PREPARED is durable.
  for (size_t cut = 1; cut <= 4; cut++) {
    MemoryBackend trial = backend;
    PairingPersistentStore initial(&trial, &crypto);
    auto third = make_credentials(3);
    assert(initial.prepare(third));

    trial.fail_on_mutation(cut);
    PairingPersistentStore committing(&trial, &crypto);
    assert(!committing.commit_prepared());
    assert_poisoned(&committing);
    trial.power_cycle();
    trial.clear_failure();
    PairingPersistentStore rebooted(&trial, &crypto);
    assert(rebooted.recover(&snapshot));
    if (cut <= 2) {
      assert(snapshot.status ==
             PersistentRecoveryStatus::ACTIVE_WITH_PREPARED);
      assert(snapshot.active_generation == 2);
    } else {
      assert(snapshot.status ==
             PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN);
      assert(snapshot.active_generation == 2);
      assert(snapshot.candidate_generation == 3);
      assert(rebooted.discard_committed_orphan());
      assert_active(&rebooted, 2);
    }
  }

  // Successful transaction switches the marker only after committed record.
  auto third = make_credentials(3);
  assert(store.prepare(third));
  assert(store.commit_prepared());
  assert_active(&store, 3);

  // A replayed, previously valid complete marker remains the explicit
  // anti-rollback limitation: old active is retained and newer record is
  // exposed as an orphan, never silently selected.
  {
    MemoryBackend trial = backend;
    trial.durable()["active"] = generation_two_marker;
    PairingPersistentStore replayed(&trial, &crypto);
    RamCredentialBundle active;
    RamCredentialBundle candidate;
    assert(replayed.recover(&snapshot, &active, &candidate));
    assert(snapshot.status ==
           PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN);
    assert(active.credential_generation == 2);
    assert(candidate.credential_generation == 3);
  }

  // A higher committed orphan is never activated automatically.
  {
    MemoryBackend trial = backend;
    PairingPersistentStore trial_store(&trial, &crypto);
    auto fourth = make_credentials(4);
    assert(trial_store.prepare(fourth));
    trial.fail_on_mutation(3);
    assert(!trial_store.commit_prepared());
    assert_poisoned(&trial_store);
    trial.power_cycle();
    trial.clear_failure();
    PairingPersistentStore rebooted(&trial, &crypto);
    RamCredentialBundle active;
    RamCredentialBundle candidate;
    assert(rebooted.recover(&snapshot, &active, &candidate));
    assert(snapshot.status ==
           PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN);
    assert(active.credential_generation == 3);
    assert(candidate.credential_generation == 4);
  }

  // Ambiguous records never leave previously supplied credential outputs live.
  {
    MemoryBackend trial = backend;
    auto duplicate = make_credentials(3);
    trial.durable()["slot_b"] = make_record(
        &crypto, CredentialSlot::B, CredentialRecordState::COMMITTED,
        duplicate);
    PairingPersistentStore conflicted(&trial, &crypto);
    RamCredentialBundle active = make_credentials(80);
    RamCredentialBundle candidate = make_credentials(81);
    assert(conflicted.recover(&snapshot, &active, &candidate));
    assert(snapshot.status == PersistentRecoveryStatus::CONFLICT);
    assert(!snapshot.active_credentials_available);
    assert(!snapshot.candidate_credentials_available);
    assert(!active.valid());
    assert(!candidate.valid());
  }

  // Inactive ciphertext corruption is isolated; active ciphertext corruption
  // remains a hard failure.
  {
    MemoryBackend trial = backend;
    trial.durable().at("slot_b").back() ^= 0x01;
    PairingPersistentStore rebooted(&trial, &crypto);
    RamCredentialBundle active;
    assert(rebooted.recover(&snapshot, &active));
    assert(snapshot.status ==
           PersistentRecoveryStatus::ACTIVE_WITH_INVALID_INACTIVE);
    assert(active.credential_generation == 3);
  }
  {
    MemoryBackend trial = backend;
    trial.durable().at("slot_a").back() ^= 0x01;
    PairingPersistentStore rebooted(&trial, &crypto);
    RamCredentialBundle stale = make_credentials(70);
    assert(!rebooted.recover(&snapshot, &stale));
    assert(snapshot.status == PersistentRecoveryStatus::INVALID_RECORD);
    assert(!stale.valid());
  }

  std::cout << "stage2d1 persistent store fault matrix passed\n";
  return 0;
}
