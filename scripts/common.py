"""수집기 공통 기능: HTTP 요청, 예매 오픈 규칙 적용, data/events.json 병합.

파이썬 표준 라이브러리만 사용한다.
"""
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / 'data' / 'events.json'
RULES_PATH = ROOT / 'data' / 'ticket-rules.json'
ART_CLASSES = ['poster-one', 'poster-two', 'poster-three', 'poster-four', 'poster-five', 'poster-six']


class CollectError(RuntimeError):
    pass


def http_get_json(url, headers=None, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ticketmoa-collector/1.0', **(headers or {})})
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode('utf-8'))
        except Exception as e:  # 네트워크 일시 오류는 재시도
            last = e
            time.sleep(2 * (attempt + 1))
    raise CollectError(f'요청 실패 {url}: {last}')


def now_kst():
    return datetime.now(KST)


def load_rules(league):
    """data/ticket-rules.json 에서 리그별 예매 오픈 규칙을 읽는다."""
    if not RULES_PATH.exists():
        return {}
    return json.loads(RULES_PATH.read_text(encoding='utf-8')).get(league, {})


def _at(game_at, days_before, hhmm):
    hh, mm = map(int, hhmm.split(':'))
    day = (game_at - timedelta(days=int(days_before))).date()
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=KST).isoformat()


def ticket_open(rules, team_key, game_at):
    """규칙(경기 N일 전 HH:MM)으로 예매 오픈 정보를 계산한다.

    반환: {'open': ISO|None, 'openEstimated': bool, 'openSource': URL|None, 'presale': {'label','at'}|None}
    """
    rule = (rules.get('teams') or {}).get(team_key) or rules.get('default')
    if not rule or rule.get('daysBefore') is None or not rule.get('time'):
        return {'open': None, 'openEstimated': False, 'openSource': None, 'presale': None}
    pre = rule.get('presale')
    return {
        'open': _at(game_at, rule['daysBefore'], rule['time']),
        'openEstimated': not rule.get('verified'),
        'openSource': rule.get('sourceUrl'),
        'presale': {'label': pre.get('label', '선예매'), 'at': _at(game_at, pre['daysBefore'], pre['time'])} if pre else None,
    }


def merge_and_save(source, category, new_events, output=DATA_PATH):
    """source가 같은 기존 항목과 같은 category의 가상 예시를 새 데이터로 교체해 저장한다."""
    if not new_events:
        # 이상 상황에서 0건이 오면 기존 데이터를 지우지 않는다.
        raise CollectError(f'{source}: 수집된 일정이 0건입니다. 기존 데이터를 유지합니다.')
    out = Path(output)
    data = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {'meta': {}, 'events': []}
    kept = [e for e in data.get('events', [])
            if e.get('source') != source and not (e.get('category') == category and e.get('isSample'))]
    stamp = now_kst().replace(microsecond=0).isoformat()
    meta = data.get('meta', {})
    meta['updatedAt'] = stamp
    meta.setdefault('sources', {})[source] = {'updatedAt': stamp, 'count': len(new_events)}
    data['meta'] = meta
    data['events'] = kept + new_events
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{source}: {len(new_events)}건 저장 (기타 {len(kept)}건 유지) → {out}')
