import json
from types import SimpleNamespace

import pytest

from editor_app import claude
from editor_app.errors import UserError


def test_key_format_checked_before_network(monkeypatch, tmp_path):
    monkeypatch.setattr(claude, "ENV_FILE", tmp_path / ".env")
    with pytest.raises(UserError) as e:
        claude.save_key("hallo")
    assert "sk-ant-" in str(e.value)


def test_key_saved_to_env_file(monkeypatch, tmp_path):
    monkeypatch.setattr(claude, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(claude, "_check", lambda key: None)
    monkeypatch.delenv(claude.KEY_NAME, raising=False)
    claude.save_key("sk-ant-api03-" + "a" * 30 + "WXYZ")
    assert (tmp_path / ".env").read_text().startswith(claude.KEY_NAME + "=sk-ant-")
    assert claude.available() and claude.masked().endswith("WXYZ")
    claude.delete_key()
    assert not claude.available()


def test_ask_json_reads_structured_answer(monkeypatch):
    answer = {"scenes": ["A"], "caption": "c", "hashtags": ["#a"], "cover_text": "x", "shorts_title": "t"}
    resp = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(answer))])
    monkeypatch.setattr(claude, "_create", lambda **kw: resp)
    assert claude.ask_json("p", claude.REEL_SCHEMA) == answer


def test_refusal_is_explained(monkeypatch):
    resp = SimpleNamespace(stop_reason="refusal", content=[])
    monkeypatch.setattr(claude, "_create", lambda **kw: resp)
    with pytest.raises(UserError):
        claude.ask_json("p", claude.REEL_SCHEMA)


def test_schemas_are_strict():
    for sch in (claude.REEL_SCHEMA, claude.YOUTUBE_SCHEMA):
        assert sch["additionalProperties"] is False and set(sch["required"]) == set(sch["properties"])
