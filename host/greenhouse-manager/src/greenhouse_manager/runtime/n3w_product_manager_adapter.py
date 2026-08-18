from __future__ import annotations

import sys

from . import n3w_product_manager_adapter_legacy as _legacy

sys.modules[__name__] = _legacy
