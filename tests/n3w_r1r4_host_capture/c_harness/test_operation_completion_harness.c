#include <assert.h>

#include "r1r4_operation_state.h"

int main(void) {
    const r1r4_operation_state_t trusted_natural = {true, true, false, true};
    const r1r4_operation_state_t trusted_after_cancel_api_failure = {true, true, false, true};
    const r1r4_operation_state_t no_matching_event = {true, false, false, true};
    const r1r4_operation_state_t event_lost = {true, true, true, true};
    const r1r4_operation_state_t request_failed = {false, true, false, true};

    assert(r1r4_termination_trusted(trusted_natural));
    assert(r1r4_termination_trusted(trusted_after_cancel_api_failure));
    assert(!r1r4_termination_trusted(no_matching_event));
    assert(!r1r4_termination_trusted(event_lost));
    assert(!r1r4_termination_trusted(request_failed));
    assert(r1r4_should_clear_roc_active(trusted_natural));
    assert(!r1r4_should_clear_roc_active(no_matching_event));
    assert(r1r4_should_continue_home_recovery(trusted_natural));
    assert(!r1r4_should_continue_home_recovery(event_lost));
    assert(r1r4_should_send_home_ack(trusted_natural, true));
    assert(!r1r4_should_send_home_ack(trusted_natural, false));
    return 0;
}
