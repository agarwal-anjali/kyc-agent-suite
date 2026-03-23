from __future__ import annotations

import json

import pytest

from core.config import Settings


def test_load_fatf_countries_returns_sets(tmp_path):
    fatf_file = tmp_path / "fatf.json"
    fatf_file.write_text(
        json.dumps(
            {
                "blacklist": ["PRK"],
                "greylist": ["MMR", "IRN"],
                "last_updated": "2026-01-01",
            }
        )
    )

    settings = Settings(
        google_api_key="test-key",
        fatf_country_list_path=fatf_file,
        _env_file=None,
    )

    loaded = settings.load_fatf_countries()

    assert loaded["blacklist"] == {"PRK"}
    assert loaded["greylist"] == {"MMR", "IRN"}


def test_load_fatf_countries_requires_expected_keys(tmp_path):
    fatf_file = tmp_path / "fatf.json"
    fatf_file.write_text(json.dumps({"blacklist": ["PRK"]}))

    settings = Settings(
        google_api_key="test-key",
        fatf_country_list_path=fatf_file,
        _env_file=None,
    )

    with pytest.raises(ValueError, match="missing required key"):
        settings.load_fatf_countries()
