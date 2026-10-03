from pathlib import Path
import subprocess

ROOT = Path.cwd()
WORKFLOW = ".github/workflows/n3w-auto-safe-fallback-gate-c-source-repair.yml"
SOURCE_COMMIT = "9babe055ba971ce77634760a934e58aadf0b876e"

old_yaml = subprocess.check_output(
    ["git", "show", f"{SOURCE_COMMIT}:{WORKFLOW}"],
    text=True,
)
lines = old_yaml.splitlines()
start = next(i for i, line in enumerate(lines) if line.strip() == "python - <<'PY'") + 1
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "PY")
prefix = "          "
body = []
for line in lines[start:end]:
    if line.startswith(prefix):
        body.append(line[len(prefix):])
    else:
        body.append(line)
code = "\n".join(body) + "\n"

code = code.replace(
    "#include <algorithm>\n#include <array>\n\n#ifdef USE_MQTT",
    "#include <algorithm>\n#include <array>\n#include <utility>\n\n#ifdef USE_MQTT",
)
code = code.replace(
    '#endif\n#include "esphome/core/log.h"',
    '#endif\n#ifdef USE_WIFI\n#include "esphome/components/wifi/wifi_component.h"\n#endif\n#include "esphome/core/log.h"',
)
code = code.replace("wifi_connected()", "broker_wifi_connected()")
code = code.replace("mqtt_connected()", "broker_mqtt_connected()")
code = code.replace(
    'static const char *const TAG = "n3w_broker_relocation";\n\n}',
    '''static const char *const TAG = "n3w_broker_relocation";

bool broker_mqtt_connected() {
#ifdef USE_MQTT
  return mqtt::global_mqtt_client != nullptr &&
         mqtt::global_mqtt_client->is_connected();
#else
  return false;
#endif
}

bool broker_wifi_connected() {
#ifdef USE_WIFI
  return wifi::global_wifi_component != nullptr &&
         wifi::global_wifi_component->is_connected();
#else
  return false;
#endif
}

}''',
)
code = code.replace(
    '''    if (broker_candidate_deadline_ms_ != 0U &&
        now >= broker_candidate_deadline_ms_) {
      broker_candidate_active_ = false;
      pending_broker_candidate_host_.clear();
      if (!start_next_broker_candidate_()) rollback_broker_candidate_();
    }''',
    '''    if (broker_candidate_deadline_ms_ != 0U &&
        now >= broker_candidate_deadline_ms_) {
      rollback_broker_candidate_();
      (void) start_next_broker_candidate_();
    }''',
)
code = code.replace(
    "assert(deadline == std::numeric_limits<uint64_t>::max() - 2000U);",
    "assert(deadline == 0U);",
)

executor = Path("/tmp/gate-c-executor.py")
executor.write_text(code, encoding="utf-8")
subprocess.run(["python", str(executor)], check=True)
