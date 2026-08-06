#!/usr/bin/env python3
"""GitHub Trending 中文翻译模块 — 用 OpenCode Zen (longcat) 把英文描述
批量翻译为流畅中文，并生成一句话中文点评。

复用 stock_daily/anime_daily 验证过的 LLM 链路：
- requests（urllib 会被 Cloudflare 拦截）
- content 为空时降级 reasoning_content
- 失败时返回 None，由调用方回退到关键词替换（不中断推送）
"""
import json
import os
import re
import requests
from pathlib import Path


def load_zen_key():
    for p in [Path("/root/.hermes/.env"), Path(__file__).resolve().parent / ".env"]:
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("OPENCODE_ZEN_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("OPENCODE_ZEN_API_KEY", "")


def _call_zen(prompt, max_tokens=3000):
    key = load_zen_key()
    if not key:
        raise RuntimeError("缺少 OPENCODE_ZEN_API_KEY")
    payload = {
        "model": "longcat-2.0-free",
        "messages": [
            {"role": "system", "content": "你是专业的 GitHub 开源项目中文翻译与点评助手，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(
        "https://opencode.ai/zen/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=300,
    )
    r.raise_for_status()
    msg = (r.json().get("choices") or [{}])[0].get("message", {}) or {}
    content = (msg.get("content") or "").strip()
    if not content:
        content = (msg.get("reasoning_content") or "").strip()
    # 从 markdown 包裹中提取 JSON
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if m:
        content = m.group(1)
    return json.loads(content)


def translate_repos(repos, top_n=15):
    """批量翻译 repo 描述，返回 {name: {cn_desc, comment}}（按 repo full_name 关联，避免排序错位）。
    """
    if not repos:
        return {}
    key = load_zen_key()
    if not key:
        return {}
    items = repos[:top_n]
    lines = []
    for i, r in enumerate(items):
        lang = r.get("language") or ""
        desc = (r.get("description") or "").strip()
        # 中文可直接跳过翻译（保留原文语义，只补齐点评）
        has_cn = bool(re.search(r"[\u4e00-\u9fff]", desc))
        lines.append(
            f'{i}. name={r.get("name")}\n'
            f'   language={lang}\n'
            f'   description={"（已是中文）" if has_cn else (desc[:200] or "无")}'
        )
    prompt = (
        "下面是一批 GitHub 热门仓库。对每个仓库输出：\n"
        "  \"cn_desc\": 描述的中文翻译（若已是中文则原样返回；若描述为空/太口语，用一句话概括该仓库用途）\n"
        "  \"comment\": 一句话中文点评（技术向、给出价值/亮点，10-25字）\n"
        "严格按编号输出 JSON 对象 {\"0\": {\"cn_desc\":\"..\",\"comment\":\"..\"}, \"1\": {...}, ...}。\n\n"
        f"{chr(10).join(lines)}"
    )
    try:
        result = _call_zen(prompt)
        if not isinstance(result, dict):
            return {}
        # 规范化：可能是 {"0": {...}} 或 {"repos": [...]}
        if "repos" in result and isinstance(result["repos"], dict):
            result = result["repos"]
        out = {}
        for k, v in result.items():
            try:
                idx = int(k)
            except (TypeError, ValueError):
                continue
            if isinstance(v, dict) and 0 <= idx < len(items):
                out[items[idx]["name"]] = {
                    "cn_desc": v.get("cn_desc") or "",
                    "comment": v.get("comment") or "",
                }
        return out
    except Exception as e:
        print(f"[translator] LLM 翻译失败: {e}", file=__import__("sys").stderr)
        return {}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from github_trending import fetch_trending_scrape
    repos = fetch_trending_scrape()
    t = translate_repos(repos)
    print(json.dumps(t, ensure_ascii=False, indent=2))