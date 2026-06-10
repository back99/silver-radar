"""Silver Radar: 실버 산업 트렌드 일일 수집 파이프라인 (v2: 데일리 브리핑).

흐름: RSS 수집 → Claude 평가 → ① 데일리 브리핑 페이지 1장 ② 고득점만 DB 아카이브
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from src.analyze import analyze_articles
from src.collect import fetch_region_articles
from src.digest import build_digest
from src.notion_push import push_daily_briefing, push_gems_to_db

KST = timezone(timedelta(hours=9))


def main() -> int:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    claude_cfg = config["claude"]
    min_relevance = config["min_relevance"]
    db_min = config.get("db_min_relevance", 8)

    all_evaluated: list[dict] = []
    for region_name, region_cfg in config["regions"].items():
        articles = fetch_region_articles(
            region_name, region_cfg, config["lookback_hours"], config["max_articles_per_region"]
        )
        print(f"[{region_name}] 수집된 기사: {len(articles)}건")
        if not articles:
            continue
        evaluated = analyze_articles(articles, region_name, claude_cfg["model"], claude_cfg["max_tokens"])
        print(f"[{region_name}] 평가 완료: {len(evaluated)}건")
        all_evaluated.extend(evaluated)

    filtered = [e for e in all_evaluated if e.get("relevance", 0) >= min_relevance]
    filtered.sort(key=lambda e: e.get("relevance", 0), reverse=True)
    print(f"관련도 {min_relevance}점 이상: {len(filtered)}건")

    if not filtered:
        print("브리핑할 기사 없음. 종료.")
        return 0

    # ① 데일리 브리핑 페이지
    digest = build_digest(filtered, claude_cfg["model"], claude_cfg["max_tokens"])
    if digest:
        date_str = datetime.now(KST).strftime("%Y-%m-%d")
        ok = push_daily_briefing(digest, filtered, date_str)
        print(f"데일리 브리핑 페이지: {'생성 완료' if ok else '실패'}")

    # ② 고득점 기사만 DB 아카이브
    gems = [e for e in filtered if e.get("relevance", 0) >= db_min]
    saved = push_gems_to_db(gems)
    print(f"DB 아카이브 ({db_min}점 이상): {saved}/{len(gems)}건 저장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
