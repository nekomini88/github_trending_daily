#!/usr/bin/env python3
"""
GitHub Trending 日报 — 生成文本并由 crontab + hermes 发送
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from github_trending import fetch_trending_scrape, fetch_trending_via_search, enrich_with_api, build_message


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = BASE_DIR / "files" / today
    out_dir.mkdir(parents=True, exist_ok=True)

    repos = fetch_trending_scrape()
    if repos:
        repos = enrich_with_api(repos)
    else:
        repos = fetch_trending_via_search()

    msg = build_message(repos, since="daily")

    text_path = out_dir / f"github_trending_{today}.txt"
    text_path.write_text(msg, encoding="utf-8")
    print(f"✅ 日报已生成: {text_path}")
    print(msg)


if __name__ == "__main__":
    main()
