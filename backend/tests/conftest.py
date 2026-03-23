from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

# The backend modules use imports like `from core.models import ...`,
# so the backend directory needs to be on sys.path for tests.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# Provide stable test defaults before application modules are imported.
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault(
    "FATF_COUNTRY_LIST_PATH",
    str(BACKEND_DIR / "data" / "fatf_high_risk_countries.json"),
)

