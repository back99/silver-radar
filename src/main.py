"""Silver Radar: 실버 산업 트렌드 일일 수집 파이프라인.

흐름: Google News RSS 수집 → Claude로 평가/요약 → Notion DB 저장
실행: python -m src.main  (저장소 루트에서)
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from src.analyze import analyze_articles
from src.collect import fetch_region_articles
from src.notion_push import push_to_notion


def main() -> int:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    lookback = config["lookback_hours"]
    max_per_region = config["max_articles_per_region"]
    claude_cfg = config["claude"]
    min_relevance = config["min_relevance"]

    all_evaluated: list[dict] = []
    for region_name, region_cfg in config["regions"].items():
        articles = fetch_region_articles(region_name, region_cfg, lookback, max_per_region)
        print(f"[{region_name}] 수집된 기사: {len(articles)}건")
        if not articles:
            continue

        evaluated = analyze_articles(
            articles, region_name, claude_cfg["model"], claude_cfg["max_tokens"]
        )
        print(f"[{region_name}] 평가 완료: {len(evaluated)}건")
        all_evaluated.extend(evaluated)

    filtered = [e for e in all_evaluated if e.get("relevance", 0) >= min_relevance]
    filtered.sort(key=lambda e: e.get("relevance", 0), reverse=True)
    print(f"관련도 {min_relevance}점 이상: {len(filtered)}건 → Notion 저장 시작")

    saved = push_to_notion(filtered)
    print(f"Notion 저장 완료: {saved}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
