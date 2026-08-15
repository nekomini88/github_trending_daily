#!/usr/bin/env python3
"""GitHub Trending 抓取 — 每日热门项目（纯API方式）"""
import json
import urllib.request
import urllib.parse
import sys
import re
from datetime import datetime
# 使用 GitHub Search API 模拟 trending（按 stars 排序近期创建/更新的仓库）
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories?q=created:>{date}+stars:>10&sort=stars&order=desc&per_page=25"

# ---- 常量 ----
MAX_TRENDING_REPOS = 25    # parse_trending_html 最多解析条数
MAX_DESC_LENGTH = 120      # 描述最大长度（超出截断为 117 + "..."）
DESC_ELLIPSIS = "..."      # 描述截断后缀
MAX_MESSAGE_REPOS = 20     # build_message 最多展示条数

# 周期 → 中文（build_message 的 since 参数）
SINCE_CN = {"daily": "今日", "weekly": "本周", "monthly": "本月"}
# 周期 → 中文（trending 页面原始英文文本）
TRENDING_PERIOD_CN = {"today": "今日", "this week": "本周", "this month": "本月"}

# ---- HTML 解析正则 ----
# 仓库链接: /owner/repo（恰好一段斜杠，无多余路径）
REPO_HREF_RE = re.compile(r'href="(/[^/]+/[^/\"]+)"')
# 需要跳过的非仓库链接前缀
SKIP_PATH_PREFIXES = ("/login", "/sponsors", "/settings")
ARTICLE_BLOCK_RE = re.compile(r'<article[^>]*class="Box-row"[^>]*>(.*?)</article>', re.DOTALL)
DESC_P_RE = re.compile(r'<p class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', re.DOTALL)
HTML_TAG_RE = re.compile(r'<[^>]+>')
LANG_P_RE = re.compile(r'<span itemprop="programmingLanguage">(.*?)</span>')
STARGAZERS_RE = re.compile(r'stargazers[^>]*>\s*(?:<[^>]*>)*\s*(\d[\d,]*)')
BIG_NUM_RE = re.compile(r'>(\d[\d,]*)</')
TODAY_STARS_RE = re.compile(r'([\d,]+)\s*stars?\s+(today|this week|this month)')


def fetch_trending_via_search():
    """Use GitHub Search API to find trending repos (recently created, high stars)"""
    from datetime import timedelta
    date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=created:>{date}&sort=stars&order=desc&per_page=25"
    
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.github.v3+json"
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            results = []
            for item in items:
                results.append({
                    "name": item.get("full_name", ""),
                    "url": item.get("html_url", ""),
                    "description": (item.get("description") or "")[:120],
                    "language": item.get("language") or "",
                    "total_stars": str(item.get("stargazers_count", 0)),
                    "today_stars": "0",
                    "period": "本周",
                    "forks": str(item.get("forks_count", 0))
                })
            return results
    except Exception as e:
        print(f"GitHub Search API failed: {e}", file=sys.stderr)
        return []


def fetch_trending_scrape():
    """Scrape GitHub trending page - improved parser"""
    url = "https://github.com/trending?since=daily"
    
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml"
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"Scrape failed: {e}", file=sys.stderr)
        return []

    return parse_trending_html(html)


def _extract_repo_path(block):
    """从 article 块提取 /owner/repo 路径；跳过 login/sponsors/settings 等非仓库链接"""
    for m in REPO_HREF_RE.findall(block):
        # 跳过 /login, /sponsors, /settings 等
        if m.startswith(SKIP_PATH_PREFIXES):
            continue
        # 必须是 owner/repo 格式
        parts = m.strip("/").split("/")
        if len(parts) == 2 and not parts[0].startswith(("login", "sponsors")):
            return m
    return ""


def _parse_description(block):
    """提取仓库描述：去 HTML 标签后截断到 MAX_DESC_LENGTH"""
    desc_match = DESC_P_RE.search(block)
    if not desc_match:
        return ""
    desc = HTML_TAG_RE.sub("", desc_match.group(1)).strip()
    if len(desc) > MAX_DESC_LENGTH:
        desc = desc[:MAX_DESC_LENGTH - len(DESC_ELLIPSIS)] + DESC_ELLIPSIS
    return desc


def _parse_language(block):
    """提取编程语言"""
    lang_match = LANG_P_RE.search(block)
    return lang_match.group(1).strip() if lang_match else ""


