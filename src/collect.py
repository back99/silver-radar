"""Google News RSS에서 실버 산업 관련 기사를 수집한다."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"


def fetch_region_articles(region_name: str, region_cfg: dict, lookback_hours: int, max_articles: int) -> list[dict]:
    """한 지역의 모든 쿼리를 돌면서 기사 목록을 수집하고 중복을 제거한다."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    seen_links: set[str] = set()
    articles: list[dict] = []

    for query in region_cfg["queries"]:
        url = GOOGLE_NEWS_RSS.format(
            query=quote(query),
            hl=region_cfg["hl"],
            gl=region_cfg["gl"],
            ceid=quote(region_cfg["ceid"], safe=":"),
        )
        feed = feedparser.parse(url)
        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or link in seen_links:
                continue

            published = _parse_time(entry)
            if published and published < cutoff:
                continue

            seen_links.add(link)
            articles.append(
                {
                    "region": region_name,
                    "query": query,
                    "title": entry.get("title", "").strip(),
                    "link": link,
                    "source": _source_name(entry),
                    "published": published.isoformat() if published else "",
                }
            )
        time.sleep(0.5)  # RSS 서버에 예의 지키기

    # 최신순 정렬 후 상한 적용
    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles[:max_articles]


def _parse_time(entry) -> datetime | None:
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)


def _source_name(entry) -> str:
    source = entry.get("source")
    if source and hasattr(source, "title"):
        return source.title
    return ""
