"""평가된 하루치 기사를 Claude가 자유 구성으로 묶어 '데일리 브리핑'을 만든다."""
from __future__ import annotations

import json
import os

import anthropic

DIGEST_SYSTEM = """당신은 실버/시니어 산업 전문 애널리스트다.
독자는 한국 시장 타겟으로 시니어 분야 창업을 준비 중이며,
'해외에서 검증됐지만 한국에 없는 모델'과 시장 신호를 찾고 있다.
하루치 기사를 받아, 그날의 내용에 맞게 스스로 구조를 정해 브리핑을 작성한다.
마크다운 코드펜스 없이 순수 JSON 객체만 출력할 것."""

DIGEST_PROMPT = """오늘 수집·평가된 기사 목록 (관련도 높은 순):

{articles_block}

오늘 기사들의 성격에 맞게 **스스로 테마/섹션을 구성해서** 브리핑을 작성하라.
- 비슷한 기사들은 하나의 섹션으로 묶어 종합 코멘트를 달 것 (기사 나열이 아니라 의미 해석)
- 섹션 수는 그날 내용에 따라 1~4개, 자유롭게
- 중요하지 않은 기사는 과감히 제외해도 됨
- 독자의 관심사(한국 갭, 창업 기회)와 연결되는 시사점이 있으면 반드시 짚을 것

JSON 형식:
{{
  "headline": "오늘 가장 중요한 흐름 한 문장",
  "sections": [
    {{
      "title": "섹션 제목 (이모지 포함 가능)",
      "body": "이 묶음에 대한 종합 해설 2~4문장. 단순 요약이 아니라 '그래서 뭐가 중요한지'",
      "items": [{{"index": 0, "note": "이 기사 한 줄 포인트"}}]
    }}
  ]
}}

JSON 객체만 출력."""


def build_digest(evaluated: list[dict], model: str, max_tokens: int) -> dict | None:
    if not evaluated:
        return None

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    articles_block = "\n".join(
        f"[{i}] ({a['region']}/{a.get('relevance', '?')}점) {a['title']} — {a.get('summary', '')}"
        for i, a in enumerate(evaluated)
    )

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=DIGEST_SYSTEM,
        messages=[{"role": "user", "content": DIGEST_PROMPT.format(articles_block=articles_block)}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text")
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        print(f"[warn] 다이제스트 JSON 파싱 실패: {cleaned[:200]}")
        return None
