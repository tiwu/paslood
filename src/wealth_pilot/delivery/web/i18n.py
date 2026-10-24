"""Internationalization (i18n) definitions and isolated locale loader for Wealth Pilot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_LANGUAGES = ["en", "nl", "fr", "de"]
DEFAULT_LANGUAGE = "en"

LOCALES_DIR = Path(__file__).resolve().parent / "static" / "locales"


def _load_translations() -> dict[str, dict[str, Any]]:
    """Loads per-language JSON locale files from static/locales/."""
    loaded: dict[str, dict[str, Any]] = {}
    for lang in SUPPORTED_LANGUAGES:
        file_path = LOCALES_DIR / f"{lang}.json"
        if file_path.exists():
            loaded[lang] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            loaded[lang] = {}
    return loaded


TRANSLATIONS: dict[str, dict[str, Any]] = _load_translations()


def get_translations_for_locale(lang: str) -> dict[str, Any]:
    """Returns the translation dictionary for the given language with fallback to English."""
    normalized = (lang or "").lower()[:2]
    return TRANSLATIONS.get(normalized, TRANSLATIONS[DEFAULT_LANGUAGE])
