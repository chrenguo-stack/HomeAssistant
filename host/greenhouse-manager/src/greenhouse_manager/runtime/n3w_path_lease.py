from __future__ import annotations

import sys

from . import n3w_path_lease_legacy as _legacy

sys.modules[__name__] = _legacy
