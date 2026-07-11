#!/bin/bash
set -euo pipefail

cd /root/github_trending_daily
today=$(date +%Y-%m-%d)
mkdir -p files/${today}

export PATH="$HOME/.local/bin:$PATH"

python3 generate_trending_daily.py
text_file="files/${today}/github_trending_${today}.txt"

echo "📺 发送 Telegram..."
/root/.local/bin/hermes send --to "telegram:-1004357190196" --file "$text_file" || echo "❌ Telegram 发送失败"

echo "🎉 GitHub Trending 日报发送完成！"
