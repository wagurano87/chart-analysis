"""Streamlit entry point: streamlit run app.py"""
import json

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from analysis import assess, completed_daily_bars, indicators
from data import demo_prices, fetch_prices, read_csv, symbols

st.set_page_config(page_title="차트 분석 · MACD 19/39/9", layout="wide")
st.title("한국·미국 주식 차트 분석")
st.caption("일봉 · MACD(19, 39, 9) · 거래량 · 분석 결과는 자동 주문이나 수익 보장이 아닙니다.")


@st.cache_data(ttl=900, show_spinner=False)
def load_prices(ticker, market, exchange):
    return fetch_prices(ticker, market, exchange)


with st.sidebar:
    st.header("분석 대상")
    with st.form("request"):
        mode = st.selectbox("데이터", ["온라인 시세", "CSV 업로드", "가상 데이터 체험"])
        market = st.selectbox("시장", ["한국", "미국"])
        ticker = st.text_input("한국 6자리 코드 / 미국 티커", "005930")
        exchange = st.selectbox("미국 TradingView 거래소 (미국 선택 시 적용)", ["NASDAQ", "NYSE", "AMEX"])
        uploaded = st.file_uploader("CSV: Date, Open, High, Low, Close, Volume", type="csv")
        submitted = st.form_submit_button("분석하기", type="primary")
    st.caption("한국: 005930(삼성전자), 000660(SK하이닉스)\n\n미국: AAPL·NVDA(NASDAQ), IBM(NYSE)")
    st.caption("일봉만 분석합니다. 미국 종목은 TradingView 거래소를 정확히 선택하세요.")

if submitted:
    try:
        with st.spinner("일봉 데이터를 준비하고 분석하는 중입니다…"):
            if mode == "가상 데이터 체험":
                raw, provider, tv_symbol = demo_prices(), "가상 데이터 · 실제 종목 아님", None
            elif mode == "CSV 업로드":
                if uploaded is None:
                    raise ValueError("CSV 파일을 선택하세요.")
                _, tv_symbol = symbols(ticker, market, exchange)
                raw, provider = read_csv(uploaded), "사용자 CSV · 수정주가 여부는 파일 제공 기준"
            else:
                raw, provider, tv_symbol = load_prices(ticker, market, exchange)
            bars = completed_daily_bars(raw, market)
            removed = len(raw) - len(bars)
            result = indicators(bars)
            st.session_state["analysis_result"] = (result, provider, tv_symbol, market, ticker, removed, mode)
    except Exception as error:
        st.session_state.pop("analysis_result", None)
        st.error(str(error))

if "analysis_result" not in st.session_state:
    st.info("왼쪽에서 종목과 데이터 방식을 선택하고 ‘분석하기’를 누르세요. 외부 연결 없이 확인하려면 ‘가상 데이터 체험’을 선택하세요.")
    st.stop()

frame, provider, tv_symbol, market, ticker, removed, mode = st.session_state["analysis_result"]
last, prev = frame.iloc[-1], frame.iloc[-2]
signal = assess(frame)
st.subheader("가상 데이터 체험" if tv_symbol is None else f"{market} · {ticker.upper()}")
st.caption(f"데이터: {provider} | 마지막 분석 일봉: {frame.index[-1]:%Y-%m-%d} | {len(frame)}개 일봉")
if removed:
    st.caption(f"당일 장중·미래 데이터 {removed}개는 분석에서 제외했습니다.")
st.caption("당일 일봉은 한국 16:00 / 미국 동부 17:00 이후에만 포함합니다. 제공처 지연·휴장·반일장은 별도로 확인하세요. 실시간 알림이 아니라 실행 시점의 마지막 일봉 분석입니다.")
if tv_symbol is None:
    st.warning("현재 모든 수치와 신호는 설명용 가상 데이터입니다. 실제 종목의 투자 판단에 사용하지 마세요.")

notify = st.error if signal["level"] == "위험" else st.warning if signal["level"] == "주의" else st.info
notify(f"매도 검토 경고: {signal['level']}")
for reason in signal["reasons"]:
    st.write("• " + reason)

columns = st.columns(4)
columns[0].metric(("종가 (KRW)" if market == "한국" else "종가 (USD)") if tv_symbol else "가상 종가", f"{last.Close:,.2f}", f"{(last.Close / prev.Close - 1) * 100:+.2f}%")
columns[1].metric("MACD (19,39)", f"{last.MACD:,.4f}", f"{last.MACD - prev.MACD:+.4f}", delta_color="off")
columns[2].metric("시그널 (9)", f"{last.Signal:,.4f}")
columns[3].metric("직전 20일 평균 대비 거래량", "계산 불가" if pd.isna(last.VolumeRatio) else f"{last.VolumeRatio:.2f}배")

