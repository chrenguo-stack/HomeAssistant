#ifdef GREENHOUSE_N3W_ENABLE_LEGACY_RADIO

#include "n3w_radio_legacy.h"

// Exact pre-Phase-5-B implementation snapshot. Keep it in a .h file because
// ESPHome external-component packaging carries C/C++ headers into the generated
// component tree, while arbitrary .inc support files are not copied.
#include "n3w_radio_legacy_impl.h"

#endif  // GREENHOUSE_N3W_ENABLE_LEGACY_RADIO
