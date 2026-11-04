"""Daily Nasdaq Trader US exchange directory, retaining last successful cache."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import csv
import io
import json
from pathlib import Path
import re
from threading import Lock
import time
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

CACHE = Path(__file__).resolve().parent / '.cache' / 'us_listings.json'
DAY = 86400
RETRY = 3600
_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='us-listings')
_future = None
_last_attempt = 0
_snapshot = None
_failed = False
EXCHANGES = {'N': 'NYSE', 'A': 'NYSE American', 'P': 'NYSE Arca',
             'Z': 'Cboe BZX', 'V': 'IEX'}


def parse_listing(payload, nasdaq):
    text = payload.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text), delimiter='|')
    code_field = 'Symbol' if nasdaq else 'NASDAQ Symbol'
    required = {code_field, 'Security Name', 'Test Issue', 'ETF'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Nasdaq directory header missing')
    if 'File Creation Time:' not in text:
        raise ValueError('Truncated Nasdaq directory')
    rows = []
    for row in reader:
        if row.get('Test Issue') != 'N':
            continue
        code = (row.get(code_field) or '').strip()
        name = (row.get('Security Name') or '').strip()
        # Keep ordinary tickers and class shares; special preferred/warrant
        # symbology is provider-specific and must not be guessed as Yahoo codes.
        if not name or not re.fullmatch(r'[A-Z][A-Z0-9]*(?:[.-][A-Z])?', code):
            continue
        exchange = 'NASDAQ' if nasdaq else EXCHANGES.get(row.get('Exchange'))
        if not exchange:
            continue
        rows.append({'name': name, 'code': code.replace('.', '-'),
                     'exchange': exchange, 'kind': 'ETF' if row['ETF'] == 'Y' else '주식/증권'})
    return rows


def validate_snapshot(data):
    if not isinstance(data, dict) or not isinstance(data.get('updated_at'), (int, float)):
        raise ValueError('Invalid US directory cache')
    seen = set()
    counts = {'NASDAQ': 0, 'other': 0}
    for row in data.get('rows', []):
        if (not isinstance(row.get('name'), str) or not row['name']
                or not re.fullmatch(r'[A-Z][A-Z0-9-]{0,12}', row.get('code', ''))
                or row.get('exchange') not in {'NASDAQ', *EXCHANGES.values()}
                or row.get('kind') not in {'ETF', '주식/증권'} or row['code'] in seen):
            raise ValueError('Invalid US listing row')
        seen.add(row['code'])
        counts['NASDAQ' if row['exchange'] == 'NASDAQ' else 'other'] += 1
    if counts['NASDAQ'] < 1000 or counts['other'] < 1000:
        raise ValueError('Incomplete US directory')
    return data


def download_snapshot():
    combined = {}
    for filename, nasdaq in [('nasdaqlisted.txt', True), ('otherlisted.txt', False)]:
        request = Request('https://www.nasdaqtrader.com/dynamic/SymDir/' + filename,
                          headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=10) as response:
            for row in parse_listing(response.read(10_000_000), nasdaq):
                combined[row['code']] = row
    return validate_snapshot({'updated_at': time.time(), 'rows': list(combined.values())})


def refresh():
    global _snapshot, _failed
    try:
        data = download_snapshot()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        temporary = CACHE.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        temporary.replace(CACHE)
        with _lock:
            _snapshot, _failed = data, False
    except Exception:
        # Keep the last valid directory; retry is throttled in get_directory().
        with _lock:
            _failed = True


def get_directory():
    """Check age on app interaction; refresh in background, at most once/day.

    After a failed refresh retry after one hour. Disk cache survives app reruns
    and process restarts, but Streamlit redeploys may remove the local disk.
    """
    global _snapshot, _future, _last_attempt
    now = time.time()
    with _lock:
        if _snapshot is None:
            try:
                _snapshot = validate_snapshot(json.loads(CACHE.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                _snapshot = {'updated_at': 0, 'rows': []}
        stale = now - _snapshot['updated_at'] >= DAY
        running = _future is not None and not _future.done()
        if stale and not running and now - _last_attempt >= RETRY:
            _last_attempt = now
            _future = _executor.submit(refresh)
            running = True
        rows = list(_snapshot['rows'])
        stamp = _snapshot['updated_at']
        if stamp:
            date = datetime.fromtimestamp(stamp, timezone.utc).astimezone(
                ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M')
            message = f'미국 상장 종목 {len(rows):,}개 · Nasdaq Trader · 갱신 {date} (한국 시간)'
            if stale:
                message += ' · 이전 목록 사용 중'
        else:
            message = '미국 전체 목록 준비 중 · 현재 기본 종목만 표시합니다.'
        if _failed:
            message += ' · 갱신 연결 실패, 1시간 후 다음 이용 시 재시도'
        elif running:
            message += ' · 백그라운드 갱신 중 · 완료 후 자동 반영됩니다.'
        return rows, message
