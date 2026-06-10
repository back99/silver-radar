"""평가된 기사를 Notion 데이터베이스에 저장한다.

Notion DB에 필요한 속성(이름은 정확히 일치해야 함):
  - Name (title), URL (url), Region (select), Category (select),
    Relevance (number), Summary (rich_text), KoreaGap (rich_text), Published (date)
"""
from __future__ import annotations

import os

import requests

NOTION_API = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


def push_to_notion(items: list[dict]) -> int:
    token = os.environ["NOTION_TOKEN"]
    database_id = os.environ["NOTION_DATABASE_ID"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    saved = 0
    for item in items:
        payload = {
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {"title": [{"text": {"content": item["title"][:200]}}]},
                "URL": {"url": item["link"] if len(item["link"]) <= 2000 else None},
                "Region": {"select": {"name": item["region"]}},
                "Category": {"select": {"name": item.get("category", "기타")}},
                "Relevance": {"number": item.get("relevance", 0)},
                "Summary": {"rich_text": [{"text": {"content": item.get("summary", "")[:1900]}}]},
                "KoreaGap": {"rich_text": [{"text": {"content": item.get("korea_gap", "")[:1900]}}]},
            },
        }
        if item.get("published"):
            payload["properties"]["Published"] = {"date": {"start": item["published"]}}

        resp = requests.post(NOTION_API, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            saved += 1
        else:
            print(f"[warn] Notion 저장 실패 ({resp.status_code}): {resp.text[:200]}")
    return saved
