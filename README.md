# 티켓모아

영화·뮤지컬·스포츠 예매 오픈 일정을 한눈에 모아보는 정적 웹사이트입니다. GitHub Pages로 배포합니다.

## 구조

| 파일 | 역할 |
| --- | --- |
| `index.html` | 화면 구조 |
| `style.css` | 화면 스타일 |
| `app.js` | 데이터 로드, 검색/필터, 관심 저장, 알림 설정 체험 |
| `data/events.json` | 예매 일정 데이터 (이 파일만 바꾸면 사이트가 갱신됨) |
| `scripts/fetch_kbl.py` | KBL 농구 경기 일정 수집기 |
| `scripts/common.py` | 수집기 공통 기능 (요청·병합·오픈 규칙) |
| `data/ticket-rules.json` | 구단별 예매 오픈 규칙 (경기 N일 전 HH:MM) |
| `.github/workflows/deploy.yml` | 하루 3회 수집 + GitHub Pages 배포 |

## 로컬에서 보기

`fetch`로 데이터를 불러오기 때문에 `index.html`을 더블클릭하면 동작하지 않습니다. 간단한 서버로 여세요.

```bash
python3 -m http.server 8080
```

브라우저에서 http://localhost:8080 접속.

## 일정 데이터 형식 (`data/events.json`)

```json
{
  "meta": { "updatedAt": "2026-10-20T00:00:00+09:00", "source": "manual" },
  "events": [
    {
      "id": "고유ID",
      "category": "movie | musical | sport",
      "title": "제목",
      "subtitle": "부제",
      "venue": "장소",
      "provider": "예매처 이름",
      "url": "https://예매처 링크",
      "open": "2026-10-21T14:00:00+09:00",
      "event": "2026-11-14T18:00:00+09:00",
      "art": "poster-one ~ poster-six",
      "artTitle": "포스터 문구(줄바꿈은 \n)",
      "kicker": "포스터 상단 작은 문구",
      "source": "sample | manual | 수집기 이름",
      "isSample": false
    }
  ]
}
```

- `open`/`event` 시간은 반드시 `+09:00`(KST)을 포함합니다.
- `isSample: true`인 항목에는 "가상 예시" 배지가 붙습니다.

## 자동 수집

GitHub Actions가 매일 06·12·18시(KST)에 수집기를 실행하고, 데이터가 바뀌면 커밋 후 다시 배포합니다.
Actions 탭 → "데이터 갱신 및 배포" → Run workflow 로 즉시 실행할 수 있습니다.

| 리그 | 수집기 | 출처 | 상태 |
| --- | --- | --- | --- |
| KBL (농구) | `scripts/fetch_kbl.py` | KBL 공식 홈페이지 공개 일정 | 사용 중 |
| K리그 (축구) | - | - | 예정 |
| KBO (야구) | - | - | 예정 (정규시즌 3월 개막) |

- 수집 결과가 0건이거나 오류가 나면 기존 데이터를 그대로 둡니다.
- 예매 오픈 일시는 공개 API로 제공되지 않습니다. `data/ticket-rules.json`에 구단별 규칙을 넣으면 계산해서 표시하고, 없으면 "예매처에서 확인"으로 표시합니다.

키 없이 테스트:

```bash
python3 scripts/fetch_kbl.py --fixture tests/fixtures/kbl_matches.json --output /tmp/test.json
```

macOS에서 python.org 파이썬으로 실제 수집을 돌릴 때 SSL 오류가 나면 `SSL_CERT_FILE=/etc/ssl/cert.pem`을 앞에 붙이세요.

## 현재 한계

- 영화·뮤지컬 데이터는 아직 가상 예시입니다.
- 관심 목록·알림 설정은 브라우저 localStorage에만 저장되며 실제 알림은 발송되지 않습니다.
