# -*- coding: utf-8 -*-
"""github_trending.py 补强测试：translate_desc 关键词翻译、语言映射、
format_stars 边界、build_message 排序/翻译优先级"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_trending import (
    translate_desc, LANG_CN, format_stars, build_message,
)


class TestTranslateDesc:
    """描述关键词替换翻译：中文保留、实体还原、最长优先、s 尾清理"""

    def test_empty(self):
        assert translate_desc("") == ""
        assert translate_desc(None) == ""

    def test_chinese_kept_entities_fixed(self):
        assert translate_desc("这是一个 &amp; 测试") == "这是一个 & 测试"

    def test_keyword_replacement(self):
        assert translate_desc("machine learning framework") == "机器学习 框架"

    def test_longest_first(self):
        # "artificial intelligence" 必须先于 "AI" 匹配（按长度降序替换）
        assert translate_desc("artificial intelligence") == "人工智能"
        assert translate_desc("AI agent") == "AI 智能体"

    def test_trailing_s_cleaned(self):
        assert translate_desc("machine learning frameworks") == "机器学习 框架"

    def test_html_entities(self):
        assert translate_desc("C++ &amp; Rust") == "C++ & Rust"

    def test_self_hosted_open_source_chatbot(self):
        assert translate_desc("self-hosted open source chatbot") == "自托管 开源 聊天机器人"


class TestLangCn:
    """语言中文映射表"""

    def test_common_mappings(self):
        assert LANG_CN["R"] == "R语言"
        assert LANG_CN["Assembly"] == "汇编"
        assert LANG_CN["Vim Script"] == "Vim"
        assert LANG_CN["Jupyter Notebook"] == "Jupyter"
        assert LANG_CN["Objective-C"] == "OC"
        assert LANG_CN["Python"] == "Python"

    def test_unknown_language_fallback(self):
        assert LANG_CN.get("Klingon", "Klingon") == "Klingon"


class TestFormatStarsEdge:
    """format_stars 边界补充"""

    def test_millions_with_commas(self):
        assert format_stars("12,345,678") == "1234.6万"

    def test_rounding_boundary(self):
        assert format_stars("9999") == "10.0k"

    def test_below_thousand(self):
        assert format_stars("999") == "999"

    def test_empty_string(self):
        assert format_stars("") == ""


REPOS_TWO = [
    {"name": "low/star", "description": "低热度", "total_stars": "500",
     "today_stars": "5", "language": "R", "url": "https://github.com/low/star"},
    {"name": "high/star", "description": "高热度", "total_stars": "20000",
     "today_stars": "300", "language": "Klingon", "url": "https://github.com/high/star"},
]


class TestBuildMessageMore:
    """build_message 补充：排序、语言标签、周期、翻译优先级"""

    def test_sorted_by_today_stars(self):
        msg = build_message(REPOS_TWO, since="daily")
        assert "1. high/star" in msg
        assert "2. low/star" in msg
        assert msg.index("1. high/star") < msg.index("2. low/star")

    def test_lang_mapping_and_unknown(self):
        msg = build_message(REPOS_TWO)
        assert "「R语言」" in msg
        assert "「Klingon」" in msg

    def test_monthly_label(self):
        msg = build_message([], since="monthly")
        assert "本月榜" in msg

    def test_star_line_with_today(self):
        msg = build_message(REPOS_TWO)
        assert "⭐ 2.0万" in msg
        assert "📈 +300 今日" in msg
        assert "📈 +5 今日" in msg

    def test_zero_today_no_increase(self):
        repos = [{"name": "a/b", "description": "d", "total_stars": "100",
                  "today_stars": "0", "language": "", "url": "https://github.com/a/b"}]
        assert "📈" not in build_message(repos)

    def test_empty_today_no_increase(self):
        repos = [{"name": "a/b", "description": "d", "total_stars": "100",
                  "today_stars": "", "language": "", "url": "https://github.com/a/b"}]
        assert "📈" not in build_message(repos)

    def test_over_20_repos_shows_total(self):
        repos = [
            {"name": f"o{i}/r{i}", "description": f"d{i}", "total_stars": "10",
             "today_stars": "0", "language": "", "url": f"https://github.com/o{i}/r{i}"}
            for i in range(25)
        ]
        assert "... 共 25 个项目" in build_message(repos)

    def test_llm_translation_priority(self):
        repos = [{"name": "a/b", "description": "raw english desc", "total_stars": "100",
                  "today_stars": "0", "language": "Go", "url": "https://github.com/a/b"}]
        msg = build_message(repos, translations={"a/b": {"cn_desc": "LLM中文描述", "comment": "LLM点评"}})
        assert "LLM中文描述" in msg
        assert "LLM点评" in msg
        assert "raw english" not in msg

    def test_empty_translation_falls_back_to_keyword(self):
        repos = [{"name": "a/b", "description": "open source framework", "total_stars": "100",
                  "today_stars": "0", "language": "Go", "url": "https://github.com/a/b"}]
        msg = build_message(repos, translations={"a/b": {}})
        assert "开源" in msg
        assert "💡" not in msg

    def test_html_entities_unescaped_in_message(self):
        repos = [{"name": "a/b", "description": "C++ &amp; Rust bindings", "total_stars": "100",
                  "today_stars": "0", "language": "", "url": "https://github.com/a/b"}]
        assert "C++ & Rust" in build_message(repos)
