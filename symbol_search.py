"""Searchable Korean/US directories, common aliases and remote fallback."""
import re
from korean_listings import get_directory
from us_listings import get_directory as get_us_directory

COMMON = [
    ('엘앤씨바이오', '290650', '한국', 'L&C Bio 엘앤씨 바이오'),
    ('LG전자', '066570', '한국', 'LG Electronics 엘지전자'),
    ('LG전자우', '066575', '한국', 'LG Electronics preferred 엘지전자우'),
    ('대한광통신', '010170', '한국', 'Taihan Fiberoptics'),
    ('삼성전자', '005930', '한국', 'Samsung Electronics'),
    ('삼성전자우', '005935', '한국', 'Samsung Electronics preferred'),
    ('SK하이닉스', '000660', '한국', 'SK Hynix'),
    ('현대차', '005380', '한국', 'Hyundai Motor'),
    ('NAVER', '035420', '한국', '네이버'),
    ('카카오', '035720', '한국', 'Kakao'),
    ('LG에너지솔루션', '373220', '한국', 'LG Energy Solution'),
    ('인텔', 'INTC', '미국', 'Intel'),
    ('애플', 'AAPL', '미국', 'Apple'),
    ('엔비디아', 'NVDA', '미국', 'NVIDIA'),
    ('마이크로소프트', 'MSFT', '미국', 'Microsoft'),
    ('테슬라', 'TSLA', '미국', 'Tesla'),
    ('아마존', 'AMZN', '미국', 'Amazon'),
    ('알파벳 A', 'GOOGL', '미국', 'Google Alphabet'),
    ('알파벳 C', 'GOOG', '미국', 'Google Alphabet'),
    ('메타', 'META', '미국', 'Meta Facebook'),
]


# 외부 검색 결과 중 지원하는 시장과 종목 종류만 골라 코드·이름 형태를 통일합니다.
def normalize_quotes(quotes):
    results=[]
    seen=set()
    for quote in quotes:
        symbol=str(quote.get('symbol','')).upper()
        exchange=quote.get('exchange')
        if quote.get('quoteType') not in {'EQUITY','ETF'}:
            continue
        if re.fullmatch(r'\d{6}\.(KS|KQ)',symbol):
            market, code='한국',symbol[:6]
        elif exchange in {'NMS','NGM','NCM','NYQ','ASE','PCX','BTS'} and re.fullmatch(r'[A-Z][A-Z0-9.-]{0,12}',symbol):
            market,code='미국',symbol
        else:
            continue
        if (market,code) in seen:
            continue
        seen.add((market,code))
        results.append((quote.get('longname') or quote.get('shortname') or code,code,market,quote.get('quoteType')))
    return results


# 기본 별칭과 국내·미국 목록을 먼저 함께 검색하고, 없을 때 Yahoo 검색을 시도합니다. 같은 시장·코드는 중복 제거합니다.
def search_symbols(query):
    query=query.strip()
    if not query or len(query)>80:
        return [], '종목명 또는 코드를 1~80자로 입력하세요.'
    compact=lambda value: re.sub(r'\s+', '',value).casefold()
    key=compact(query)
    local=[(name,code,market,'주식') for name,code,market,alias in COMMON
           if any(key in compact(v) for v in (name,code,alias))]
    directory, _ = get_directory()
    domestic = [(row['name'], row['code'], '한국', row['exchange']) for row in directory
                if key in compact(row['name']) or key in row['code']]
    us_directory, _ = get_us_directory()
    us_matches = [(row['name'], row['code'], '미국', row['kind']) for row in us_directory
                  if key in compact(row['name']) or key in compact(row['code'])]
    matches = {}
    for match in local + domestic + us_matches:
        matches.setdefault((match[2], match[1]), match)
    if matches:
        return list(matches.values()), '종목 목록 · 이름과 코드를 확인하고 선택하세요.'
    import yfinance as yf
    try:
        results=normalize_quotes(yf.Search(query,max_results=20,news_count=0,timeout=10).quotes)
    except Exception:
        return [], '종목 검색 서버에 연결하지 못했습니다. 코드 직접 입력은 계속 사용할 수 있습니다.'
    return results, 'Yahoo Finance 검색 · 한국·미국 주식/ETF만 표시합니다. 결과가 없으면 영문명 또는 코드를 입력하세요.'


