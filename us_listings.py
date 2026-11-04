"""Daily Nasdaq Trader US exchange directory, retaining last successful cache."""
import csv
import io
from pathlib import Path
import re
from listing_cache import ListingCache, validate_timestamp
import time
from urllib.request import Request, urlopen

CACHE = Path(__file__).resolve().parent / '.cache' / 'us_listings.json'
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
    validate_timestamp(data)
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


_cache = ListingCache(CACHE, download_snapshot, validate_snapshot, '미국 상장 종목 · Nasdaq Trader')


def get_directory():
    return _cache.get()
