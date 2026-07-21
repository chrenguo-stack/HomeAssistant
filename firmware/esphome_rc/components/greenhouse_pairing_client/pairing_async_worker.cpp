#include "pairing_async_worker.h"

#ifdef USE_ESP32
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#endif

namespace esphome::greenhouse_pairing_client {

bool PairingAsyncExecutionContext::cancellation_requested() const {
  return this->worker_ == nullptr || this->worker_->cancellation_requested();
}

bool PairingAsyncExecutionContext::publish(PairingAsyncPhase phase,
                                           const PairingClientSnapshot &client) {
  return this->worker_ != nullptr && this->worker_->publish_phase_(phase, client);
}

PairingAsyncWorker::~PairingAsyncWorker() { this->stop(); }

bool PairingAsyncWorker::start(PairingAsyncDelegate *delegate,
                               uint32_t stack_size_bytes, uint8_t priority) {
#ifdef USE_ESP32
  if (delegate == nullptr || this->task_ != nullptr || this->command_queue_ != nullptr ||
      this->snapshot_queue_ != nullptr || stack_size_bytes < 4096 || stack_size_bytes > 24576 ||
      priority == 0 || priority > 5)
    return false;

  this->command_queue_ = xQueueCreate(1, sizeof(Command));
  this->snapshot_queue_ = xQueueCreate(1, sizeof(PairingAsyncSnapshot));
  if (this->command_queue_ == nullptr || this->snapshot_queue_ == nullptr) {
    if (this->command_queue_ != nullptr)
      vQueueDelete(this->command_queue_);
    if (this->snapshot_queue_ != nullptr)
      vQueueDelete(this->snapshot_queue_);
    this->command_queue_ = nullptr;
    this->snapshot_queue_ = nullptr;
    return false;
  }
  this->delegate_ = delegate;
  const BaseType_t created =
      xTaskCreate(task_entry_, "gh_pairing_worker", stack_size_bytes, this, priority, &this->task_);
  if (created != pdPASS) {
    vQueueDelete(this->command_queue_);
    vQueueDelete(this->snapshot_queue_);
    this->command_queue_ = nullptr;
    this->snapshot_queue_ = nullptr;
    this->delegate_ = nullptr;
    this->task_ = nullptr;
    return false;
  }
  return true;
#else
  (void) delegate;
  (void) stack_size_bytes;
  (void) priority;
  return false;
#endif
}

bool PairingAsyncWorker::request(uint32_t operation_id) {
#ifdef USE_ESP32
  if (operation_id == 0 || this->task_ == nullptr || this->command_queue_ == nullptr ||
      this->active_.load())
    return false;
  const Command command{.type = CommandType::RUN, .operation_id = operation_id};
  return xQueueSend(this->command_queue_, &command, 0) == pdTRUE;
#else
  (void) operation_id;
  return false;
#endif
}

bool PairingAsyncWorker::cancel() {
#ifdef USE_ESP32
  if (!this->active_.load())
    return false;
  this->cancel_requested_.store(true);
  return true;
#else
  return false;
#endif
}

bool PairingAsyncWorker::poll(PairingAsyncSnapshot *snapshot) {
#ifdef USE_ESP32
  if (snapshot == nullptr || this->snapshot_queue_ == nullptr)
    return false;
  return xQueueReceive(this->snapshot_queue_, snapshot, 0) == pdTRUE;
#else
  (void) snapshot;
  return false;
#endif
}

bool PairingAsyncWorker::stop(uint32_t wait_ms) {
#ifdef USE_ESP32
  if (this->task_ == nullptr) {
    if (this->command_queue_ != nullptr)
      vQueueDelete(this->command_queue_);
    if (this->snapshot_queue_ != nullptr)
      vQueueDelete(this->snapshot_queue_);
    this->command_queue_ = nullptr;
    this->snapshot_queue_ = nullptr;
    this->delegate_ = nullptr;
    return true;
  }
  this->cancel_requested_.store(true);
  const Command stop{.type = CommandType::STOP, .operation_id = 0};
  if (this->command_queue_ != nullptr)
    xQueueSend(this->command_queue_, &stop, 0);

  const TickType_t started = xTaskGetTickCount();
  const TickType_t budget = pdMS_TO_TICKS(wait_ms);
  while (this->task_ != nullptr && xTaskGetTickCount() - started < budget)
    vTaskDelay(pdMS_TO_TICKS(10));
  if (this->task_ != nullptr)
    return false;

  if (this->command_queue_ != nullptr)
    vQueueDelete(this->command_queue_);
  if (this->snapshot_queue_ != nullptr)
    vQueueDelete(this->snapshot_queue_);
  this->command_queue_ = nullptr;
  this->snapshot_queue_ = nullptr;
  this->delegate_ = nullptr;
  return true;
#else
  (void) wait_ms;
  return true;
#endif
}

bool PairingAsyncWorker::publish_phase_(PairingAsyncPhase phase,
                                        const PairingClientSnapshot &client) {
  if (!this->contract_.publish(phase, client))
    return false;
  this->publish_snapshot_();
  return true;
}

void PairingAsyncWorker::publish_snapshot_() {
#ifdef USE_ESP32
  if (this->snapshot_queue_ == nullptr)
    return;
  PairingAsyncSnapshot snapshot = this->contract_.snapshot();
  if (this->cancel_requested_.load())
    snapshot.cancel_requested = true;
  xQueueOverwrite(this->snapshot_queue_, &snapshot);
#endif
}

#ifdef USE_ESP32
void PairingAsyncWorker::task_entry_(void *argument) {
  auto *worker = static_cast<PairingAsyncWorker *>(argument);
  if (worker != nullptr)
    worker->task_loop_();
  vTaskDelete(nullptr);
}

void PairingAsyncWorker::task_loop_() {
  PairingAsyncExecutionContext context(this);
  Command command{};
  while (xQueueReceive(this->command_queue_, &command, portMAX_DELAY) == pdTRUE) {
    if (command.type == CommandType::STOP)
      break;
    if (command.type != CommandType::RUN || this->delegate_ == nullptr)
      continue;

    this->cancel_requested_.store(false);
    this->active_.store(true);
    const PairingClientSnapshot initial = this->delegate_->async_client_snapshot();
    if (!this->contract_.queue(command.operation_id, initial)) {
      this->active_.store(false);
      continue;
    }
    this->publish_snapshot_();

    PairingAsyncOutcome outcome = this->delegate_->execute_async_pairing(&context);
    if (this->cancel_requested_.load() && outcome != PairingAsyncOutcome::SUCCESS)
      outcome = PairingAsyncOutcome::CANCELLED;
    const PairingClientSnapshot final_snapshot = this->delegate_->async_client_snapshot();
    if (outcome == PairingAsyncOutcome::CANCELLED)
      this->contract_.request_cancel();
    if (!this->contract_.finish(outcome, final_snapshot))
      this->contract_.finish(PairingAsyncOutcome::INVALID_TRANSITION, final_snapshot);
    this->publish_snapshot_();
    this->active_.store(false);
  }
  this->active_.store(false);
  this->cancel_requested_.store(false);
  this->task_ = nullptr;
}
#endif

}  // namespace esphome::greenhouse_pairing_client
