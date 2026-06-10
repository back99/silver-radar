"""Claude API로 수집된 기사를 필터링·요약하고 창업 기회 관점에서 점수를 매긴다.

API 문서: https://docs.claude.com/en/api/overview
"""
from __future__ import annotations

import json
import os

import anthropic

SYSTEM_PROMPT = """당신은 실버/시니어 산업 전문 시장 분석가다.
사용자는 한국 시장을 타겟으로 시니어 분야 창업을 준비 중이며,
특히 '일본·북미·유럽에서 검증됐지만 한국에는 아직 없는 모델'을 찾고 있다.

뉴스 기사 목록을 받으면 각 기사를 평가해 JSON으로만 응답한다.
마크다운 코드펜스 없이 순수 JSON 배열만 출력할 것."""

USER_PROMPT_TEMPLATE = """다음은 오늘 수집된 {region} 지역 실버 산업 관련 기사들이다.

{articles_block}

각 기사에 대해 아래 기준으로 평가하라:
- relevance (1~10): 시니어 산업 창업 기회 탐색 관점의 가치. 단순 복지정책 홍보·행사 소식은 낮게, 새 비즈니스 모델·투자 유치·시장 데이터는 높게.
- category: "비즈니스모델" | "투자/M&A" | "시장데이터" | "정책/규제" | "기술" | "기타" 중 하나
- summary: 한국어 2문장 요약. 무엇이 새로운지 중심으로.
- korea_gap: 이 모델/트렌드가 한국에 존재하는지에 대한 한 줄 코멘트 (모르면 "확인 필요").

JSON 배열로만 응답:
[{{"index": 0, "relevance": 7, "category": "비즈니스모델", "summary": "...", "korea_gap": "..."}}, ...]"""


def analyze_articles(articles: list[dict], region: str, model: str, max_tokens: int) -> list[dict]:
    """기사 목록을 Claude에 보내 평가 결과를 병합해 돌려준다."""
    if not articles:
        return []

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    articles_block = "\n".join(
        f"[{i}] {a['title']} ({a['source']}, {a['published'][:10]})" for i, a in enumerate(articles)
    )

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(region=region, articles_block=articles_block),
            }
        ],
    )

    raw = "".join(block.text for block in response.content if block.type == "text")
    evaluations = _parse_json_array(raw)

    merged: list[dict] = []
    for ev in evaluations:
        idx = ev.get("index")
        if not isinstance(idx, int) or idx >= len(articles):
            continue
        merged.append({**articles[idx], **ev})
    return merged


def _parse_json_array(raw: str) -> list[dict]:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        # 응답 안에서 첫 '['부터 마지막 ']'까지 재시도
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        print(f"[warn] Claude 응답 JSON 파싱 실패. 원문 일부: {cleaned[:200]}")
        return []
