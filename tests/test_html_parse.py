# -*- coding: utf-8 -*-
"""github_trending.parse_trending_html 纯函数测试（离线 HTML fixture，不联网）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_trending import parse_trending_html

# 仿真实 GitHub trending 页面单条 article 结构
ARTICLE_DAILY = """<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/openai/whisper"><span>openai/whisper</span></a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">
    Robust Speech Recognition via Large-Scale Weak Supervision
  </p>
  <div class="f6 color-fg-muted mt-2">
    <a href="/openai/whisper/stargazers" class="Link--muted d-inline-block mr-3">
      <svg aria-hidden="true" class="octicon octicon-star"><path d="M8 .25"></path></svg>
      56,789
    </a>
    <a href="/openai/whisper/forks" class="Link--muted d-inline-block mr-3">
      <svg aria-hidden="true" class="octicon octicon-repo-forked"><path d="M5 5"></path></svg>
      4,321
    </a>
    <span itemprop="programmingLanguage">Python</span>
    <a href="/openai/whisper" class="Link--muted d-inline-block mr-3">
      <svg aria-hidden="true" class="octicon octicon-flame"><path d="M8 14"></path></svg>
      1,234 stars today
    </a>
  </div>
</article>"""


class TestParseTrendingHtml:
    """trending HTML 解析：repo 名 / 描述 / 语言 / star / 周期"""

    def test_empty_html(self):
        assert parse_trending_html("") == []

    def test_no_articles(self):
        assert parse_trending_html("<html><body>nothing here</body></html>") == []

    def test_single_daily_repo(self):
        repos = parse_trending_html(ARTICLE_DAILY)
        assert len(repos) == 1
        r = repos[0]
        assert r["name"] == "openai/whisper"
        assert r["url"] == "https://github.com/openai/whisper"
        assert r["description"] == "Robust Speech Recognition via Large-Scale Weak Supervision"
        assert r["language"] == "Python"
        assert r["total_stars"] == "56789"
        assert r["today_stars"] == "1234"
        assert r["period"] == "今日"

    def test_weekly_period(self):
        html = ARTICLE_DAILY.replace("1,234 stars today", "2,345 stars this week")
        r = parse_trending_html(html)[0]
        assert r["period"] == "本周"
        assert r["today_stars"] == "2345"

    def test_monthly_period(self):
        html = ARTICLE_DAILY.replace("1,234 stars today", "999 stars this month")
        r = parse_trending_html(html)[0]
        assert r["period"] == "本月"
        assert r["today_stars"] == "999"

    def test_multiple_articles(self):
        html = ARTICLE_DAILY + "\n" + ARTICLE_DAILY.replace("openai/whisper", "rust-lang/rust").replace("Python", "Rust")
        repos = parse_trending_html(html)
        assert len(repos) == 2
        assert [r["name"] for r in repos] == ["openai/whisper", "rust-lang/rust"]

    def test_login_link_skipped(self):
        html = """<article class="Box-row">
          <h2 class="h3 lh-condensed"><a href="/login">Sign in</a></h2>
        </article>"""
        assert parse_trending_html(html) == []

    def test_no_stargazers_fallback_to_numbers(self):
        html = """<article class="Box-row">
          <h2 class="h3 lh-condensed"><a href="/owner/legacy">owner/legacy</a></h2>
          <p class="col-9 color-fg-muted my-1 pr-4">Old repo</p>
          <span itemprop="programmingLanguage">Go</span>
          <div class="f6 color-fg-muted mt-2"><span>999</span></div>
        </article>"""
        repos = parse_trending_html(html)
        assert len(repos) == 1
        assert repos[0]["total_stars"] == "999"
        assert repos[0]["today_stars"] == ""
        assert repos[0]["period"] == "今日"

    def test_no_stars_no_language(self):
        html = """<article class="Box-row">
          <h2 class="h3 lh-condensed"><a href="/a/b">a/b</a></h2>
          <p class="col-9 color-fg-muted my-1 pr-4">No meta</p>
        </article>"""
        r = parse_trending_html(html)[0]
        assert r["total_stars"] == "0"
        assert r["language"] == ""
        assert r["today_stars"] == ""

    def test_description_tags_stripped(self):
        html = ARTICLE_DAILY.replace(
            "Robust Speech Recognition via Large-Scale Weak Supervision",
            "A <code>fast</code> &amp; <strong>tiny</strong> library")
        assert parse_trending_html(html)[0]["description"] == "A fast &amp; tiny library"

    def test_description_truncated_at_120(self):
        long_text = ("word " * 40).strip()
        html = ARTICLE_DAILY.replace(
            "Robust Speech Recognition via Large-Scale Weak Supervision", long_text)
        desc = parse_trending_html(html)[0]["description"]
        assert len(desc) == 120
        assert desc.endswith("...")

    def test_max_25_articles(self):
        html = "".join(
            ARTICLE_DAILY.replace("openai/whisper", f"owner/repo{i}") for i in range(30))
        repos = parse_trending_html(html)
        assert len(repos) == 25
