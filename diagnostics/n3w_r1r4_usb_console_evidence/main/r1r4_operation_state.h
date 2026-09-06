#ifndef R1R4_OPERATION_STATE_H
#define R1R4_OPERATION_STATE_H

#include <stdbool.h>

/* Shared decision predicates used by the diagnostic firmware and the host C
 * harness.  They deliberately contain no ESP-IDF or transport behavior. */
typedef struct {
    bool request_ok;
    bool cancel_api_ok;
    bool termination_observed;
    bool event_loss;
    bool roc_active;
} r1r4_operation_state_t;

static inline bool r1r4_termination_trusted(r1r4_operation_state_t state) {
    return state.request_ok && state.termination_observed && !state.event_loss;
}

static inline bool r1r4_should_clear_roc_active(r1r4_operation_state_t state) {
    return r1r4_termination_trusted(state) && state.roc_active;
}

static inline bool r1r4_should_continue_home_recovery(r1r4_operation_state_t state) {
    return r1r4_termination_trusted(state);
}

static inline bool r1r4_should_send_home_ack(r1r4_operation_state_t state,
                                              bool final_home_return) {
    return r1r4_should_continue_home_recovery(state) && final_home_return;
}

#endif
