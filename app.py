"""Streamlit entry point: streamlit run app.py"""

import pandas as pd
import streamlit as st

from analysis import assess, completed_daily_bars, indicators, resample_bars
from charts import chart_html
from data import demo_prices, fetch_prices, read_csv, symbols

st.set_page_config(page_title="차트 분석 · Dual MACD", layout="wide")
st.title("한국·미국 주식 차트 분석")
st.caption("일봉·주봉 · MACD 6/19/9 + 19/39/9 · RSI · OBV · VRVP · 분석 결과는 자동 주문이나 수익 보장이 아닙니다.")
timeframe = st.radio("차트 주기", ["일봉", "주봉"], horizontal=True, key="chart_timeframe")


@st.cache_data(ttl=900, show_spinner=False)
def load_prices(ticker, market):
    """Five years of daily prices for daily and weekly analysis."""
    return fetch_prices(ticker, market, "NASDAQ")


with st.sidebar:
    st.header("분석 대상")
    with st.form("request"):
        mode = st.selectbox("데이터", ["온라인 시세", "CSV 업로드", "가상 데이터 체험"])
        market = st.selectbox("시장", ["한국", "미국"])
        ticker = st.text_input("한국 6자리 코드 / 미국 티커", "005930")
        uploaded = st.file_uploader("CSV: Date, Open, High, Low, Close, Volume", type="csv")
        submitted = st.form_submit_button("분석하기", type="primary")
    st.caption("한국: 005930(삼성전자), 000660(SK하이닉스)\n\n미국: AAPL·NVDA(NASDAQ), IBM(NYSE)")
    bins = st.select_slider("VRVP 가격 구간 수", options=[16, 24, 32, 48, 64], value=32)
    st.caption("CSV는 일봉을 입력하세요. 주봉은 일봉에서 합산합니다.")

if submitted:
    try:
        with st.spinner("일봉 데이터를 준비하고 분석하는 중입니다…"):
            if mode == "가상 데이터 체험":
                raw, provider, tv_symbol = demo_prices(), "가상 데이터 · 실제 종목 아님", None
            elif mode == "CSV 업로드":
                if uploaded is None:
                    raise ValueError("CSV 파일을 선택하세요.")
                _, tv_symbol = symbols(ticker, market)
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
try:
    frame = indicators(resample_bars(daily, market, timeframe))
except ValueError as error:
    st.error(str(error))
    st.stop()
period = "일" if timeframe == "일봉" else "주"
last, prev = frame.iloc[-1], frame.iloc[-2]
signal = assess(frame)
st.subheader("가상 데이터 체험" if tv_symbol is None else f"{market} · {ticker.upper()}")
st.caption(f"데이터: {provider} | 마지막 분석 {timeframe}: {frame.index[-1]:%Y-%m-%d} | {len(frame)}개 {timeframe}")
if removed:
    st.caption(f"당일 장중·미래 데이터 {removed}개는 분석에서 제외했습니다.")
st.caption("당일 일봉은 한국 16:00 / 미국 동부 17:00 이후에만 포함합니다. 제공처 지연·휴장·반일장은 별도로 확인하세요. 실시간 알림이 아니라 실행 시점의 마지막 일봉 분석입니다.")
if timeframe == "주봉":
    st.caption("주봉은 월~금 일봉을 합산하고 금요일을 날짜로 표시합니다. 해당 시장 금요일 마감 대기 시각 전에는 이번 주를 제외합니다. 휴일 주간도 금요일까지 기다리며 첫 불완전 주는 제외합니다.")
if tv_symbol is None:
    st.warning("현재 모든 수치와 신호는 설명용 가상 데이터입니다. 실제 종목의 투자 판단에 사용하지 마세요.")

notify = st.error if signal["level"] == "위험" else st.warning if signal["level"] == "주의" else st.info
notify(f"매도 검토 경고: {signal['level']} · {timeframe} MACD(19,39,9)")
sell_events = frame.loc[frame.MACD19SellSignal]
if bool(last.MACD19SellSignal):
    st.warning(f"▼ 새 매도 주의 시그널 · {frame.index[-1]:%Y-%m-%d}: MACD 0선 상향 돌파 후 양수 구간에서 오실레이터가 음수로 전환했습니다.")
with st.expander("경고 근거 보기"):
    for reason in signal["reasons"]:
        st.write("• " + reason)

columns = st.columns(4)
columns[0].metric(("종가 (KRW)" if market == "한국" else "종가 (USD)") if tv_symbol else "가상 종가", f"{last.Close:,.2f}", f"{(last.Close / prev.Close - 1) * 100:+.2f}%")
columns[1].metric("MACD (19,39)", f"{last.MACD:,.4f}", f"{last.MACD - prev.MACD:+.4f}", delta_color="off")
columns[2].metric("시그널 (9)", f"{last.Signal:,.4f}")
columns[3].metric("직전 20봉 평균 대비 거래량", "계산 불가" if pd.isna(last.VolumeRatio) else f"{last.VolumeRatio:.2f}배")

st.subheader(f"{timeframe} 종합 차트")
st.caption("기본 최근 60봉 · 드래그로 이동 · 휠/도구막대로 확대 · 더블클릭 초기화 · 선/사각형 그리기 · 이미지 저장. 모든 지표의 시간축이 함께 움직입니다.")
st.caption("우측 VRVP는 표시 구간의 봉 데이터로 추정한 거래량 분포입니다. 노란 막대는 추정 POC입니다.")
st.caption("분홍색 ▼: MACD(19,39,9) 0선 상향 돌파 후 양수 유지 중 오실레이터(MACD−시그널선)가 음수로 바뀐 봉. 가격·MACD 패널에 함께 표시합니다.")
st.iframe(chart_html(frame, timeframe, bins), height=1490)
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
    for window in (20, 60, 200):
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
