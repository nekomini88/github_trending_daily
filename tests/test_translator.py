# -*- coding: utf-8 -*-
"""translator.py 纯函数测试：key 加载、_call_zen 响应解析、translate_repos 映射"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import translator
from translator import load_zen_key, translate_repos, _call_zen


class NoEnvFile:
    """mock pathlib.Path：所有路径都不存在（不走 .env 文件，只看环境变量）"""

    def __init__(self, p):
        self.p = str(p)

    def exists(self):
        return False

    def read_text(self, *a, **k):
        raise AssertionError("不应读取不存在的文件")

    def resolve(self):
        return self

    @property
    def parent(self):
        return self

    def __truediv__(self, other):
        return NoEnvFile(f"{self.p}/{other}")


class EnvFile:
    """mock pathlib.Path：.env 文件存在，内容由 CONTENT 控制"""

    CONTENT = 'OPENCODE_ZEN_API_KEY="file-key"\n'

    def __init__(self, p):
        self.p = str(p)

    def exists(self):
        return ".env" in self.p

    def read_text(self, encoding="utf-8", errors="ignore"):
        return self.CONTENT

    def resolve(self):
        return self

    @property
    def parent(self):
        return self

    def __truediv__(self, other):
        return EnvFile(f"{self.p}/{other}")


class TestLoadZenKey:
    """OPENCODE_ZEN_API_KEY 加载：.env 文件优先，其次环境变量"""

    def test_no_key_anywhere(self, monkeypatch):
        monkeypatch.setattr(translator, "Path", NoEnvFile)
        monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
        assert load_zen_key() == ""

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setattr(translator, "Path", NoEnvFile)
        monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "env-key-123")
        assert load_zen_key() == "env-key-123"

    def test_env_file_quoted_value_wins(self, monkeypatch):
        monkeypatch.setattr(translator, "Path", EnvFile)
        monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "env-key-123")
        assert load_zen_key() == "file-key"

    def test_env_file_unquoted_value(self, monkeypatch):
        monkeypatch.setattr(translator, "Path", EnvFile)
        monkeypatch.setattr(EnvFile, "CONTENT", 'OPENCODE_ZEN_API_KEY=plain-key\n')
        monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
        assert load_zen_key() == "plain-key"


class FakeResp:
    """mock requests.Response"""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class TestCallZen:
    """_call_zen：请求构造 + 响应解析（markdown 包裹 / reasoning 降级）"""

    def _patch_post(self, monkeypatch, payload):
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers
            return FakeResp(payload)

        monkeypatch.setattr(translator, "load_zen_key", lambda: "test-key")
        monkeypatch.setattr(translator.requests, "post", fake_post)
        return captured

    def test_normal_content(self, monkeypatch):
        captured = self._patch_post(
            monkeypatch, {"choices": [{"message": {"content": '{"0": {"cn_desc": "中文"}}'}}]})
        assert _call_zen("hi") == {"0": {"cn_desc": "中文"}}
        assert captured["url"] == "https://opencode.ai/zen/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["payload"]["model"] == "longcat-2.0-free"
        assert captured["payload"]["response_format"] == {"type": "json_object"}

    def test_markdown_fence_extracted(self, monkeypatch):
        self._patch_post(
            monkeypatch, {"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]})
        assert _call_zen("hi") == {"a": 1}

    def test_reasoning_content_fallback(self, monkeypatch):
        self._patch_post(
            monkeypatch, {"choices": [{"message": {"content": "", "reasoning_content": '{"b": 2}'}}]})
        assert _call_zen("hi") == {"b": 2}

    def test_http_error_propagates(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(translator, "load_zen_key", lambda: "test-key")
        monkeypatch.setattr(translator.requests, "post", boom)
        with pytest.raises(RuntimeError):
            _call_zen("hi")

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.setattr(translator, "load_zen_key", lambda: "")
        with pytest.raises(RuntimeError, match="OPENCODE_ZEN_API_KEY"):
            _call_zen("hi")


class TestTranslateRepos:
    """translate_repos：按编号映射回 repo full_name，异常时安全返回 {}"""

    def test_empty_repos(self, monkeypatch):
        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")
        assert translate_repos([]) == {}

    def test_no_key_returns_empty(self, monkeypatch):
        monkeypatch.setattr(translator, "load_zen_key", lambda: "")
        assert translate_repos([{"name": "a/b"}]) == {}

    def test_mapping_by_name(self, monkeypatch):
        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")
        repos = [
            {"name": "a/b", "description": "d1", "language": "Python"},
            {"name": "c/d", "description": "d2", "language": "Go"},
        ]
        monkeypatch.setattr(translator, "_call_zen", lambda prompt, max_tokens=3000: {
            "0": {"cn_desc": "中文一", "comment": "点评一"},
            "1": {"cn_desc": "中文二", "comment": "点评二"},
        })
        assert translate_repos(repos) == {
            "a/b": {"cn_desc": "中文一", "comment": "点评一"},
            "c/d": {"cn_desc": "中文二", "comment": "点评二"},
        }

    def test_repos_wrapped_format(self, monkeypatch):
        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")
        monkeypatch.setattr(translator, "_call_zen", lambda prompt, max_tokens=3000: {
            "repos": {"0": {"cn_desc": "x", "comment": "y"}}})
        assert translate_repos([{"name": "a/b", "description": "d", "language": ""}]) == {
            "a/b": {"cn_desc": "x", "comment": "y"}}

    def test_invalid_keys_skipped(self, monkeypatch):
        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")
        monkeypatch.setattr(translator, "_call_zen", lambda prompt, max_tokens=3000: {
            "bad": {"cn_desc": "x"},      # 非数字 key
            "2": {"cn_desc": "x"},        # 越界 index
            "0": "not-a-dict",            # 非 dict 值
        })
        assert translate_repos([{"name": "a/b", "description": "d", "language": ""}]) == {}

    def test_missing_fields_default_empty(self, monkeypatch):
        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")
        monkeypatch.setattr(translator, "_call_zen", lambda prompt, max_tokens=3000: {
            "0": {"cn_desc": "只有描述"}})
        assert translate_repos([{"name": "a/b", "description": "d", "language": ""}]) == {
            "a/b": {"cn_desc": "只有描述", "comment": ""}}

    def test_llm_failure_returns_empty(self, monkeypatch):
        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")

        def boom(prompt, max_tokens=3000):
            raise Exception("LLM down")

        monkeypatch.setattr(translator, "_call_zen", boom)
        assert translate_repos([{"name": "a/b", "description": "d", "language": ""}]) == {}

    def test_top_n_limits_prompt(self, monkeypatch):
        captured = {}

        def fake_zen(prompt, max_tokens=3000):
            captured["prompt"] = prompt
            return {}

        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")
        monkeypatch.setattr(translator, "_call_zen", fake_zen)
        repos = [{"name": f"o{i}/r{i}", "description": f"desc {i}", "language": ""} for i in range(5)]
        translate_repos(repos, top_n=2)
        assert "o0/r0" in captured["prompt"]
        assert "o1/r1" in captured["prompt"]
        assert "o2/r2" not in captured["prompt"]

    def test_chinese_desc_marked(self, monkeypatch):
        captured = {}

        def fake_zen(prompt, max_tokens=3000):
            captured["prompt"] = prompt
            return {}

        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")
        monkeypatch.setattr(translator, "_call_zen", fake_zen)
        translate_repos([{"name": "a/b", "description": "一个中文描述", "language": "Python"}])
        assert "（已是中文）" in captured["prompt"]
        assert "一个中文描述" not in captured["prompt"]

    def test_english_desc_included(self, monkeypatch):
        captured = {}

        def fake_zen(prompt, max_tokens=3000):
            captured["prompt"] = prompt
            return {}

        monkeypatch.setattr(translator, "load_zen_key", lambda: "k")
        monkeypatch.setattr(translator, "_call_zen", fake_zen)
        translate_repos([{"name": "a/b", "description": "An English description", "language": "Go"}])
        assert "An English description" in captured["prompt"]
        assert "（已是中文）" not in captured["prompt"]
