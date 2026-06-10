# Silver Radar 📡

실버/시니어 산업 트렌드를 매일 자동 수집하는 파이프라인.

**흐름**: GitHub Actions (매일 KST 07:00) → Google News RSS 수집 (한국·일본·북미·유럽) → Claude API로 평가·요약·한국 갭 분석 → Notion DB 저장

## 셋업 (약 20분)

### 1. Notion 데이터베이스 만들기
새 데이터베이스(테이블)를 만들고 속성 이름을 **정확히** 아래와 같이 설정:

| 속성 이름 | 타입 |
|---|---|
| Name | 제목 (기본) |
| URL | URL |
| Region | 선택 |
| Category | 선택 |
| Relevance | 숫자 |
| Summary | 텍스트 |
| KoreaGap | 텍스트 |
| Published | 날짜 |

### 2. Notion Integration 발급
1. https://www.notion.so/my-integrations 에서 새 Integration 생성 → **Internal Integration Secret** 복사 (= `NOTION_TOKEN`)
2. 만든 데이터베이스 페이지 우상단 `...` → 연결(Connections) → 방금 만든 Integration 추가
3. 데이터베이스 URL에서 ID 복사: `notion.so/{workspace}/{이 32자리가 DB ID}?v=...` (= `NOTION_DATABASE_ID`)

### 3. Anthropic API 키
https://console.anthropic.com 에서 발급 (= `ANTHROPIC_API_KEY`)
- 기본 모델은 `claude-haiku-4-5` (저비용). config.yaml에서 변경 가능.
- API 문서: https://docs.claude.com/en/api/overview

### 4. GitHub 저장소 설정
1. 이 폴더를 새 저장소로 push
2. Settings → Secrets and variables → Actions → 시크릿 3개 등록:
   `ANTHROPIC_API_KEY`, `NOTION_TOKEN`, `NOTION_DATABASE_ID`
3. Actions 탭 → "Silver Radar Daily" → **Run workflow**로 수동 첫 실행 테스트

### 로컬 테스트
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=... NOTION_TOKEN=... NOTION_DATABASE_ID=...
python -m src.main
```

## 튜닝 포인트 (config.yaml)
- `regions.*.queries`: 키워드 추가/삭제 — 특정 아이템(예: "안부 확인 AI", "見守りサービス") 추적 시 여기에 추가
- `min_relevance`: 노이즈 많으면 6~7로 상향
- `claude.model`: 더 깊은 분석 원하면 `claude-sonnet-4-6`

## 예상 비용
Haiku 기준 하루 기사 ~100건 평가 시 월 $1~3 수준. GitHub Actions는 public repo면 무료.
