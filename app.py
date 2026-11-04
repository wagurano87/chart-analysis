"""Streamlit entry point: streamlit run app.py"""

import pandas as pd
import streamlit as st

from analysis import MA_WINDOWS, assess, completed_daily_bars, indicators, resample_bars
from crypto_data import CRYPTO_MARKETS, crypto_symbol, quote_currency, fetch_crypto, completed_four_hour_bars
from symbol_search import render_symbol_picker
from market_data import demo_prices, fetch_prices, read_csv, symbols, stock_four_hour

st.set_page_config(page_title="차트 분석 · Dual MACD", layout="wide")
st.title("주식·코인 차트 분석")
st.caption("일봉·주봉 · MACD 6/19/9 + 19/39/9 · RSI · OBV · VRVP · 분석 결과는 자동 주문이나 수익 보장이 아닙니다.")
st.markdown("""<style>
[data-testid="stMainBlockContainer"] {padding-top:3.5rem;padding-bottom:2rem;}
[data-testid="stMain"] h1 {font-size:1.65rem;}
[data-testid="stMain"] h3 {font-size:1.2rem;}
[data-testid="stRadio"] [role="radiogroup"] {gap:6px;}
[data-testid="stRadio"] label {border:1px solid #475569;border-radius:5px;padding:6px 16px;}
[data-testid="stRadio"] label:has(input:checked) {background:#1d4ed8;border-color:#60a5fa;color:white;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner=False)
def load_prices(ticker, market):
    """Five years of daily prices for daily and weekly analysis."""
    return fetch_prices(ticker, market, "NASDAQ")


st.session_state.setdefault("analysis_ticker", "005930")


def open_favorite(symbol):
    st.session_state['analysis_mode'] = '온라인 시세'
    st.session_state['analysis_market'] = '바이낸스'
    st.session_state['analysis_ticker'] = symbol
    st.session_state['favorite_requested'] = True
    st.session_state['symbol_sync'] = True
    st.session_state['symbol_pending'] = False


st.caption('바이낸스 현물 빠른 조회 · USDT 기준')
favorites = st.columns(2)
favorites[0].button('₿ 비트코인', key='favorite_btc', on_click=open_favorite,
                    args=('BTCUSDT',), width='stretch')
favorites[1].button('◆ 이더리움', key='favorite_eth', on_click=open_favorite,
                    args=('ETHUSDT',), width='stretch')


with st.sidebar:
    st.header("분석 대상")
    mode = st.selectbox("데이터", ["온라인 시세", "CSV 업로드", "가상 데이터 체험"], key="analysis_mode")
    render_symbol_picker()
    market = st.selectbox("시장", ["한국", "미국", "바이낸스", "업비트"], key="analysis_market")
    ticker = st.session_state['analysis_ticker']
    uploaded = st.file_uploader("CSV: Date, Open, High, Low, Close, Volume", type="csv")
    submitted = st.button("분석하기", type="primary", disabled=st.session_state.get('symbol_pending', False))
    st.caption("바이낸스: BTCUSDT, ETHUSDT · 업비트: KRW-BTC, KRW-ETH (현물)")
    st.caption("한국: 005930(삼성전자), 000660(SK하이닉스)\n\n미국: AAPL·NVDA(NASDAQ), IBM(NYSE)")
    bins = st.select_slider("VRVP 가격 구간 수", options=[16, 24, 32, 48, 64], value=32)
    with st.expander('ADX·ADXR·DI 설정'):
        di_length = int(st.number_input('Length (DI)', min_value=2, max_value=100, value=14))
        adx_threshold = int(st.number_input('Threshold', min_value=0, max_value=100, value=20))
        adx_length = int(st.number_input('Length ADX', min_value=2, max_value=100, value=14))
        adxr_length = int(st.number_input('Length ADXR', min_value=1, max_value=100, value=14))
    st.caption("CSV는 일봉을 입력하세요. 주봉은 일봉에서 합산합니다.")

favorite_requested = st.session_state.pop("favorite_requested", False)
if submitted or favorite_requested:
    try:
        with st.spinner("일봉 데이터를 준비하고 분석하는 중입니다…"):
            if mode == "가상 데이터 체험":
                raw, provider, tv_symbol = demo_prices(), "가상 데이터 · 실제 종목 아님", None
            elif mode == "CSV 업로드":
                if uploaded is None:
                    raise ValueError("CSV 파일을 선택하세요.")
                tv_symbol = crypto_symbol(ticker, market) if market in CRYPTO_MARKETS else symbols(ticker, market)[1]
                raw, provider = read_csv(uploaded), "사용자 CSV · 수정주가 여부는 파일 제공 기준"
            else:
                raw, provider, tv_symbol = load_prices(ticker, market)
            bars = completed_daily_bars(raw, market)
            removed = len(raw) - len(bars)
            st.session_state["analysis_result"] = (bars, provider, tv_symbol, market, ticker, removed, mode)
    except Exception as error:
        st.session_state.pop("analysis_result", None)
        st.error(str(error))

if "analysis_result" not in st.session_state:
    st.info("왼쪽에서 종목과 데이터 방식을 선택하고 ‘분석하기’를 누르세요. 외부 연결 없이 확인하려면 ‘가상 데이터 체험’을 선택하세요.")
    st.stop()

daily, provider, tv_symbol, market, ticker, removed, mode = st.session_state["analysis_result"]
# Fill this container after calculation so the period control sits directly above the chart.
summary = st.container()
period_options = ["일봉", "주봉", "4시간봉"]
if st.session_state.get('chart_timeframe') not in period_options:
    st.session_state['chart_timeframe'] = '일봉'
timeframe = st.radio("차트 주기", period_options, horizontal=True,
                     key="chart_timeframe", label_visibility="collapsed")
try:
    if timeframe == '4시간봉':
        if mode != '온라인 시세':
            st.info('4시간봉은 온라인 시세에서 지원합니다. 데이터 방식을 온라인 시세로 바꾸고 분석하기를 누르세요.')
            st.stop()
        @st.cache_data(ttl=300, show_spinner=False)
        def load_four_hour(ticker, market, source):
            if market not in CRYPTO_MARKETS:
                return stock_four_hour(source, market), source, source
            return fetch_crypto(ticker, market, interval='4h')
        with st.spinner('4시간봉을 불러오는 중입니다…'):
            intraday, provider, tv_symbol = load_four_hour(ticker, market, provider)
        completed = completed_four_hour_bars(intraday) if market in CRYPTO_MARKETS else intraday
        removed = len(intraday)-len(completed)
        frame = indicators(completed, di_length, adx_length, adxr_length)
    else:
        frame = indicators(resample_bars(daily, market, timeframe), di_length, adx_length, adxr_length)
except (ValueError, RuntimeError) as error:
    st.error(str(error))
    st.stop()
period = "일" if timeframe == "일봉" else "주" if timeframe == "주봉" else " × 4시간"
last, prev = frame.iloc[-1], frame.iloc[-2]
signal = assess(frame)
with summary:
    st.subheader("가상 데이터 체험" if tv_symbol is None else f"{market} · {ticker.upper()}")
    excluded_prices = daily.attrs.get('excluded_price_dates', []) if timeframe != '4시간봉' else []
    if excluded_prices:
        st.warning(f"제공처의 잘못된 가격 데이터 {len(excluded_prices)}개 봉을 제외했습니다. 누락 봉 때문에 지표가 원본과 달라질 수 있습니다.")
        with st.expander('제외된 시세 날짜 확인'):
            st.write(', '.join(excluded_prices))
    if timeframe != '4시간봉' and daily.attrs.get('rounded_price_rows', 0):
        st.caption(f"수정주가 계산의 미세 오차 {daily.attrs['rounded_price_rows']}개 봉을 보정했습니다.")
    st.caption(f"{provider} · {timeframe} · 마지막 완료 봉 {frame.index[-1]:%Y-%m-%d %H:%M} · {len(frame):,}개 봉")
    if timeframe == "4시간봉":
        st.caption("코인 4시간봉은 UTC 시작 시각입니다(한국 +9시간). 진행 중 봉은 제외합니다." if market in CRYPTO_MARKETS else "주식 4시간봉은 거래소 현지 시각·정규장 시작 기준입니다. 마지막 봉은 4시간보다 짧을 수 있으며 당일 데이터는 마감 확인 이후 표시합니다.")
    if tv_symbol is None:
        st.warning("현재 모든 수치와 신호는 설명용 가상 데이터입니다. 실제 종목의 투자 판단에 사용하지 마세요.")
    notify = st.error if signal["level"] == "위험" else st.warning if signal["level"] == "주의" else st.info
    notify(f"매도 검토 경고: {signal['level']} · {timeframe} MACD(19,39,9)")
    if bool(last.MACD19SellSignal):
        st.warning(f"▼ 새 매도 주의 시그널 · {frame.index[-1]:%Y-%m-%d}: MACD 0선 상향 돌파 후 양수 구간에서 오실레이터가 음수로 전환했습니다.")

from charts import chart_html

st.iframe(chart_html(frame, timeframe, bins, adx_threshold), height=1510)
st.caption(f'ADX·ADXR·DI 설정: DI {di_length} / ADX {adx_length} / ADXR {adxr_length} / 기준선 {adx_threshold}. +DI·−DI는 방향, ADX·ADXR은 추세 강도 참고 지표이며 기존 매도 경고와 독립적입니다.')
st.caption("▲ DI 매수 시그널 · ▼ 매도 주의 시그널 · 우측 VRVP는 표시 구간의 OHLCV로 추정한 거래량 분포이며 노란 막대는 추정 POC입니다.")
sell_events = frame.loc[frame.MACD19SellSignal]
with st.expander("차트 조작·데이터 안내"):
    st.write("차트 바로 위에서 일봉·주봉·4시간봉을 선택하세요. 최근 60봉·180봉·전체 버튼으로 범위를 바꿀 수 있습니다. 이동·확대·추세선·사각형·지우기·PNG 저장 도구를 제공합니다. 그린 선·사각형은 클릭해 선택한 뒤 Delete 키 또는 선택 삭제 버튼으로 삭제합니다. 방금 그린 도형은 자동 선택되며 Esc로 선택을 해제합니다. 휠로 확대하고, 기본 보기로 최근 60봉에 돌아옵니다.")
    st.write("고저점 표시 버튼으로 차트 위 최고·최저 정보 카드를 켜거나 끌 수 있습니다. 캔들 위에는 고저점 설명을 겹쳐 표시하지 않습니다.")
    st.write("모바일 도형 삭제: 도형 선택 목록에서 피보나치·추세선 등을 고른 뒤 선택 삭제를 누르세요. 도형 전체 삭제는 직접 그린 도형만 한 번에 지웁니다. 한 번 그린 뒤에는 자동으로 이동 모드로 돌아옵니다.")
    st.write("모바일: 이동 도구에서 차트 안에 두 손가락을 대고 벌리면 확대, 모으면 축소됩니다. 한 손가락은 페이지 스크롤입니다. 그리기 도구 사용 후에는 이동을 선택하세요.")
    st.write("피보나치: 버튼 선택 후 가격 차트에서 시작점부터 끝점까지 드래그하세요. 끝점 0%·시작점 100% 기준으로 되돌림 가격을 표시합니다. 점선 기준선을 선택한 뒤 Delete를 누르면 전체 삭제됩니다. 클릭한 가격을 사용하며 고가·저가 자동 맞춤은 하지 않습니다.")
    st.write("십자선을 움직이면 모든 패널의 같은 날짜와 OHLC·지표 수치를 함께 확인할 수 있습니다. MA 버튼으로 이동평균선을 숨기거나 표시합니다. MACD 막대는 양수/음수와 직전 봉 대비 증가/감소를 색으로 구분합니다.")
    st.write("초록색 ▲: 직전 봉 +DI ≤ −DI, 현재 완료 봉 +DI > −DI인 상향 돌파. 가격·DI 패널에 함께 표시하며 ADX 기준값과 무관하게 표시합니다.")
    st.write("분홍색 ▼: MACD(19,39,9) 0선 상향 돌파 후 양수 유지 중 오실레이터(MACD−시그널선)가 음수로 바뀐 봉. 가격·MACD 패널에 함께 표시합니다.")
    if removed:
        st.caption(f"당일 장중·미래 데이터 {removed}개는 분석에서 제외했습니다.")
    if market in CRYPTO_MARKETS:
        st.caption("코인 일봉은 UTC 00:00~24:00(한국 09:00 기준), 주봉은 UTC 월~일입니다. 진행 중인 일봉·주봉은 제외합니다. 거래 없는 날짜는 거래소가 제공하지 않을 수 있습니다.")
    else:
        st.caption("당일 일봉은 한국 16:00 / 미국 동부 17:00 이후에만 포함합니다. 제공처 지연·휴장·반일장은 별도로 확인하세요. 실시간 알림이 아니라 실행 시점의 마지막 완료 봉 분석입니다.")
    if timeframe == "주봉" and market not in CRYPTO_MARKETS:
        st.caption("주봉은 월~금 일봉을 합산하고 금요일을 날짜로 표시합니다. 해당 시장 금요일 마감 대기 시각 전에는 이번 주를 제외합니다. 휴일 주간도 금요일까지 기다리며 첫 불완전 주는 제외합니다.")
with st.expander("경고 근거 보기"):
    for reason in signal["reasons"]:
        st.write("• " + reason)

columns = st.columns(4)
columns[0].metric((f"종가 ({quote_currency(ticker,market)})" if market in CRYPTO_MARKETS else "종가 (KRW)" if market == "한국" else "종가 (USD)") if tv_symbol else "가상 종가", f"{last.Close:,.2f}", f"{(last.Close / prev.Close - 1) * 100:+.2f}%")
columns[1].metric("MACD (19,39)", f"{last.MACD:,.4f}", f"{last.MACD - prev.MACD:+.4f}", delta_color="off")
columns[2].metric("시그널 (9)", f"{last.Signal:,.4f}")
columns[3].metric("직전 20봉 평균 대비 거래량", "계산 불가" if pd.isna(last.VolumeRatio) else f"{last.VolumeRatio:.2f}배")

with st.expander(f"오실레이터 음전환 시그널 내역 · {len(sell_events)}회"):
    if sell_events.empty:
        st.write("조회한 데이터에서 해당 조건이 발생하지 않았습니다.")
    else:
        st.dataframe(sell_events[['Close', 'MACD', 'Signal', 'Histogram']].sort_index(ascending=False)
                     .rename(columns={'Close':'종가','Signal':'시그널선','Histogram':'오실레이터'})
                     .rename_axis('일자'), width='stretch')
    st.caption("조회 구간에서 확인된 0선 상향 돌파 이후만 계산합니다. MACD가 0 이하가 되면 조건을 초기화합니다. 음수 유지 중에는 반복 표시하지 않으며, 다시 0 이상으로 회복 후 음전환하면 재표시합니다. 주봉도 동일한 규칙입니다.")
indicator_columns = st.columns(3)
indicator_columns[0].metric("MACD (6,19,9)", f"{last.MACD6:.4f}")
indicator_columns[1].metric("RSI (14)", f"{last.RSI:.2f}")
indicator_columns[2].metric("OBV", f"{last.OBV:,.0f}")
st.caption("RSI: Wilder 방식, 30·70 기준선. OBV: 첫 봉 0에서 시작해 종가 상승 시 거래량을 더하고 하락 시 뺍니다. 새 지표는 표시용이며 경고 판정은 기존 MACD(19,39,9) 규칙을 사용합니다.")

with st.expander("거래량·이동평균 상세 분석"):
    st.subheader("거래량과 가격 흐름")
    if signal["distribution"]:
        st.write("종가가 하락하면서 거래량이 직전 20봉 평균의 1.5배 이상입니다. 매도 압력 가능성에 주의하세요. 거래 주체의 의도까지 확인한 것은 아닙니다.")
    elif pd.isna(last.VolumeRatio):
        st.write("비교 기간의 평균 거래량이 0이어서 배율을 계산할 수 없습니다.")
    elif last.VolumeRatio >= 1.5 and last.Close > prev.Close:
        st.write("종가 상승과 거래량 증가가 동반됐습니다. 추세 지속 여부를 다음 봉과 함께 확인하세요.")
    elif last.VolumeRatio < .5:
        st.write("거래량이 평소의 절반 미만입니다. 가격 움직임의 참여 강도가 약할 수 있습니다.")
    else:
        st.write("1.5배 이상 거래량 증가를 동반한 종가 하락 조건은 발생하지 않았습니다.")
    for window in MA_WINDOWS:
        average = last[f"MA{window}"]
        st.write(f"{window}{period} 이동평균: 데이터 부족" if pd.isna(average) else f"{window}{period} 이동평균 {average:,.2f} · 종가는 이동평균 {'위' if last.Close >= average else '아래'}")


with st.expander("위험 신호 계산 기준과 한계"):
    st.markdown("""- MACD = EMA(종가,19) − EMA(종가,39), 시그널 = EMA(MACD,9).
- **주의:** MACD선이 직전 봉보다 하락하거나 시그널선 아래에 있는 경우, 또는 거래량 증가를 동반한 종가 하락.
- **위험:** 최신 봉 데드크로스, 최신 봉 0선 하향 돌파, 또는 MACD 하락과 거래량 증가를 동반한 종가 하락이 동시에 발생.
- 거래량 증가 기준: 최신 봉 거래량 ÷ **해당 봉 제외 직전 20봉 평균** ≥ 1.5.
- MACD 3개 봉 연속 하락과 히스토그램 감소는 추가 설명으로 표시합니다.
- 횡보장에서는 거짓 신호가 생기고 추세 전환을 늦게 알릴 수 있습니다. 신호의 수익성·정확도는 백테스트하지 않았습니다.
- 앱을 다시 분석할 때만 신호가 갱신됩니다. 푸시·텔레그램 알림과 자동 매도는 없습니다.""")
st.download_button("분석 데이터 CSV 저장", frame.to_csv(index_label="Date").encode("utf-8-sig"), file_name=f"chart-analysis-{timeframe}.csv", mime="text/csv")

from fundamentals import render_fundamentals
if market not in CRYPTO_MARKETS:
    render_fundamentals(provider, mode)
else:
    st.caption("코인은 기업 분기 재무제표·PEG 분석 대상이 아닙니다. 거래량은 기준 코인 수량입니다.")
