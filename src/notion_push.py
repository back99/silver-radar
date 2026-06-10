"""Notion 저장: 일일 브리핑 페이지 1장 + 고득점 기사만 DB 아카이브.

필요 환경변수:
  NOTION_TOKEN, NOTION_DATABASE_ID(아카이브 DB), NOTION_PARENT_PAGE_ID(브리핑 부모 페이지)
"""
from __future__ import annotations

import os

import requests

NOTION_PAGES_API = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _link_bullet(text: str, url: str, suffix: str = "") -> dict:
    """링크 텍스트 + 부가 설명으로 구성된 bullet 블록."""
    rich = [{"type": "text", "text": {"content": text[:200], "link": {"url": url} if url and len(url) <= 2000 else None}}]
    if suffix:
        rich.append({"type": "text", "text": {"content": f" — {suffix[:300]}"}})
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rich}}


def _heading(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:1900]}}]}}


def push_daily_briefing(digest: dict, evaluated: list[dict], date_str: str) -> bool:
    """하루치 브리핑을 부모 페이지 아래 새 페이지로 생성한다. 섹션 구성은 digest가 결정."""
    parent_id = os.environ["NOTION_PARENT_PAGE_ID"]

    blocks: list[dict] = [_paragraph(f"💬 {digest.get('headline', '')}")]

    for section in digest.get("sections", []):
        blocks.append(_heading(section.get("title", "")[:100]))
        if section.get("body"):
            blocks.append(_paragraph(section["body"]))
        for it in section.get("items", []):
            idx = it.get("index")
            if isinstance(idx, int) and 0 <= idx < len(evaluated):
                a = evaluated[idx]
                blocks.append(_link_bullet(a["title"], a["link"], it.get("note", "")))

    payload = {
        "parent": {"page_id": parent_id},
        "icon": {"type": "emoji", "emoji": "📰"},
        "properties": {"title": {"title": [{"text": {"content": f"{date_str} 브리핑 ({len(evaluated)}건 분석)"}}]}},
        "children": blocks[:95],
    }
    resp = requests.post(NOTION_PAGES_API, headers=_headers(), json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"[warn] 브리핑 페이지 생성 실패 ({resp.status_code}): {resp.text[:200]}")
        return False
    return True


def push_gems_to_db(items: list[dict]) -> int:
    """고득점 기사만 아카이브 DB에 저장한다."""
    database_id = os.environ["NOTION_DATABASE_ID"]
    saved = 0
    for item in items:
        link = item["link"]
        payload = {
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {"title": [{"text": {"content": item["title"][:200]}}]},
                "URL": {"url": link if len(link) <= 2000 else None},
                "Region": {"select": {"name": item["region"]}},
                "Category": {"select": {"name": item.get("category", "기타")}},
                "Relevance": {"number": item.get("relevance", 0)},
                "Summary": {"rich_text": [{"text": {"content": item.get("summary", "")[:1900]}}]},
                "KoreaGap": {"rich_text": [{"text": {"content": item.get("korea_gap", "")[:1900]}}]},
            },
        }
        if item.get("published"):
            payload["properties"]["Published"] = {"date": {"start": item["published"]}}

        resp = requests.post(NOTION_PAGES_API, headers=_headers(), json=payload, timeout=30)
        if resp.status_code == 200:
            saved += 1
        else:
            print(f"[warn] DB 저장 실패 ({resp.status_code}): {resp.text[:200]}")
    return saved
