from __future__ import annotations

import os
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CORE = SKILL_ROOT / "assets" / "template" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from circuitlab_platform import (  # noqa: E402,F401
    COMPONENT_SCHEMA,
    HIL_SCHEMA,
    CircuitLabPlatform,
    ComponentRegistry,
    HilEngine,
    generate_fixture,
    import_sindri_assets,
)


def default_data_root() -> Path:
    return Path(os.environ.get("CIRCUITLAB_DATA_DIR", "~/.local/share/circuitlab")).expanduser().resolve()

