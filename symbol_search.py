"""Small offline alias list plus Yahoo search for other listed instruments."""
import re

COMMON = [
    ('대한광통신', '010170', '한국', 'Taihan Fiberoptics'),
    ('삼성전자', '005930', '한국', 'Samsung Electronics'),
    ('삼성전자우', '005935', '한국', 'Samsung Electronics preferred'),
    ('SK하이닉스', '000660', '한국', 'SK Hynix'),
    ('현대차', '005380', '한국', 'Hyundai Motor'),
    ('NAVER', '035420', '한국', '네이버'),
    ('카카오', '035720', '한국', 'Kakao'),
    ('LG에너지솔루션', '373220', '한국', 'LG Energy Solution'),
    ('애플', 'AAPL', '미국', 'Apple'),
    ('엔비디아', 'NVDA', '미국', 'NVIDIA'),
    ('마이크로소프트', 'MSFT', '미국', 'Microsoft'),
    ('테슬라', 'TSLA', '미국', 'Tesla'),
    ('아마존', 'AMZN', '미국', 'Amazon'),
    ('알파벳 A', 'GOOGL', '미국', 'Google Alphabet'),
    ('알파벳 C', 'GOOG', '미국', 'Google Alphabet'),
    ('메타', 'META', '미국', 'Meta Facebook'),
]


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


def search_symbols(query):
    query=query.strip()
    if not query or len(query)>80:
        return [], '종목명 또는 코드를 1~80자로 입력하세요.'
    compact=lambda value: re.sub(r'\s+', '',value).casefold()
    key=compact(query)
    local=[(name,code,market,'주식') for name,code,market,alias in COMMON
           if any(key in compact(v) for v in (name,code,alias))]
    if local:
        return local, '기본 종목 목록 · 이름과 코드를 확인하고 선택하세요.'
    import yfinance as yf
    try:
        results=normalize_quotes(yf.Search(query,max_results=20,news_count=0,timeout=10).quotes)
    except Exception:
        return [], '종목 검색 서버에 연결하지 못했습니다. 코드 직접 입력은 계속 사용할 수 있습니다.'
    return results, 'Yahoo Finance 검색 · 한국·미국 주식/ETF만 표시합니다. 결과가 없으면 영문명 또는 코드를 입력하세요.'


def render_symbol_search():
    import streamlit as st
    with st.expander('🔎 종목명으로 코드 찾기'):
        with st.form('symbol_lookup'):
            query=st.text_input('회사명 / 종목명 / 코드',placeholder='삼성전자, 엔비디아, Apple')
            search=st.form_submit_button('종목 검색')
        if search:
            results,message=search_symbols(query)
            st.session_state['symbol_matches']=results
            st.session_state['symbol_search_message']=message
            st.session_state.pop('symbol_choice',None)
        matches=st.session_state.get('symbol_matches',[])
        if 'symbol_search_message' in st.session_state:
            st.caption(st.session_state['symbol_search_message'])
        if matches:
            choice=st.selectbox('검색 결과',range(len(matches)),key='symbol_choice',
                format_func=lambda i:f'{matches[i][0]} · {matches[i][1]} · {matches[i][2]} · {matches[i][3]}')
            def apply():
                match=st.session_state['symbol_matches'][st.session_state['symbol_choice']]
                st.session_state['analysis_market']=match[2]
                st.session_state['analysis_ticker']=match[1]
            st.button('선택 종목 입력',on_click=apply)
            st.caption('선택 종목 입력 후 위의 분석하기를 누르세요.')
        elif search:
            st.info('검색 결과가 없습니다.')
