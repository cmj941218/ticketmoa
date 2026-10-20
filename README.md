# 티켓모아

영화·뮤지컬·스포츠 예매 오픈 일정을 한눈에 모아보는 정적 웹사이트입니다. GitHub Pages로 배포합니다.

## 구조

| 파일 | 역할 |
| --- | --- |
| `index.html` | 화면 구조 |
| `style.css` | 화면 스타일 |
| `app.js` | 데이터 로드, 검색/필터, 관심 저장, 알림 설정 체험 |
| `data/events.json` | 예매 일정 데이터 (이 파일만 바꾸면 사이트가 갱신됨) |

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

## 현재 한계

- 현재 데이터는 모두 가상 예시입니다.
- 관심 목록·알림 설정은 브라우저 localStorage에만 저장되며 실제 알림은 발송되지 않습니다.
