"""KIND listed-company directory with a non-blocking, daily disk cache."""
from html.parser import HTMLParser
from pathlib import Path
import re
from listing_cache import ListingCache, validate_timestamp
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MARKETS = {'코스피': 'stockMkt', '코스닥': 'kosdaqMkt', '코넥스': 'konexMkt'}
CACHE = Path(__file__).resolve().parent / '.cache' / 'korean_listings.json'


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
    validate_timestamp(data)
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


_cache = ListingCache(CACHE, download_snapshot, validate_snapshot, '국내 상장사 · KIND')


def get_directory():
    return _cache.get()