# Streamlit 검색 입력창과 도움말을 만듭니다. 후보 선택 시 시장과 코드를 함께 저장합니다.
def render_symbol_picker():
    """One searchable input for aliases, codes and remote search results."""
    import streamlit as st
    entries = {f'{name} · {alias} · {code} · {market}': (code, market)
               for name, code, market, alias in COMMON}
    directory, _ = get_directory()
    known = {code for _, code, market, _ in COMMON if market == '한국'}
    entries.update({f"{row['name']} · {row['code']} · 한국 · {row['exchange']}": (row['code'], '한국')
                    for row in directory if row['code'] not in known})
    us_directory, _ = get_us_directory()
    known_us = {code for _, code, market, _ in COMMON if market == '미국'}
    entries.update({f"{row['name']} · {row['code']} · 미국 · {row['exchange']} · {row['kind']}": (row['code'], '미국')
                    for row in us_directory if row['code'] not in known_us})
    entries.update({f'{code} · {market}': (code, market)
                    for code, market in [('BTCUSDT', '바이낸스'), ('ETHUSDT', '바이낸스'),
                                         ('KRW-BTC', '업비트'), ('KRW-ETH', '업비트')]})
    entries = {**st.session_state.get('symbol_extra_entries', {}), **entries}
    current = (st.session_state.get('analysis_ticker', '005930'),
               st.session_state.get('analysis_market', '한국'))
    default = next((label for label, pair in entries.items() if pair == current), None)
    if default is None:
        default = f'{current[0]} · {current[1]}'
        entries[default] = current
    if st.session_state.pop('symbol_sync', False) or 'symbol_entry' not in st.session_state:
        st.session_state['symbol_entry'] = default

    def select():
        value = st.session_state['symbol_entry'].strip()
        st.session_state.pop('symbol_picker_message', None)
        if value in entries:
            code, market = entries[value]
        else:
            if re.fullmatch(r'(?:[A-Za-z0-9]+USDT|KRW-[A-Za-z0-9]+)', value, re.I):
                matches, message = [], ''
            else:
                matches, message = search_symbols(value)
            if matches:
                extras = {f'{name} · {code} · {market}': (code, market)
                          for name, code, market, _ in matches}
                st.session_state['symbol_extra_entries'] = extras
                st.session_state['symbol_picker_message'] = '검색된 후보 목록에서 종목을 선택하세요.'
                st.session_state['symbol_pending'] = True
                return
            code = value.upper()
            if re.fullmatch(r'\d{6}', code):
                market = '한국'
            elif re.fullmatch(r'KRW-[A-Z0-9]+', code):
                market = '업비트'
            elif re.fullmatch(r'[A-Z0-9]+USDT', code):
                market = '바이낸스'
            elif re.fullmatch(r'[A-Z][A-Z0-9.-]{0,12}', code):
                market = '미국'
            else:
                st.session_state['symbol_picker_message'] = message
                st.session_state['symbol_pending'] = True
                return
        st.session_state['analysis_ticker'] = code
        st.session_state['analysis_market'] = market
        st.session_state['symbol_pending'] = False
        st.session_state['symbol_sync'] = True

    st.selectbox('종목명 / 코드 / 티커 / 코인 거래쌍', list(entries),
                 key='symbol_entry', accept_new_options=True, on_change=select,
                 placeholder='삼성전자, 인텔, AAPL, BTCUSDT',
                 help='이름을 입력해 후보를 선택하세요. 목록에 없는 종목은 입력 후 Enter로 검색합니다.')
    @st.fragment(run_every='30s')
    def directory_status():
        latest, message = get_directory()
        latest_us, us_message = get_us_directory()
        if latest != directory or latest_us != us_directory:
            st.rerun()
        st.caption('종목 목록 상태', help=f'**국내**\n\n{message}\n\n**미국**\n\n{us_message}')
        if st.button('목록 갱신 확인', key='check_listing_refresh'):
            st.rerun()

    directory_status()
    if st.session_state.get('symbol_picker_message'):
        st.caption(st.session_state['symbol_picker_message'])
    st.caption(f"선택 종목: {st.session_state['analysis_ticker']} · {st.session_state.get('analysis_market', '한국')}")
