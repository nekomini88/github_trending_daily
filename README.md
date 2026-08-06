# 🔥 GitHub Trending 日报 (github_trending_daily)

每日抓取 GitHub 热门项目，用 **LLM 翻译为中文描述**并生成一句话中文点评，推送 Telegram 频道。

> 数据真实性第一：项目来自 GitHub Trending 实时抓取 + Search API 补全 star 数；
> 全中文输出（仓库名保留原文），无硬编码/伪造数据。

---

## 🏗 架构

```text
GitHub Trending 页 ──► fetch_trending_scrape()（抓取，fallback）
        │
        ▼
repos（name/description/language/today_stars）
        │
        ▼
enrich_with_api() → Search API 补全 total_stars（scrape 提取的 star 常为 0）
        │
        ▼
translator.translate_repos() → OpenCode Zen LLM
        每条生成 {cn_desc 中文翻译, comment 一句话点评}
        （LLM 失败 → 回退 translate_desc 关键词替换，不中断推送）
        │
        ▼
build_message() → 中文日报 → files/YYYY-MM-DD/ → hermes send → TG 频道 -1004357190196
```

---

## 📁 文件

| 文件 | 职责 |
|------|------|
| `github_trending.py` | 抓取(scrape+search fallback) + enrich star + 中文构建消息 |
| `translator.py` | **LLM 中文翻译模块**（OpenCode Zen longcat，批量翻译+点评） |
| `generate_trending_daily.py` | 主入口：抓取→enrich→翻译→生成日报文本 |
| `trending_daily.sh` | cron 入口：生成 + hermes send 推送 |
| `config.ini(.example)` | 私密配置（gitignored） |

---

## 🚀 运行

```bash
bash trending_daily.sh                     # 完整：生成 + 推送
python3 generate_trending_daily.py         # 仅生成文本
python3 github_trending.py                 # 仅测抓取+翻译
```

---

## ⏰ 调度

系统 crontab，每天 **9:00**：

```bash
0 9 * * * cd /root/github_trending_daily && bash trending_daily.sh >> /root/github_trending_daily/cron.log 2>&1
```

目标频道：`-1004357190196`（hermes send）

---

## 📄 输出示例

```text
🔥 GitHub 热门项目 · 今日榜 🔥
📅 2026-08-06 08:00

1. cloudflare/computer 「TypeScript」
   📝 为你的 AI Agent 提供一台虚拟计算机 👾
   💡 让 Agent 拥有独立沙箱环境，实现真正的自主操作能力
   ⭐ 2949  📈 +891 今日
   🔗 https://github.com/cloudflare/computer

2. uber/ADR 「Python」
   📝 ADR 通过可观测性、安全基准测试和威胁检测来保护企业 AI 智能体
   💡 企业级智能体安全防护与监控方案
   ⭐ 1.0k  📈 +354 今日
   🔗 https://github.com/uber/ADR
...
🌐 https://github.com/trending
```

---

## 🤖 LLM 中文翻译

- **Endpoint**：`https://opencode.ai/zen/v1/chat/completions`
- **Model**：`longcat-2.0-free`
- **Key**：`OPENCODE_ZEN_API_KEY`（`/root/.hermes/.env`）
- 必须用 `requests`（urllib 会被 Cloudflare 拦截）
- `response_format=json_object`，content 空时降级 `reasoning_content`
- 批量 15 条一次翻译（desc 中文翻译 + 一句话点评）

## ⚠️ 容错设计

- LLM 失败 → 回退原有关键词替换翻译（`translate_desc`），**推送不中断**
- GitHub Trending 抓取失败 → 回退 Search API（`fetch_trending_via_search`）
- **翻译按 repo full_name 关联**（不是索引）——避免 build_message 按今日 star 排序后描述错位（修复记录见下）

## ⚠️ 已知限制

- 翻译 LLM 每次调用约 5-20s（15 条批量），比纯抓取慢；若 LLM 不可用自动回退
- GitHub API 未认证限 60 req/h，`enrich` 已批量复用 1 次查询
- `github_trending.py` 的 `DESC_CN`/`LANG_CN` 映射保留为 fallback 兜底

## 🔒 隐私

`config.ini` gitignored，不提交 GitHub。