def _parse_total_stars(block):
    """提取总 star 数：优先 stargazers 链接，回退块内大数字"""
    star_match = STARGAZERS_RE.search(block)
    if star_match:
        return star_match.group(1).replace(",", "")
    big_nums = BIG_NUM_RE.findall(block)
    return big_nums[0].replace(",", "") if big_nums else "0"


def _parse_today_stars(block):
    """提取今日/本周/本月 star 增量及周期中文标签"""
    today_match = TODAY_STARS_RE.search(block)
    if not today_match:
        return "", "今日"
    return today_match.group(1).replace(",", ""), TRENDING_PERIOD_CN.get(today_match.group(2), "今日")


def parse_trending_html(html):
    """Parse GitHub trending page HTML into repo dicts. 纯函数（不联网）。

    Used by fetch_trending_scrape; extracted so parsing can be unit-tested
    offline with fixture HTML.
    """
    results = []
    for block in ARTICLE_BLOCK_RE.findall(html)[:MAX_TRENDING_REPOS]:
        # Repo name: href="/owner/repo" — must have exactly one slash, no extra path
        repo_path = _extract_repo_path(block)
        if not repo_path:
            continue
        name = repo_path.strip("/")
        today_stars, period = _parse_today_stars(block)
        results.append({
            "name": name,
            "url": f"https://github.com/{name}",
            "description": _parse_description(block),
            "language": _parse_language(block),
            "total_stars": _parse_total_stars(block),
            "today_stars": today_stars,
            "period": period
        })
    return results


def enrich_with_api(repos):
    """Enrich scraped repos with star counts from GitHub API"""
    if not repos:
        return repos
    
    # Batch fetch via search API
    names = [r["name"] for r in repos[:25]]
    query = " ".join(f"repo:{n}" for n in names)
    url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&per_page=25"
    
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.github.v3+json"
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            star_map = {}
            for item in data.get("items", []):
                star_map[item["full_name"]] = str(item.get("stargazers_count", 0))
            
            for repo in repos:
                if repo["name"] in star_map:
                    repo["total_stars"] = star_map[repo["name"]]
            return repos
    except Exception as e:
        print(f"API enrichment failed: {e}", file=sys.stderr)
        return repos


# 语言中文映射
LANG_CN = {
    "Python": "Python", "JavaScript": "JavaScript", "TypeScript": "TypeScript",
    "Java": "Java", "C++": "C++", "C": "C", "C#": "C#", "Go": "Go",
    "Rust": "Rust", "Ruby": "Ruby", "PHP": "PHP", "Swift": "Swift",
    "Kotlin": "Kotlin", "Dart": "Dart", "Scala": "Scala", "Haskell": "Haskell",
    "Shell": "Shell", "PowerShell": "PowerShell", "Lua": "Lua",
    "R": "R语言", "Julia": "Julia", "Zig": "Zig", "Elixir": "Elixir",
    "Clojure": "Clojure", "Perl": "Perl", "OCaml": "OCaml",
    "HTML": "HTML", "CSS": "CSS", "Vue": "Vue", "Svelte": "Svelte",
    "Jupyter Notebook": "Jupyter", "Dockerfile": "Dockerfile",
    "Makefile": "Makefile", "Nix": "Nix", "Vim Script": "Vim",
    "Objective-C": "OC", "Fortran": "Fortran", "MATLAB": "MATLAB",
    "Assembly": "汇编", "Solidity": "Solidity", "Swift": "Swift",
}

# 描述关键词中英映射（简单替换）
DESC_CN = {
    "messaging": "通讯", "network": "网络", "private": "隐私",
    "artificial intelligence": "人工智能", "AI": "AI", "machine learning": "机器学习",
    "deep learning": "深度学习", "framework": "框架", "library": "库",
    "operating system": "操作系统", "database": "数据库", "compiler": "编译器",
    "encryption": "加密", "security": "安全", "monitoring": "监控",
    "automation": "自动化", "testing": "测试", "deployment": "部署",
    "authentication": "认证", "authorization": "授权", "infrastructure": "基础设施",
    "orchestration": "编排", "container": "容器", "serverless": "无服务器",
    "blockchain": "区块链", "cryptocurrency": "加密货币", "trading": "交易",
    "analytics": "分析", "visualization": "可视化", "dashboard": "仪表盘",
    "chatbot": "聊天机器人", "agent": "智能体", "workflow": "工作流",
    "desktop app": "桌面应用", "mobile app": "移动应用", "web app": "Web应用",
    "open source": "开源", "self-hosted": "自托管", "cross-platform": "跨平台",
    "command line": "命令行", "CLI": "CLI", "API": "API",
    "GPU": "GPU", "CPU": "CPU", "performance": "性能",
    "real-time": "实时", "offline": "离线", "local": "本地",
}


