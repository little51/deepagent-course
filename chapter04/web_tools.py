"""给 minihermes 装的两只手：搜网页、读正文。

两个工具都是纯 Python 实现的（Playwright 驱动浏览器 + trafilatura 抽正文），
不依赖 Node/npx，也不需要任何搜索服务的 Key。

这两个函数的 docstring 就是写给模型看的说明书：它据此决定什么时候调哪个。
"""

from __future__ import annotations

from urllib.parse import quote

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def web_search(query: str, max_results: int = 5) -> str:
    """用浏览器搜索网页，返回若干条结果的标题、链接和摘要。

    什么时候用：想知道"有哪些网页在讲这件事"、找官方文档、找最新消息时，先用它。
    拿到链接之后，再用 fetch_url 去读其中某一页的正文。
    """
    from playwright.sync_api import sync_playwright

    url = f"https://cn.bing.com/search?q={quote(query)}&setlang=zh-CN"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="zh-CN", user_agent=UA)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector("li.b_algo", timeout=15000)
        rows = page.eval_on_selector_all(
            "li.b_algo",
            """els => els.map(e => {
                const a = e.querySelector('h2 a');
                const p = e.querySelector('.b_caption p') || e.querySelector('p');
                return {
                    title: (e.querySelector('h2')?.innerText || '').trim(),
                    url: a ? a.href : '',
                    snippet: (p?.innerText || '').trim(),
                };
            })""",
        )
        browser.close()

    lines = []
    for i, row in enumerate(rows[:max_results], 1):
        if not row.get("url"):
            continue
        lines.append(f"{i}. {row['title']}\n   {row['url']}\n   {row['snippet'][:180]}")
    return "\n".join(lines) if lines else f"没有搜到「{query}」的结果"


def fetch_url(url: str, max_chars: int = 4000) -> str:
    """读一个网页的正文，返回去掉导航和广告之后的纯文本。

    什么时候用：已经有具体链接、需要看页面里到底写了什么时。
    长文会被截断，先读前面的部分通常就够判断要不要继续。
    """
    import trafilatura

    html = trafilatura.fetch_url(url)
    if not html:
        return f"抓取失败（页面打不开或超时）：{url}"
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    text = text.strip()
    if not text:
        return f"这个页面没能抽出正文（可能是纯 JS 渲染的）：{url}"
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n（正文共 {len(text)} 字，已截断）"
    return text
