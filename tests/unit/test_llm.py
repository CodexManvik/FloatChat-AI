import json

import pytest

from floatchat import config, llm


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None, lines=None):
        self.status_code, self.headers = status, headers or {}
        self._body, self._lines = body or {}, lines or []
        self.ok = status < 400

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body

    def iter_lines(self, decode_unicode=True):
        yield from self._lines

    def close(self):
        pass


def reply(text):
    return FakeResponse(body={"choices": [{"message": {"content": text}}]})


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setattr(config, "LLM_MODEL", "test-model")
    monkeypatch.setattr(config, "LLM_API_KEY", "key")


def install(monkeypatch, responses):
    sent, waits = [], []

    def post(url, json=None, headers=None, timeout=None, stream=False):
        sent.append(json)
        return responses.pop(0)

    monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.setattr(llm, "_sleep", waits.append)
    return sent, waits


def test_json_mode_sets_response_format(monkeypatch):
    sent, _ = install(monkeypatch, [reply('{"a": 1}')])
    assert llm.chat("q", json_mode=True) == '{"a": 1}'
    assert sent[0]["response_format"] == {"type": "json_object"}


def test_rate_limit_is_retried_once_honouring_retry_after(monkeypatch):
    sent, waits = install(monkeypatch, [FakeResponse(429, headers={"retry-after": "3"}), reply("ok")])
    assert llm.chat("q") == "ok"
    assert len(sent) == 2 and waits == [3.0]


def test_retry_after_is_capped_and_second_429_gives_up(monkeypatch):
    _, waits = install(monkeypatch, [FakeResponse(429, headers={"retry-after": "120"}), FakeResponse(429)])
    assert llm.chat("q") is None
    assert waits == [10.0]


def test_stream_yields_tokens(monkeypatch):
    chunk = lambda text: "data: " + json.dumps({"choices": [{"delta": {"content": text}}]})  # noqa: E731
    lines = [chunk("Hel"), "", chunk("lo"), "data: [DONE]"]
    sent, _ = install(monkeypatch, [FakeResponse(lines=lines)])
    assert "".join(llm.chat_stream("q")) == "Hello"
    assert sent[0]["stream"] is True


def test_stream_decodes_utf8_bytes(monkeypatch):
    # Event streams usually carry no charset; the bytes must still be read as UTF-8
    text = "O₂ minimum 0.8 µmol/kg"
    line = ("data: " + json.dumps({"choices": [{"delta": {"content": text}}]}, ensure_ascii=False)).encode("utf-8")
    install(monkeypatch, [FakeResponse(lines=[line, b"data: [DONE]"])])
    assert "".join(llm.chat_stream("q")) == text


def test_stream_yields_nothing_without_an_llm(monkeypatch):
    monkeypatch.setattr(config, "LLM_BASE_URL", "")
    assert list(llm.chat_stream("q")) == []
