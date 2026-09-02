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
    component_family,
    generate_fixture,
    is_chip_package,
    import_sindri_assets,
    require_chip_package,
    sha256_json,
    validate_component,
)


def default_data_root() -> Path:
    return Path(os.environ.get("CIRCUITLAB_DATA_DIR", "~/.local/share/circuitlab")).expanduser().resolve()
