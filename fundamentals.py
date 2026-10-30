"""Quarterly reported financials; missing observations are never filled."""
import math
import pandas as pd


def quarterly_metrics(statement):
    if statement.empty:
        raise ValueError('제공처에 분기 재무제표가 없습니다.')
    result = pd.DataFrame(index=pd.to_datetime(statement.columns))
    for field, label in [('Total Revenue', '매출액'), ('Operating Income', '영업이익')]:
        result[label] = pd.to_numeric(statement.loc[field], errors='coerce').to_numpy() if field in statement.index else float('nan')
    result = result.loc[~result.index.duplicated()].sort_index().dropna(how='all').tail(8)
    if result.empty:
        raise ValueError('매출액·영업이익 자료가 없습니다.')
    result['영업이익률'] = result['영업이익'].div(result['매출액'].where(result['매출액'] > 0)) * 100
    return result.replace([float('inf'), -float('inf')], float('nan'))


def positive_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (ValueError, TypeError):
        return None


class UnsupportedFinancials(ValueError):
    """A fund does not publish company operating results."""


def fetch_fundamentals(symbol):
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    try:
        info = ticker.get_info() or {}
    except Exception:
        info = {}
    kind = str(info.get('quoteType', '')).upper()
    if kind in {'ETF', 'MUTUALFUND', 'INDEX', 'CURRENCY', 'CRYPTOCURRENCY', 'FUTURE'}:
        name = info.get('longName') or info.get('shortName') or symbol
        raise UnsupportedFinancials(
            f'{symbol} · {name} ({kind})은 기업 분기 손익계산서 분석 대상이 아닙니다. '
            '매출액·영업이익·영업이익률·기업 PEG를 표시할 수 없습니다. '
            '개별 기업 종목을 선택하면 분기 실적을 조회할 수 있습니다. 가격·거래량 차트는 계속 사용할 수 있습니다.')
    try:
        statement = ticker.quarterly_income_stmt
    except Exception as error:
        raise RuntimeError('Yahoo Finance 분기 재무제표 요청에 실패했습니다. 일시적인 요청 제한 또는 연결 오류일 수 있습니다.') from error
    if statement.empty:
        raise ValueError(f'Yahoo Finance가 {symbol}의 분기 손익계산서를 반환하지 않았습니다. '
                         '시세와 재무제표의 지원 범위는 다릅니다. ETF·펀드 여부와 종목 코드를 확인하세요. '
                         '개별 기업이라면 제공처 미지원 또는 일시적인 요청 제한일 수 있습니다.')
    financials = quarterly_metrics(statement)
    return financials, info.get('financialCurrency'), positive_number(info.get('trailingPegRatio'))


def render_fundamentals(symbol, mode):
    import streamlit as st
    import plotly.graph_objects as go
    from datetime import datetime, timezone

    st.subheader('기본적 분석 · 분기 실적')
    st.caption('출처: Yahoo Finance (yfinance) · 최근 최대 8분기의 보고 실적 · 결산 종료일 기준 · 시세의 일봉/주봉 선택과 독립적으로 표시됩니다.')
    if mode != '온라인 시세':
        st.info('실제 종목의 기본적 분석은 온라인 시세로 분석한 후 사용할 수 있습니다. 가격 CSV·가상 데이터에는 재무제표가 포함되어 있지 않습니다.')
        return
    @st.cache_data(ttl=21600, show_spinner=False)
    def load(symbol):
        frame, currency, peg = fetch_fundamentals(symbol)
        return frame, currency, peg, datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    # Keep technical charts usable when the financial provider is slow or unavailable.
    if st.button('분기 재무제표 불러오기', key='load_financials'):
        load.clear(symbol)
        st.session_state['financial_symbol'] = symbol
    if st.session_state.get('financial_symbol') != symbol:
        return
    try:
        with st.spinner('분기 실적을 불러오는 중입니다…'):
            frame, currency, peg, fetched = load(symbol)
    except UnsupportedFinancials as error:
        st.info(str(error))
        return
    except (ValueError, RuntimeError) as error:
        st.warning(str(error))
        return
    except Exception:
        st.warning('재무 데이터를 불러오지 못했습니다. 제공처의 지원 여부나 일시적인 연결 문제일 수 있습니다. 잠시 후 다시 시도하세요.')
        return
    st.caption(f'출처: Yahoo Finance · {symbol} · 보고 통화: {currency or "미확인"} · 조회: {fetched}')
    if len(frame) < 8:
        st.info(f'제공처에서 {len(frame)}분기만 제공했습니다. 누락 분기를 임의로 채우지 않고 제공된 실적만 표시합니다.')
    labels = frame.index.strftime('%Y-%m-%d').tolist()
    for row in [('매출액', '영업이익'), ('영업이익률', 'PEG')]:
        for col, name in zip(st.columns(2), row):
            with col:
                st.markdown(f'**{name}**' + (' · 최신 제공값' if name == 'PEG' else ''))
                fig = go.Figure()
                if name == 'PEG':
                    if peg is None:
                        st.info('유효한 양수 PEG가 제공되지 않았습니다.')
                        continue
                    fig.add_bar(x=['최신 제공값'], y=[peg], text=[f'{peg:.2f}'], textposition='auto', marker_color='#c084fc')
                    unit = '배'
                elif frame[name].notna().any():
                    unit = '%' if name == '영업이익률' else f'백만 {currency or "통화 미확인"}'
                    values = frame[name] if name == '영업이익률' else frame[name]/1_000_000
                    if name == '영업이익률':
                        fig.add_scatter(x=labels, y=values, mode='lines+markers', connectgaps=False, line_color='#fbbf24')
                    else:
                        fig.add_bar(x=labels, y=values, marker_color=['#ef5350' if v < 0 else '#60a5fa' for v in values])
                else:
                    st.info(f'{name} 자료가 제공되지 않았습니다.')
                    continue
                fig.update_layout(height=310, margin=dict(l=20,r=20,t=20,b=35), yaxis_title=unit, xaxis_type='category', showlegend=False)
                st.plotly_chart(fig, width='stretch', key='fundamental_'+name)
    st.caption('영업이익률 = 영업이익 ÷ 매출액 × 100. PEG는 제공처의 최신 trailingPegRatio이며 분기별 시계열이 아닙니다. 과거 시점의 PER·성장률 자료가 없어 8분기 PEG를 임의 계산하지 않습니다. 제공처의 성장률 기간·산식이 공개 자료와 다를 수 있어 PEG 단독으로 저평가 여부를 판단하지 마세요.')
    latest=frame.iloc[-1]
    if pd.notna(latest['영업이익률']):
        st.write(f'최근 보고 분기({labels[-1]}) 영업이익률은 {latest["영업이익률"]:.2f}%입니다.')
    with st.expander('분기 실적 원자료'):
        st.dataframe(frame.rename_axis('결산 종료일'), width='stretch')
