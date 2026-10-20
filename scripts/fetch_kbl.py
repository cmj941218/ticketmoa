#!/usr/bin/env python3
"""KBL(남자프로농구) 공식 홈페이지의 공개 경기 일정을 가져와 data/events.json을 갱신한다.

사용법:
  python3 scripts/fetch_kbl.py
  python3 scripts/fetch_kbl.py --fixture tests/fixtures/kbl_matches.json --output /tmp/test.json

KBL 티켓 API는 로그인이 필요하므로 사용하지 않는다. 예매 오픈 일시는
data/ticket-rules.json 의 구단별 규칙(경기 N일 전 HH:MM)이 있을 때만 계산한다.
"""
import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ART_CLASSES, DATA_PATH, KST, CollectError, http_get_json, load_rules, merge_and_save, now_kst, ticket_open  # noqa: E402

API = 'https://api.kbl.or.kr/match/list'
HEADERS = {'Channel': 'WEB', 'TeamCode': 'kbl', 'X-Requested-With': 'XMLHttpRequest', 'lang': 'ko',
           'Origin': 'https://www.kbl.or.kr', 'Referer': 'https://www.kbl.or.kr/'}
DAYS_AHEAD = 45
CATEGORIES = {'R', 'P', 'PO', 'C'}  # 정규시즌·플레이오프·챔피언결정전 (D리그·EASL 제외)
SCHEDULE_URL = 'https://www.kbl.or.kr/match/schedule'
TICKET_URL = 'https://www.kbl.or.kr/ticket/regular'
# 로고 키 → (짧은 이름, 연고 지역)
TEAMS = {
    'db': ('DB', '강원'), 'ss': ('삼성', '서울'), 'sono': ('소노', '경기'), 'sk': ('SK', '서울'),
    'lg': ('LG', '경남'), 'kgc': ('정관장', '경기'), 'kcc': ('KCC', '부산'), 'kt': ('KT', '경기'),
    'pega': ('한국가스공사', '대구'), 'hd': ('현대모비스', '울산'),
}


def fetch_matches(start, end):
    query = urllib.parse.urlencode({'fromDate': start.strftime('%Y%m%d'), 'toDate': end.strftime('%Y%m%d'), 'tcodeList': 'all'})
    data = http_get_json(f'{API}?{query}', HEADERS)
    if not isinstance(data, list):
        raise CollectError(f'KBL 응답 형식이 예상과 다릅니다: {str(data)[:200]}')
    return data


def build_event(g, rules, index):
    game_at = datetime.strptime(g['gameDate'] + g['gameStart'], '%Y%m%d%H%M').replace(tzinfo=KST)
    home, away = g.get('logoH', ''), g.get('logoA', '')
    home_short, area = TEAMS.get(home, (g.get('tnameH', ''), ''))
    away_short = TEAMS.get(away, (g.get('tnameA', ''), ''))[0]
    open_at, verified = ticket_open(rules, home, game_at)
    season = f"{g.get('seasonName1', '')} {g.get('seasonCategoryName', '')}".strip()
    return {
        'id': f"kbl-{g['gmkey']}",
        'category': 'sport',
        'sport': 'basketball',
        'league': 'KBL',
        'title': f"{g.get('tnameH', '')} vs {g.get('tnameA', '')}",
        'subtitle': f"KBL {season}" + (f" · 중계 {g['tv']}" if g.get('tv') else ''),
        'venue': g.get('stadiumnameF') or g.get('stadiumname', ''),
        'area': area,
        'provider': 'KBL 티켓',
        'url': TICKET_URL,
        'links': [{'name': 'KBL 티켓 예매', 'url': TICKET_URL}, {'name': 'KBL 경기 일정', 'url': SCHEDULE_URL}],
        'open': open_at,
        'openEstimated': bool(open_at) and not verified,
        'event': game_at.isoformat(),
        'art': ART_CLASSES[index % len(ART_CLASSES)],
        'artTitle': f'{home_short}\nVS {away_short}',
        'kicker': f"KBL · {season}".upper(),
        'source': 'kbl',
        'isSample': False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixture', help='API 대신 읽을 예제 JSON 파일')
    ap.add_argument('--output', default=str(DATA_PATH))
    args = ap.parse_args()

    now = now_kst()
    if args.fixture:
        matches = json.loads(Path(args.fixture).read_text(encoding='utf-8'))
    else:
        matches = fetch_matches(now.date(), now.date() + timedelta(days=DAYS_AHEAD))

    rules = load_rules('kbl')
    games = [g for g in matches
             if g.get('seasonCategory') in CATEGORIES and g.get('gmkey') and g.get('gameDate') and g.get('gameStart')
             and g.get('logoH') in TEAMS and not g.get('isEnded')]
    games.sort(key=lambda g: (g['gameDate'], g['gameStart']))
    events = [build_event(g, rules, i) for i, g in enumerate(games)]
    events = [e for e in events if datetime.fromisoformat(e['event']) > now or args.fixture]
    merge_and_save('kbl', 'sport', events, args.output)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except CollectError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
