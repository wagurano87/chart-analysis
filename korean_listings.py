"""KIND listed-company directory with a non-blocking, daily disk cache."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from threading import Lock
import time
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MARKETS = {'코스피': 'stockMkt', '코스닥': 'kosdaqMkt', '코넥스': 'konexMkt'}
CACHE = Path(__file__).resolve().parent / '.cache' / 'korean_listings.json'
DAY = 86400
RETRY = 3600
_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='korean-listings')
_future = None
_last_attempt = 0
_snapshot = None
_failed = False


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        if tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        if tag == 'tr' and self.row:
            self.rows.append(self.row)


def parse_listing(payload, market):
    # KIND serves an HTML table as an Excel download, normally encoded EUC-KR.
    try:
        html = payload.decode('utf-8-sig')
    except UnicodeDecodeError:
        html = payload.decode('cp949')
    parser = TableParser()
    parser.feed(html)
    header = next((row for row in parser.rows if '회사명' in row and '종목코드' in row), None)
    if header is None:
        raise ValueError('KIND listing header missing')
    ni, ci = header.index('회사명'), header.index('종목코드')
    result = []
    for row in parser.rows:
        if len(row) <= max(ni, ci):
            continue
        name, code = row[ni], row[ci]
        if re.fullmatch(r'\d{6}', code) and name:
            result.append({'name': name, 'code': code, 'exchange': market})
    return result


def validate_snapshot(data):
    if not isinstance(data, dict) or not isinstance(data.get('updated_at'), (float, int)):
        raise ValueError('Invalid listing cache')
    rows = data.get('rows', [])
    seen = set()
    counts = {market: 0 for market in MARKETS}
    for row in rows:
        if (not isinstance(row.get('name'), str) or not row['name']
                or not re.fullmatch(r'\d{6}', row.get('code', ''))
                or row.get('exchange') not in counts or row['code'] in seen):
            raise ValueError('Invalid listing row')
        seen.add(row['code'])
        counts[row['exchange']] += 1
    # Reject empty, truncated or error pages instead of replacing a good cache.
    if counts['코스피'] < 500 or counts['코스닥'] < 500 or counts['코넥스'] < 20:
        raise ValueError('Incomplete KIND directory')
    return data


def download_snapshot():
    rows = []
    for market, market_type in MARKETS.items():
        url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?' + urlencode({
            'method': 'download', 'searchType': '13', 'marketType': market_type})
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=10) as response:
            rows.extend(parse_listing(response.read(5_000_000), market))
    return validate_snapshot({'updated_at': time.time(), 'rows': rows})


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
            message = f'국내 상장사 {len(rows):,}개 · KIND · 갱신 {date} (한국 시간)'
            if stale:
                message += ' · 이전 목록 사용 중'
        else:
            message = '국내 전체 목록 준비 중 · 현재 기본 종목만 표시합니다.'
        if _failed:
            message += ' · 갱신 연결 실패, 1시간 후 다음 이용 시 재시도'
        elif running:
            message += ' · 백그라운드 갱신 중 · 완료 후 자동 반영됩니다.'
        return rows, message
