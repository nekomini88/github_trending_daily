#!/usr/bin/env python3
"""
GitHub Trending 日报 — 生成文本并由 crontab + hermes 发送
流程: 抓取(scrape) → enrich(API补stars) → LLM中文翻译+点评(失败自动回退关键词替换)
"""
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from github_trending import (
    fetch_trending_scrape, fetch_trending_via_search,
    enrich_with_api, build_message,
)
from translator import translate_repos


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = BASE_DIR / "files" / today
    out_dir.mkdir(parents=True, exist_ok=True)

    repos = fetch_trending_scrape()
    if repos:
        repos = enrich_with_api(repos)
    else:
        repos = fetch_trending_via_search()

    # LLM 中文翻译+点评（失败返回 {}，build_message 自动回退）
    translations = translate_repos(repos, top_n=15)

    msg = build_message(repos, since="daily", translations=translations)

    text_path = out_dir / f"github_trending_{today}.txt"
    text_path.write_text(msg, encoding="utf-8")
    print(f"✅ 日报已生成: {text_path}")
    print(msg)


if __name__ == "__main__":
    main()