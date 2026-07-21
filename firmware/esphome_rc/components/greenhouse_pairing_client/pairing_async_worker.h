#pragma once

#include <atomic>
#include <cstdint>

#include "pairing_async_contract.h"

#ifdef USE_ESP32
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#endif

namespace esphome::greenhouse_pairing_client {

class PairingAsyncWorker;

class PairingAsyncExecutionContext {
 public:
  bool cancellation_requested() const;
  bool publish(PairingAsyncPhase phase, const PairingClientSnapshot &client);

 protected:
  friend class PairingAsyncWorker;
  explicit PairingAsyncExecutionContext(PairingAsyncWorker *worker) : worker_(worker) {}

  PairingAsyncWorker *worker_{nullptr};
};

class PairingAsyncDelegate {
 public:
  virtual PairingAsyncOutcome execute_async_pairing(PairingAsyncExecutionContext *context) = 0;
  virtual PairingClientSnapshot async_client_snapshot() const = 0;

 protected:
  virtual ~PairingAsyncDelegate() = default;
};

class PairingAsyncWorker {
 public:
  PairingAsyncWorker() = default;
  ~PairingAsyncWorker();

  PairingAsyncWorker(const PairingAsyncWorker &) = delete;
  PairingAsyncWorker &operator=(const PairingAsyncWorker &) = delete;

  bool start(PairingAsyncDelegate *delegate, uint32_t stack_size_bytes, uint8_t priority);
  bool request(uint32_t operation_id);
  bool cancel();
  bool poll(PairingAsyncSnapshot *snapshot);
  bool stop(uint32_t wait_ms = 45000);

  // active() covers both a queued request and an executing request. This closes
  // the queue-to-task handoff window against main-loop selection/reset changes.
  bool active() const { return this->active_.load(); }
  bool running() const { return this->running_.load(); }
  bool cancellation_requested() const { return this->cancel_requested_.load(); }

 protected:
  friend class PairingAsyncExecutionContext;

  bool publish_phase_(PairingAsyncPhase phase, const PairingClientSnapshot &client);
  void publish_snapshot_();

#ifdef USE_ESP32
  enum class CommandType : uint8_t { RUN = 1, STOP = 2 };
  struct Command {
    CommandType type{CommandType::RUN};
    uint32_t operation_id{0};
  };

  static void task_entry_(void *argument);
  void task_loop_();

  QueueHandle_t command_queue_{nullptr};
  QueueHandle_t snapshot_queue_{nullptr};
  TaskHandle_t task_{nullptr};
#endif

  PairingAsyncDelegate *delegate_{nullptr};
  PairingAsyncContract contract_{};
  std::atomic<bool> running_{false};
  std::atomic<bool> active_{false};
  std::atomic<bool> cancel_requested_{false};
};

}  // namespace esphome::greenhouse_pairing_client