def _unescape_html_entities(text):
    """还原常见 HTML 实体（&amp;/&lt;/&gt;），空值原样返回"""
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">") if text else ""


def translate_desc(desc):
    """Simple description translation — keep technical terms, translate common words"""
    if not desc:
        return ""
    # Don't translate Chinese descriptions
    if any('\u4e00' <= c <= '\u9fff' for c in desc):
        # Just fix HTML entities
        return _unescape_html_entities(desc)
    result = _unescape_html_entities(desc)
    for en, cn in sorted(DESC_CN.items(), key=lambda x: -len(x[0])):
        result = result.replace(en, cn)
    # Clean up trailing 's' after Chinese translations
    result = re.sub(r'([\u4e00-\u9fff])s\b', r'\1', result)
    return result


def format_stars(count_str):
    """Format star count in Chinese-friendly way"""
    try:
        n = int(count_str.replace(",", ""))
        if n >= 10000:
            return f"{n/10000:.1f}万"
        elif n >= 1000:
            return f"{n/1000:.1f}k"
        return str(n)
    except:
        return count_str


def _today_stars_sort_key(repo):
    """按今日 star 数排序的 key（容忍空值/千分位）"""
    return int(repo.get("today_stars", "0").replace(",", "") or "0")


def _format_star_line(total, today, period):
    """构建单条 repo 的 star 行：⭐ 总数 + 📈 今日增量"""
    star_info = f"⭐ {total}"
    if today and today != "0" and today != "":
        star_info += f"  📈 +{format_stars(today)} {period}"
    return star_info


def _format_repo_block(index, repo, period_label, translations, use_llm):
    """构建单条 repo 的完整消息块（多行）"""
    name = repo["name"]
    desc_raw = _unescape_html_entities(repo.get("description", ""))
    lang = repo.get("language", "")
    total = format_stars(repo.get("total_stars", "0"))
    today = repo.get("today_stars", "")
    period = repo.get("period", period_label)

    # 优先 LLM 翻译；否则回退关键词替换（translations 按 repo full_name 关联）
    tr = translations.get(name, {}) if use_llm else {}
    if tr:
        desc_cn = tr.get("cn_desc") or (translate_desc(desc_raw) if desc_raw else "")
        comment = tr.get("comment") or ""
    else:
        desc_cn = translate_desc(desc_raw)
        comment = ""

    lang_cn = LANG_CN.get(lang, lang) if lang else ""
    lang_tag = f"「{lang_cn}」" if lang_cn else ""
    lines = [f"{index}. {name} {lang_tag}"]
    if desc_cn:
        lines.append(f"   📝 {desc_cn}")
    elif desc_raw:
        lines.append(f"   📝 {desc_raw}")
    if comment:
        lines.append(f"   💡 {comment}")
    lines.append(f"   {_format_star_line(total, today, period)}")
    lines.append(f"   🔗 {repo['url']}")
    lines.append("")
    return lines


def build_message(repos, since="daily", translations=None):
    """Format trending repos into push message — 中文描述+点评
    translations: {repo_full_name: {cn_desc, comment}} 由 translator.translate_repos() 生成；
    为空则回退 translate_desc 关键词替换。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    period_label = SINCE_CN.get(since, "今日")
    translations = translations or {}
    use_llm = bool(translations)

    lines = [
        f"🔥 GitHub 热门项目 · {period_label}榜 🔥",
        f"📅 {now}",
        "",
    ]

    if not repos:
        lines.append("📭 暂无数据，请稍后查看")
        lines.append("🌐 https://github.com/trending")
        return "\n".join(lines)

    # 按今日涨幅排序
    sorted_repos = sorted(repos, key=_today_stars_sort_key, reverse=True)

    for i, repo in enumerate(sorted_repos[:MAX_MESSAGE_REPOS], 1):
        lines.extend(_format_repo_block(i, repo, period_label, translations, use_llm))

    if len(repos) > MAX_MESSAGE_REPOS:
        lines.append(f"... 共 {len(repos)} 个项目")
        lines.append("")

    lines.append("🌐 https://github.com/trending")

    return "\n".join(lines)


if __name__ == "__main__":
    repos = fetch_trending_scrape()
    if not repos:
        repos = fetch_trending_via_search()
    msg = build_message(repos)
    print(msg)
