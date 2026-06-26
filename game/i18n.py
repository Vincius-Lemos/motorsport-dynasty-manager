"""
Sistema de internacionalização (i18n) — PT-BR · EN-US · DE-DE
Uso:
    from game.i18n import t, set_language
    set_language("en_US")
    label = t("menu.new_driver")           # → "DRIVER CAREER"
    msg   = t("offer.years", n=2)          # → "2 year(s)"
"""
import json, os

_LANG    = "pt_BR"
_STRINGS: dict = {}

LANG_NAMES = {
    "pt_BR": "PT-BR",
    "en_US": "EN-US",
    "de_DE": "DE",
}

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "lang")


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = str(v)
    return out


def set_language(lang: str) -> bool:
    global _LANG, _STRINGS
    path = os.path.join(_DATA_DIR, f"{lang}.json")
    try:
        with open(path, encoding="utf-8") as f:
            _STRINGS = _flatten(json.load(f))
        _LANG = lang
        return True
    except Exception:
        return False


def t(key: str, _fallback: str = "", **kwargs) -> str:
    s = _STRINGS.get(key, _fallback or key)
    if kwargs:
        try:
            s = s.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            pass
    return s


def current_language() -> str:
    return _LANG


def available_languages() -> list:
    return list(LANG_NAMES.keys())
