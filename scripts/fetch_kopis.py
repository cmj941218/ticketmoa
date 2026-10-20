#!/usr/bin/env python3
"""KOPIS(공연예술통합전산망) Open API에서 공연 예정 뮤지컬을 가져와 data/events.json을 갱신한다.

외부 패키지 없이 파이썬 표준 라이브러리만 사용한다.

사용법:
  KOPIS_API_KEY=발급키 python3 scripts/fetch_kopis.py
  python3 scripts/fetch_kopis.py --fixtures tests/fixtures   # 키 없이 예제 XML로 테스트

KOPIS는 '예매 오픈 일시'를 제공하지 않으므로 open은 null로 두고 개막일(event)을 기준으로 표시한다.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
API_BASE = 'http://www.kopis.or.kr/openApi/restful/pblprfr'  # KOPIS API는 https 요청을 http로 돌려보냄
GENRE_MUSICAL = 'GGGA'
STATE_UPCOMING = '01'
DAYS_AHEAD = 60        # 오늘부터 며칠 뒤 개막 공연까지 가져올지
WINDOW_DAYS = 31       # KOPIS 조회 기간 최대 31일
ROWS = 100             # KOPIS 한 페이지 최대 100건
MAX_EVENTS = 400
DATA_PATH = Path(__file__).resolve().parent.parent / 'data' / 'events.json'
ART_CLASSES = ['poster-one', 'poster-two', 'poster-three', 'poster-four', 'poster-five', 'poster-six']


class KopisError(RuntimeError):
    pass


def text(node, tag):
    el = node.find(tag)
    return (el.text or '').strip() if el is not None and el.text else ''


def https(url):
    return 'https://' + url[len('http://'):] if url.startswith('http://') else url


def poster_url(url):
    # 포스터는 https://kopis.or.kr 에서 제공됨 (https://www. 는 리다이렉트)
    for prefix in ('http://www.kopis.or.kr/', 'https://www.kopis.or.kr/', 'http://kopis.or.kr/'):
        if url.startswith(prefix):
            return 'https://kopis.or.kr/' + url[len(prefix):]
    return https(url)


def parse_xml(raw):
    root = ET.fromstring(raw)
    # 인증키 오류 등은 <returncode>/<errmsg> 형태로 돌아온다.
    code = root.findtext('.//returncode') or root.findtext('.//returnCode')
    if code and code.strip() not in ('00', '0'):
        msg = root.findtext('.//errmsg') or root.findtext('.//returnMsg') or ''
        raise KopisError(f'KOPIS 오류 코드 {code.strip()}: {msg.strip()}')
    return root


class Client:
    def __init__(self, key=None, fixtures=None):
        self.key, self.fixtures = key, Path(fixtures) if fixtures else None

    def get(self, path, params):
        if self.fixtures:
            name = 'list.xml' if not path else f'detail_{path}.xml'
            f = self.fixtures / name
            return parse_xml(f.read_bytes()) if f.exists() else None
        query = urllib.parse.urlencode({'service': self.key, **params})
        url = f"{API_BASE}{'/' + path if path else ''}?{query}"
        last = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'ticketmoa-collector/1.0'})
                with urllib.request.urlopen(req, timeout=30) as res:
                    return parse_xml(res.read())
            except KopisError:
                raise
            except Exception as e:  # 네트워크 일시 오류는 재시도
                last = e
                time.sleep(2 * (attempt + 1))
        raise KopisError(f'KOPIS 요청 실패: {last}')


def list_upcoming(client, today):
    found = {}
    start = today
    end_limit = today + timedelta(days=DAYS_AHEAD)
    while start <= end_limit:
        end = min(start + timedelta(days=WINDOW_DAYS - 1), end_limit)
        page = 1
        while True:
            root = client.get('', {
                'stdate': start.strftime('%Y%m%d'), 'eddate': end.strftime('%Y%m%d'),
                'cpage': page, 'rows': ROWS, 'shcate': GENRE_MUSICAL, 'prfstate': STATE_UPCOMING,
            })
            rows = root.findall('db') if root is not None else []
            for db in rows:
                pid = text(db, 'mt20id')
                if pid:
                    found[pid] = db
            if client.fixtures or len(rows) < ROWS:
                break
            page += 1
            time.sleep(0.2)
        if client.fixtures:
            break
        start = end + timedelta(days=1)
    return list(found.values())


def to_iso_date(kopis_date):
    # '2026.11.01' -> '2026-11-01T00:00:00+09:00'
    y, m, d = kopis_date.split('.')
    return f'{y}-{int(m):02d}-{int(d):02d}T00:00:00+09:00'


def build_event(db, detail, index):
    pid = text(db, 'mt20id')
    title = text(db, 'prfnm')
    start, end = text(db, 'prfpdfrom'), text(db, 'prfpdto')
    area = text(db, 'area')
    links = []
    if detail is not None:
        for rel in detail.findall('.//relate'):
            name, url = text(rel, 'relatenm'), text(rel, 'relateurl')
            if name and url.startswith(('http://', 'https://')):
                links.append({'name': name, 'url': https(url)})
    kopis_page = f'https://www.kopis.or.kr/por/db/pblprfr/pblprfrView.do?menuId=MNU_00020&mt20Id={pid}'
    cast = text(detail, './/prfcast') if detail is not None else ''
    return {
        'id': f'kopis-{pid}',
        'category': 'musical',
        'title': title,
        'subtitle': f'공연기간 {start} ~ {end}' + (f' · {cast[:40]}' if cast else ''),
        'venue': text(db, 'fcltynm'),
        'area': area,
        'provider': links[0]['name'] if links else 'KOPIS',
        'url': links[0]['url'] if links else kopis_page,
        'links': links,
        'infoUrl': kopis_page,
        'open': None,
        'event': to_iso_date(start),
        'eventEnd': to_iso_date(end) if end else None,
        'timeUnknown': True,
        'poster': poster_url(text(db, 'poster')),
        'art': ART_CLASSES[index % len(ART_CLASSES)],
        'artTitle': title,
        'kicker': f"MUSICAL · {area or 'KOREA'}",
        'source': 'kopis',
        'isSample': False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixtures', help='API 대신 읽을 예제 XML 폴더')
    ap.add_argument('--output', default=str(DATA_PATH))
    args = ap.parse_args()

    key = os.environ.get('KOPIS_API_KEY', '').strip()
    if not key and not args.fixtures:
        print('KOPIS_API_KEY가 설정되지 않아 수집을 건너뜁니다.')
        return 0

    client = Client(key, args.fixtures)
    today = datetime.now(KST).date()
    rows = list_upcoming(client, today)
    rows.sort(key=lambda db: (text(db, 'prfpdfrom'), text(db, 'prfnm')))
    rows = rows[:MAX_EVENTS]

    new_events = []
    for i, db in enumerate(rows):
        pid = text(db, 'mt20id')
        try:
            detail = client.get(pid, {})
        except KopisError as e:
            print(f'상세 조회 실패 {pid}: {e}', file=sys.stderr)
            detail = None
        new_events.append(build_event(db, detail, i))
        if not client.fixtures:
            time.sleep(0.1)

    if not new_events:
        # API 이상으로 0건이 오면 기존 데이터를 지우지 않는다.
        raise KopisError('수집된 뮤지컬이 0건입니다. 기존 데이터를 유지합니다.')

    out = Path(args.output)
    data = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {'meta': {}, 'events': []}
    kept = [e for e in data.get('events', [])
            if e.get('source') != 'kopis' and not (e.get('category') == 'musical' and e.get('isSample'))]
    now = datetime.now(KST).replace(microsecond=0).isoformat()
    meta = data.get('meta', {})
    meta['updatedAt'] = now
    meta.setdefault('sources', {})['kopis'] = {'updatedAt': now, 'count': len(new_events)}
    data['meta'] = meta
    data['events'] = kept + new_events
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'KOPIS 뮤지컬 {len(new_events)}건 저장 (기타 {len(kept)}건 유지) → {out}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KopisError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