st.subheader("거래량과 가격 흐름")
if signal["distribution"]:
    st.write("종가가 하락하면서 거래량이 직전 20일 평균의 1.5배 이상입니다. 매도 압력 가능성에 주의하세요. 거래 주체의 의도까지 확인한 것은 아닙니다.")
elif pd.isna(last.VolumeRatio):
    st.write("비교 기간의 평균 거래량이 0이어서 배율을 계산할 수 없습니다.")
elif last.VolumeRatio >= 1.5 and last.Close > prev.Close:
    st.write("종가 상승과 거래량 증가가 동반됐습니다. 추세 지속 여부를 다음 일봉과 함께 확인하세요.")
elif last.VolumeRatio < .5:
    st.write("거래량이 평소의 절반 미만입니다. 가격 움직임의 참여 강도가 약할 수 있습니다.")
else:
    st.write("1.5배 이상 거래량 증가를 동반한 종가 하락 조건은 발생하지 않았습니다.")
for window in (20, 60, 200):
    average = last[f"MA{window}"]
    st.write(f"{window}일 이동평균: 데이터 부족" if pd.isna(average) else f"{window}일 이동평균 {average:,.2f} · 종가는 이동평균 {'위' if last.Close >= average else '아래'}")

st.subheader("분석에 사용한 일봉 · MACD · 거래량")
st.caption("아래 차트와 위험 신호는 같은 데이터로 계산합니다. Yahoo 온라인 데이터의 가격은 배당·분할 조정값입니다.")
display = frame.tail(180)
fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[.5, .3, .2], vertical_spacing=.04)
fig.add_trace(go.Candlestick(x=display.index, open=display.Open, high=display.High, low=display.Low, close=display.Close, name="일봉"), row=1, col=1)
for window in (20, 60, 200):
    fig.add_trace(go.Scatter(x=display.index, y=display[f"MA{window}"], name=f"MA{window}"), row=1, col=1)
for name in ("MACD", "Signal"):
    fig.add_trace(go.Scatter(x=display.index, y=display[name], name=name), row=2, col=1)
fig.add_trace(go.Bar(x=display.index, y=display.Histogram, name="Histogram", marker_color=["#16a34a" if x >= 0 else "#dc2626" for x in display.Histogram]), row=2, col=1)
fig.add_trace(go.Bar(x=display.index, y=display.Volume, name="거래량"), row=3, col=1)
fig.add_trace(go.Scatter(x=display.index, y=display.VolumeAvg20, name="직전 20일 거래량 평균"), row=3, col=1)
fig.update_layout(height=850, xaxis_rangeslider_visible=False, margin=dict(t=30, b=20))
st.plotly_chart(fig, width="stretch")

if tv_symbol:
    st.subheader("TradingView 차트")
    st.caption("외부 TradingView 위젯입니다. 시세 제공처·수정주가·갱신 시점 차이로 위 분석값과 다를 수 있습니다. 위젯의 지표를 바꿔도 본 앱의 MACD(19,39,9) 계산은 바뀌지 않습니다.")
    config = json.dumps({"autosize": True, "symbol": tv_symbol, "interval": "D", "timezone": "Asia/Seoul" if market == "한국" else "America/New_York", "theme": "light", "style": "1", "locale": "kr", "allow_symbol_change": False, "calendar": False})
    st.iframe('<div class="tradingview-widget-container" style="height:600px;width:100%"><div class="tradingview-widget-container__widget" style="height:calc(100% - 32px);width:100%"></div><div class="tradingview-widget-copyright"><a href="https://www.tradingview.com/" target="_blank" rel="noopener">TradingView에서 차트 보기</a></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>' + config + '</script></div>', height=640)
    st.caption("위젯이 보이지 않으면 브라우저의 외부 스크립트 차단이나 종목 지원 여부를 확인하세요.")

with st.expander("위험 신호 계산 기준과 한계"):
    st.markdown("""- MACD = EMA(종가,19) − EMA(종가,39), 시그널 = EMA(MACD,9).
- **주의:** MACD선이 전일보다 하락하거나 시그널선 아래에 있는 경우, 또는 거래량 증가를 동반한 종가 하락.
- **위험:** 당일 데드크로스, 당일 0선 하향 돌파, 또는 MACD 하락과 거래량 증가를 동반한 종가 하락이 동시에 발생.
- 거래량 증가 기준: 당일 거래량 ÷ **당일 제외 직전 20거래일 평균** ≥ 1.5.
- MACD 3일 연속 하락과 히스토그램 감소는 추가 설명으로 표시합니다.
- 횡보장에서는 거짓 신호가 생기고 추세 전환을 늦게 알릴 수 있습니다. 신호의 수익성·정확도는 백테스트하지 않았습니다.
- 앱을 다시 분석할 때만 신호가 갱신됩니다. 푸시·텔레그램 알림과 자동 매도는 없습니다.""")
st.download_button("분석 데이터 CSV 저장", frame.to_csv(index_label="Date").encode("utf-8-sig"), file_name="chart-analysis.csv", mime="text/csv")
