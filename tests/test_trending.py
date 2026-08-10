# -*- coding: utf-8 -*-
"""github_trending_daily 核心逻辑测试：star 格式化、消息构建"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_trending import format_stars, build_message


class TestFormatStars:
    """star 数格式化测试"""

    def test_plain_number(self):
        assert format_stars("500") == "500"

    def test_thousands(self):
        assert format_stars("1500") == "1.5k"

    def test_ten_thousands(self):
        assert format_stars("12000") == "1.2万"

    def test_hundred_thousands(self):
        assert format_stars("100000") == "10.0万"

    def test_with_commas(self):
        assert format_stars("12,345") == "1.2万"

    def test_invalid_input(self):
        assert format_stars("N/A") == "N/A"

    def test_zero(self):
        assert format_stars("0") == "0"


class TestBuildMessage:
    """trending 日报消息构建测试"""

    def test_empty_repos(self):
        msg = build_message([], since="daily")
        assert "GitHub" in msg or "Trending" in msg or "趋势" in msg

    def test_with_repos(self):
        repos = [
            {"name": "owner/project", "description": "测试项目", "total_stars": "1234",
             "today_stars": "12", "language": "Python",
             "url": "https://github.com/owner/project"},
        ]
        msg = build_message(repos, since="daily")
        assert "owner/project" in msg
        assert "测试项目" in msg
        assert "今日" in msg

    def test_with_translations(self):
        repos = [
            {"name": "owner/project", "description": "desc", "total_stars": "500",
             "today_stars": "5", "language": "Go",
             "url": "https://github.com/owner/project"},
        ]
        msg = build_message(repos, since="weekly", translations={"owner/project": {"cn_desc": "中文描述", "comment": "点评"}})
        assert "中文描述" in msg
        assert "点评" in msg
        assert "本周" in msg
