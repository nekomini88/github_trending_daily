# GitHub Trending 日报

独立 Telegram 项目，抓取 GitHub 每日热门项目并推送。

## 目录

- `generate_trending_daily.py`：主脚本，抓取并生成日报文本
- `github_trending.py`：抓取 + 翻译逻辑
- `trending_daily.sh`：cron 入口，生成文本后由 `hermes send` 推送
- `config.ini`：私密配置，写入 `.gitignore`，不提交

## 本地运行

```bash
bash trending_daily.sh
```

## 调度

使用系统 crontab，每天 9:00 执行 `trending_daily.sh`。

```bash
0 9 * * * cd /root/github_trending_daily && bash trending_daily.sh >> /root/github_trending_daily/cron.log 2>&1
```
