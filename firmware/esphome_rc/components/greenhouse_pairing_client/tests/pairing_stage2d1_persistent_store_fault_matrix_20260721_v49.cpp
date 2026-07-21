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
    if (key == nullptr || value == nullptr)
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
    if (should_fail_() || key == nullptr || value == nullptr || length == 0)
      return false;
    pending_[key] = Pending{false, std::vector<uint8_t>(value, value + length)};
    return true;
  }

  bool erase_key(const char *key) override {
    if (should_fail_() || key == nullptr)
      return false;
    pending_[key] = Pending{true, {}};
    return true;
  }

  bool commit() override {
    if (should_fail_())
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

  void power_cycle() { pending_.clear(); }
  void fail_on_mutation(size_t mutation) {
    mutation_ = 0;
    fail_on_ = mutation;
  }
  void clear_failure() {
    mutation_ = 0;
    fail_on_.reset();
  }
  std::map<std::string, std::vector<uint8_t>> &durable() { return durable_; }

 private:
  bool should_fail_() {
    mutation_++;
    return fail_on_.has_value() && mutation_ == *fail_on_;
  }

  std::map<std::string, std::vector<uint8_t>> durable_;
  std::map<std::string, Pending> pending_;
  size_t mutation_{0};
  std::optional<size_t> fail_on_;
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
  bundle.mqtt_password = "password-" + std::to_string(generation);
  assert(bundle.valid());
  return bundle;
}

void assert_active(PairingPersistentStore *store, uint32_t generation,
                   PersistentRecoveryStatus allowed =
                       PersistentRecoveryStatus::ACTIVE) {
  PersistentRecoverySnapshot snapshot{};
  RamCredentialBundle active;
  assert(store->recover(&snapshot, &active));
  assert(snapshot.status == allowed);
  assert(snapshot.active_generation == generation);
  assert(active.credential_generation == generation);
  assert(active.valid());
}

int main() {
  std::array<uint8_t, 32> root_key{};
  for (size_t i = 0; i < root_key.size(); i++)
    root_key[i] = static_cast<uint8_t>(i + 1);
  FixedPersistenceKeyProvider key_provider(root_key);
  PairingPersistenceCrypto crypto(&key_provider);
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
  assert(snapshot.status != PersistentRecoveryStatus::CONFLICT);

  // Corrupting the active marker must fail closed.
  {
    auto saved = backend.durable().at("active");
    backend.durable().at("active")[3] ^= 0x01;
    assert(!store.recover(&snapshot));
    assert(snapshot.status == PersistentRecoveryStatus::STORAGE_ERROR);
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

  // Prepare power-cut matrix: old active generation must remain usable.
  for (size_t cut = 1; cut <= 2; cut++) {
    MemoryBackend trial = backend;
    trial.fail_on_mutation(cut);
    PairingPersistentStore trial_store(&trial, &crypto);
    auto third = make_credentials(3);
    assert(!trial_store.prepare(third));
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

  // A higher committed orphan is never activated automatically.
  {
    MemoryBackend trial = backend;
    PairingPersistentStore trial_store(&trial, &crypto);
    auto fourth = make_credentials(4);
    assert(trial_store.prepare(fourth));
    trial.fail_on_mutation(3);  // marker write fails after committed slot commit
    assert(!trial_store.commit_prepared());
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
    assert(!rebooted.recover(&snapshot));
    assert(snapshot.status == PersistentRecoveryStatus::INVALID_RECORD);
  }

  std::cout << "stage2d1 persistent store fault matrix passed\n";
  return 0;
}
