import re
from pathlib import Path

import pytest

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
I18N_JS = UI_DIR / "js" / "i18n.js"


def _extract_block(text, name):
    match = re.search(rf"\b{name}\s*:\s*\{{", text)
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return None


def _keys(block):
    return set(re.findall(r"[\w.-]+(?=\s*:)", block))


@pytest.fixture(scope="module")
def locales():
    if not I18N_JS.exists():
        pytest.skip("i18n.js not written yet")
    text = I18N_JS.read_text(encoding="utf-8")
    ru_block = _extract_block(text, "ru")
    en_block = _extract_block(text, "en")
    if not ru_block or not en_block:
        pytest.skip("i18n.js structure not recognized")
    ru_keys = _keys(ru_block)
    en_keys = _keys(en_block)
    if not ru_keys or not en_keys:
        pytest.skip("i18n.js locales are empty")
    return {"ru": ru_keys, "en": en_keys}


def _i18n_keys_in_html():
    html = (UI_DIR / "index.html").read_text(encoding="utf-8")
    keys = []
    for attr in ("data-i18n", "data-i18n-ph", "data-i18n-title"):
        keys.extend(re.findall(rf'{attr}="([^"]+)"', html))
    return keys


def test_index_html_exists():
    assert (UI_DIR / "index.html").exists()


def test_index_i18n_attributes_defined_in_both_locales(locales):
    keys = _i18n_keys_in_html()
    if not keys:
        pytest.skip("no data-i18n attributes in index.html yet")
    for key in keys:
        assert key in locales["ru"], f"missing ru key: {key}"
        assert key in locales["en"], f"missing en key: {key}"


def test_t_call_literals_defined_in_both_locales(locales):
    js_dir = UI_DIR / "js"
    if not js_dir.exists():
        pytest.skip("ui/js not written yet")
    used = []
    for js_file in js_dir.glob("*.js"):
        used.extend(re.findall(r"\bt\(\s*['\"]([\w.-]+)['\"]", js_file.read_text(encoding="utf-8")))
    if not used:
        pytest.skip("no t() literals found in ui/js")
    for key in used:
        assert key in locales["ru"], f"missing ru key: {key}"
        assert key in locales["en"], f"missing en key: {key}"
