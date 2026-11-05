"""Poll recent public crypto candles without remounting the chart iframe."""
import json
import pandas as pd
from analysis import indicators, completed_daily_bars, resample_bars, validate_prices
from crypto_data import fetch_crypto, completed_four_hour_bars


def merge_recent(history, recent):
    if recent.empty:
        raise ValueError('최근 시세가 없습니다.')
    # Do not silently skip a gap after a long suspended browser session.
    if recent.index.min() > history.index.max() + pd.Timedelta(days=1):
        raise ValueError('조회 공백이 길어졌습니다. 분석하기로 전체 시세를 다시 불러오세요.')
    merged = pd.concat([history, recent])
    return validate_prices(merged.loc[~merged.index.duplicated(keep='last')].sort_index(), normalize_dates=False)


def live_indicators(raw, timeframe, market, di_length, adx_length, adxr_length, now=None):
    current = pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    current = current.tz_localize('UTC') if current.tzinfo is None else current.tz_convert('UTC')
    raw = raw.loc[raw.index <= current.tz_localize(None)]
    if timeframe == '주봉':
        bars = raw.resample('W-SUN').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        first = raw.index.min().to_period('W-SUN').start_time
        if raw.index.min() > first:
            bars = bars.loc[bars.index >= first + pd.Timedelta(days=7)]
        completed = resample_bars(raw, market, '주봉', now=current)
    elif timeframe == '4시간봉':
        bars = raw
        completed = completed_four_hour_bars(raw, now=current)
    else:
        bars = raw
        completed = completed_daily_bars(raw, market, now=current)
    frame = indicators(bars, di_length, adx_length, adxr_length)
    confirmed = frame.index.isin(completed.index)
    frame.loc[~confirmed, ['MACD19SellSignal', 'DIBuySignal']] = False
    return frame, int((~confirmed).sum())


def message_html(message):
    # Escape HTML parser delimiters; the payload contains no executable source.
    encoded = json.dumps(message, ensure_ascii=True).replace('<', '\\u003c')
    return '''<script>
const message=PAYLOAD;
const channelOrigin=new URL(document.baseURI).origin;
let timer;
const targets=new Set();
function send(){for(let i=0;i<parent.frames.length;i++) {
    const target=parent.frames[i];
    try {if(target!==window && target.document.getElementById('analysis-chart')) {
        targets.add(target);target.postMessage(message,channelOrigin);
    }} catch(error) { /* Ignore unrelated cross-origin frames. */ }
}}
window.addEventListener('message',e=>{if(e.origin===channelOrigin && targets.has(e.source) && e.data?.type==='chart-live-ack' && e.data.token===message.token) clearInterval(timer);});
timer=setInterval(send,500);send();setTimeout(()=>clearInterval(timer),9000);
</script>'''.replace('PAYLOAD', encoded)


def render_live_updates(seed, ticker, market, timeframe, bins, threshold, lengths, token):
    import streamlit as st
    from charts import live_payload
    state_key = 'live_history_' + token
    for key in list(st.session_state):
        if key.startswith('live_history_'):
            del st.session_state[key]
    st.session_state[state_key] = seed

    @st.fragment(run_every='10s')
    def poll():
        try:
            interval = '4h' if timeframe == '4시간봉' else '1d'
            recent, _, _ = fetch_crypto(ticker, market, limit=30, interval=interval)
            history = merge_recent(st.session_state[state_key], recent)
            frame, pending = live_indicators(history, timeframe, market, *lengths)
            st.session_state[state_key] = history
            payload = live_payload(frame, timeframe, bins, threshold)
            stamp = pd.Timestamp.now(tz='Asia/Seoul').strftime('%H:%M:%S')
            message = {'type':'chart-live', 'token':token, 'payload':payload,
                       'status':f'10초 자동 갱신 · {stamp} (한국 시간) · 진행 중 {pending}봉 · 시그널은 마감 후 확정'}
        except Exception:
            message = {'type':'chart-live', 'token':token,
                       'error':'자동 갱신 실패 · 마지막 수신 차트 유지 · 반복되면 분석하기로 다시 조회하세요.'}
        st.iframe(message_html(message), height=1, tab_index=-1)

    poll()
