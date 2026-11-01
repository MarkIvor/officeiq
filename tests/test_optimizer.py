from optimizer import SYNTH_SYSTEM, build_synth_messages, collect_fixes, strip_fences


def test_strip_fences_removes_tagged_fence():
    assert strip_fences("```text\nhello world\n```") == "hello world"
    assert strip_fences("```\nplain fence\n```") == "plain fence"
    assert strip_fences("```python\nx = 1\n```") == "x = 1"


def test_strip_fences_removes_fence_without_closing():
    assert strip_fences("```python\nx = 1") == "x = 1"


def test_strip_fences_plain_text_unchanged():
    assert strip_fences("  hello  ") == "hello"
    assert strip_fences("multi\nline\ntext") == "multi\nline\ntext"


def test_strip_fences_empty_and_none():
    assert strip_fences("") == ""
    assert strip_fences(None) == ""


def test_collect_fixes_dedups_case_insensitive():
    run = {
        "summary": {"prompt_fixes": {"ethics": ["Be stricter", "be stricter"]}},
        "items": [{"category": "ethics", "prompt_fix": "BE STRICTER"}],
    }
    fixes = collect_fixes(run)
    assert len(fixes) == 1
    assert fixes[0] == {"category": "ethics", "fix": "Be stricter"}


def test_collect_fixes_from_summary_and_items():
    run = {
        "summary": {"prompt_fixes": {"ethics": ["fix one"], "communication": ["fix two"]}},
        "items": [
            {"category": "documents", "prompt_fix": "fix three"},
            {"category": "documents", "prompt_fix": ""},
            {"category": "documents"},
        ],
    }
    fixes = collect_fixes(run)
    assert [(f["category"], f["fix"]) for f in fixes] == [
        ("ethics", "fix one"),
        ("communication", "fix two"),
        ("documents", "fix three"),
    ]


def test_collect_fixes_caps_at_15():
    run = {
        "summary": {"prompt_fixes": {"ethics": [f"fix number {i}" for i in range(20)]}},
        "items": [],
    }
    fixes = collect_fixes(run)
    assert len(fixes) == 15
    assert fixes[0]["fix"] == "fix number 0"
    assert fixes[-1]["fix"] == "fix number 14"


def test_collect_fixes_empty_run():
    assert collect_fixes({}) == []
    assert collect_fixes({"summary": {}, "items": []}) == []


def test_build_synth_messages_ru():
    fixes = [{"category": "ethics", "fix": "Be stricter about refusals"}]
    messages = build_synth_messages("CURRENT PROMPT", fixes, lang="ru")
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYNTH_SYSTEM["ru"]
    assert messages[1]["role"] == "user"
    assert "CURRENT PROMPT" in messages[1]["content"]
    assert "Be stricter about refusals" in messages[1]["content"]
    assert "ethics" in messages[1]["content"]


def test_build_synth_messages_en():
    fixes = [{"category": "ethics", "fix": "Be stricter"}]
    messages = build_synth_messages("CURRENT PROMPT", fixes, lang="en")
    assert messages[0]["content"] == SYNTH_SYSTEM["en"]
    assert "CURRENT PROMPT" in messages[1]["content"]


def test_build_synth_messages_defaults_to_ru():
    messages = build_synth_messages("P", [{"category": "ethics", "fix": "F"}], lang="de")
    assert messages[0]["content"] == SYNTH_SYSTEM["ru"]


def test_build_synth_messages_without_fixes():
    messages = build_synth_messages("P", [])
    assert len(messages) == 2
    assert messages[1]["content"]
