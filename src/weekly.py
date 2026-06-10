"""주간 리포트: 지난 7일치 데이터를 종합해 Notion 페이지 1장으로.

실행: python -m src.weekly  (매주 일요일 18:00 KST, GitHub Actions)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
import requests
import yaml

from src.notion_push import _headers, _heading, _link_bullet, _paragraph, NOTION_PAGES_API

KST = timezone(timedelta(hours=9))

WEEKLY_SYSTEM = """당신은 실버/시니어 산업 전문 시장 분석가다.
독자는 한국 타겟 시니어 창업 준비자로, 후보 아이템 점수표를 운영 중이다:
1) 부모 안부 AI 에이전트(자녀 구독) 2) 시니어 피싱 방어 3) 방문요양 AI 스케줄링 SaaS
4) 엔딩 산업 비교 포털 5) 렌탈 손주 6) 시니어 단기알바 매칭. (1+2 통합 컨셉 = '디지털 보호자')
일주일치 기사 데이터를 받아 주간 리포트를 작성한다.
마크다운 코드펜스 없이 순수 JSON만 출력."""

WEEKLY_PROMPT = """지난 7일간 수집된 기사 데이터:

{articles_block}

주간 리포트를 작성하라:
- 이번 주의 큰 흐름 (단순 나열 말고 패턴/방향)
- 후보 아이템 점수표에 영향을 주는 신호가 있으면 명시 (어느 후보, 긍정/부정, 근거 기사)
- 한국 갭 관점에서 새로 발견된 기회
- 다음 주에 주시할 것

JSON 형식:
{{
  "headline": "이번 주를 한 문장으로",
  "sections": [
    {{"title": "섹션 제목", "body": "해설 3~5문장",
      "items": [{{"index": 0, "note": "한 줄 포인트"}}]}}
  ],
  "scoreboard_signals": [
    {{"candidate": "후보 이름", "direction": "긍정|부정|중립", "reason": "근거", "index": 3}}
  ]
}}
신호가 없으면 scoreboard_signals는 빈 배열. JSON만 출력."""


def load_week_data(data_dir: Path, days: int = 7) -> list[dict]:
    articles: list[dict] = []
    today = datetime.now(KST).date()
    for d in range(days):
        f = data_dir / f"{(today - timedelta(days=d)).isoformat()}.json"
        if f.exists():
            articles.extend(json.loads(f.read_text(encoding="utf-8")))
    # 중복 링크 제거
    seen, unique = set(), []
    for a in articles:
        if a["link"] not in seen:
            seen.add(a["link"])
            unique.append(a)
    unique.sort(key=lambda a: a.get("relevance", 0), reverse=True)
    return unique


def build_weekly(articles: list[dict], model: str, max_tokens: int) -> dict | None:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    block = "\n".join(
        f"[{i}] ({a['region']}/{a.get('relevance', '?')}점/{a.get('published', '')[:10]}) "
        f"{a['title']} — {a.get('summary', '')} / 갭: {a.get('korea_gap', '')}"
        for i, a in enumerate(articles[:120])
    )
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=WEEKLY_SYSTEM,
        messages=[{"role": "user", "content": WEEKLY_PROMPT.format(articles_block=block)}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        s, e = cleaned.find("{"), cleaned.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(cleaned[s : e + 1])
            except json.JSONDecodeError:
                pass
        print(f"[warn] 주간 리포트 JSON 파싱 실패: {cleaned[:200]}")
        return None


def push_weekly_page(report: dict, articles: list[dict], start: str, end: str) -> bool:
    parent_id = os.environ["NOTION_PARENT_PAGE_ID"]
    blocks = [_paragraph(f"💬 {report.get('headline', '')}")]

    signals = report.get("scoreboard_signals", [])
    if signals:
        blocks.append(_heading("🎯 후보 점수표 신호"))
        for s in signals:
            idx = s.get("index")
            note = f"[{s.get('direction', '')}] {s.get('reason', '')}"
            if isinstance(idx, int) and 0 <= idx < len(articles):
                blocks.append(_link_bullet(f"{s.get('candidate', '')} — {articles[idx]['title']}",
                                           articles[idx]["link"], note))
            else:
                blocks.append(_paragraph(f"• {s.get('candidate', '')}: {note}"))

    for sec in report.get("sections", []):
        blocks.append(_heading(sec.get("title", "")[:100]))
        if sec.get("body"):
            blocks.append(_paragraph(sec["body"]))
        for it in sec.get("items", []):
            idx = it.get("index")
            if isinstance(idx, int) and 0 <= idx < len(articles):
                a = articles[idx]
                blocks.append(_link_bullet(a["title"], a["link"], it.get("note", "")))

    payload = {
        "parent": {"page_id": parent_id},
        "icon": {"type": "emoji", "emoji": "📊"},
        "properties": {"title": {"title": [{"text": {"content": f"주간 리포트 {start} ~ {end}"}}]}},
        "children": blocks[:95],
    }
    resp = requests.post(NOTION_PAGES_API, headers=_headers(), json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"[warn] 주간 리포트 생성 실패 ({resp.status_code}): {resp.text[:200]}")
        return False
    return True


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    weekly_cfg = config.get("weekly", {})
    model = weekly_cfg.get("model", "claude-sonnet-4-6")
    max_tokens = weekly_cfg.get("max_tokens", 6000)

    articles = load_week_data(root / "data")
    print(f"지난 7일 누적 기사: {len(articles)}건")
    if not articles:
        print("데이터 없음. 종료.")
        return 0

    report = build_weekly(articles, model, max_tokens)
    if not report:
        return 1

    today = datetime.now(KST).date()
    ok = push_weekly_page(report, articles, (today - timedelta(days=6)).isoformat(), today.isoformat())
    print(f"주간 리포트: {'생성 완료' if ok else '실패'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
