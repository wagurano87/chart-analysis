"""Interactive multi-pane chart with viewport-dependent approximate volume profile."""
import json

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def chart_html(frame, timeframe, bins=32):
    x = list(range(len(frame)))
    dates = frame.index.strftime('%Y-%m-%d').tolist()
    fig = make_subplots(rows=6, cols=2, shared_xaxes=True, shared_yaxes=True,
                        column_widths=[.86, .14], row_heights=[.42, .08, .15, .15, .10, .10],
                        horizontal_spacing=.065, vertical_spacing=.042,
                        specs=[[{}, {}], [{}, None], [{}, None], [{}, None], [{}, None], [{}, None]])
    colors = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(frame.Close, frame.Open)]
    fig.add_trace(go.Candlestick(x=x, open=frame.Open, high=frame.High, low=frame.Low,
                                close=frame.Close, text=dates, name=timeframe,
                                increasing=dict(line=dict(color='#26a69a', width=2), fillcolor='#26a69a'),
                                decreasing=dict(line=dict(color='#ef5350', width=2), fillcolor='#ef5350')), row=1, col=1)
    for window, color in [(20, '#fbbf24'), (60, '#60a5fa'), (200, '#c084fc')]:
        fig.add_trace(go.Scatter(x=x, y=frame[f'MA{window}'], name=f'MA{window}',
                                line=dict(color=color, width=2), customdata=dates,
                                hovertemplate='%{customdata} MA'+str(window)+': %{y:.2f}<extra></extra>'), row=1, col=1)
    profile_index = len(fig.data)
    fig.add_trace(go.Bar(x=[], y=[], orientation='h', name='VRVP 추정',
                        marker_color='#475569', hovertemplate='가격 %{y:.2f}<br>추정 거래량 %{x:,.0f}<extra></extra>'), row=1, col=2)
    fig.add_trace(go.Bar(x=x, y=frame.Volume, name='거래량', marker_color=colors, customdata=dates,
                        hovertemplate='%{customdata}<br>거래량 %{y:,.0f}<extra></extra>'), row=2, col=1)
    for row, names, label in [(3, ('MACD6', 'Signal6', 'Histogram6'), '6,19,9'),
                               (4, ('MACD', 'Signal', 'Histogram'), '19,39,9')]:
        for name, color in zip(names[:2], ['#38bdf8', '#fb923c']):
            fig.add_trace(go.Scatter(x=x, y=frame[name], name=f'{name} ({label})', line=dict(color=color, width=2),
                                    customdata=dates, hovertemplate='%{customdata}<br>%{y:.4f}<extra>%{fullData.name}</extra>'), row=row, col=1)
        fig.add_trace(go.Bar(x=x, y=frame[names[2]], name=f'Histogram ({label})',
                            marker_color=['#26a69a' if v >= 0 else '#ef5350' for v in frame[names[2]]]), row=row, col=1)
    for row, name, color in [(5, 'RSI', '#c084fc'), (6, 'OBV', '#fbbf24')]:
        fig.add_trace(go.Scatter(x=x, y=frame[name], name=name, line=dict(color=color, width=2), customdata=dates,
                                hovertemplate='%{customdata}<br>'+name+': %{y:,.2f}<extra></extra>'), row=row, col=1)
    signal_positions = [i for i, value in enumerate(frame.MACD19SellSignal) if value]
    for row, column in [(1, 'High'), (4, 'MACD')]:
        fig.add_trace(go.Scatter(
            x=signal_positions, y=frame[column].iloc[signal_positions], mode='markers',
            name='0선 돌파 후 오실레이터 음전환',
            marker=dict(symbol='triangle-down', size=14, color='#ff4d8d',
                        line=dict(color='#ffffff', width=1)),
            customdata=[[dates[i], float(frame.MACD.iloc[i]), float(frame.Histogram.iloc[i])]
                        for i in signal_positions],
            hovertemplate='%{customdata[0]}<br><b>매도 주의 시그널</b><br>0선 상향 돌파 후 MACD 양수 유지·오실레이터 음전환<br>MACD %{customdata[1]:.4f}<br>오실레이터 %{customdata[2]:.4f}<extra></extra>'
        ), row=row, col=1)
    for value in (30, 70):
        fig.add_hline(y=value, line_dash='dot', line_color='#94a3b8', row=5, col=1)
    start = max(0, len(frame) - 60)
    ticks = list(range(0, len(frame), max(1, len(frame) // 15)))
    for row in range(1, 7):
        fig.update_xaxes(range=[start-.5, len(frame)-.5], tickvals=ticks, ticktext=[dates[i] for i in ticks],
                         showspikes=True, spikemode='across', spikesnap='cursor', spikethickness=1,
                         showgrid=True, gridcolor='#242b38', row=row, col=1)
    for row, title in [(1, '가격'), (2, '거래량'), (3, 'MACD 6·19·9'), (4, 'MACD 19·39·9'), (5, 'RSI 14'), (6, 'OBV')]:
        fig.update_yaxes(title_text=None, side='right', tickfont=dict(size=12, color='#cbd5e1'),
                         nticks=5, gridcolor='#242b38', fixedrange=False,
                         showspikes=True, spikemode='across', spikesnap='cursor', row=row, col=1)
    for row, title in [(1, f'{timeframe}  ·  MA20 / MA60 / MA200'), (2, '거래량'),
                       (3, 'MACD 6 · 19 · 9'), (4, 'MACD 19 · 39 · 9'), (5, 'RSI 14'), (6, 'OBV')]:
        axis = fig.layout['yaxis' if row == 1 else f'yaxis{row+1}']
        text = '<b>'+title+'</b>'
        if row in (3,4):
            text += '  <span style="color:#38bdf8">MACD</span>  <span style="color:#fb923c">Signal</span>'
        if row == 1:
            text = '<b>'+timeframe+'</b>  <span style="color:#fbbf24">MA20</span>  <span style="color:#60a5fa">MA60</span>  <span style="color:#c084fc">MA200</span>'
        fig.add_annotation(x=0, y=axis.domain[1], xref='paper', yref='paper', text=text,
                           showarrow=False, xanchor='left', yanchor='bottom', yshift=5,
                           font=dict(size=12,color='#e2e8f0'))
    fig.add_annotation(x=1, y=1, xref='paper',yref='paper',text='VRVP · 추정',
                       showarrow=False,xanchor='right',yanchor='bottom',yshift=5,font=dict(size=11,color='#94a3b8'))
    fig.add_hrect(y0=30, y1=70, fillcolor='#a78bfa', opacity=.08, line_width=0, row=5,col=1)
    fig.update_yaxes(range=[0, 100], tickvals=[30,50,70], row=5, col=1)
    fig.update_yaxes(showticklabels=False, row=1, col=2)
    # Shared axes normally hide labels on upper panes. Keep dates directly below price.
    fig.update_xaxes(showticklabels=True, side='bottom', ticks='outside',
                     tickfont=dict(size=11), tickangle=0, row=1, col=1)
    fig.update_xaxes(title_text=None, showticklabels=False, row=1, col=2)
    fig.update_layout(height=1330, template='plotly_dark', paper_bgcolor='#131722', plot_bgcolor='#131722',
                      margin=dict(l=16,r=12,t=40,b=36), dragmode='pan', hovermode='x',
                      xaxis_rangeslider_visible=False, showlegend=False, font=dict(family='Arial, sans-serif',size=12,color='#cbd5e1'),
                      hoverlabel=dict(bgcolor='#222b3b',font_size=13),
                      newshape=dict(line_color='#eab308'), uirevision='chart')
    records = frame[['Low','High','Volume']].to_numpy().tolist()
    script = r'''
const gd = document.getElementById('analysis-chart');
const records = RECORDS;
const ohlc = OHLC;
const series = SERIES;
const dates = DATES;
const binCount = BINS;
const profileIndex = PROFILE;
let busy = false;
function showCandle(index) {
    const i=Math.min(ohlc.length-1,Math.max(0,Math.round(index))), row=ohlc[i];
    const f=n=>Number(n).toLocaleString(undefined,{maximumFractionDigits:2});
    const change=i ? (row[3]/ohlc[i-1][3]-1)*100 : 0;
    const readout=document.getElementById('candle-readout');
    readout.textContent=`${dates[i]}   시 ${f(row[0])}   고 ${f(row[1])}   저 ${f(row[2])}   종 ${f(row[3])}   ${change>=0?'+':''}${change.toFixed(2)}%   거래량 ${f(records[i][2])}`;
    readout.style.color=change>=0?'#5dd6be':'#ff858d';
}
gd.on('plotly_hover',event=>{if(event.points.length && event.points[0].curveNumber!==profileIndex) showCandle(event.points[0].x);});
gd.on('plotly_unhover',()=>showCandle(records.length-1));
showCandle(records.length-1);
document.querySelectorAll('#range-toolbar button').forEach(button => {
    button.addEventListener('click', () => {
        const count = button.dataset.count === 'all' ? records.length : Number(button.dataset.count);
        Plotly.relayout(gd, {'xaxis.range':[Math.max(-.5,records.length-count-.5),records.length-.5]});
    });
});
function updateProfile(range) {
    const lo = Math.max(0, Math.ceil(Number(range[0]))), hi = Math.min(records.length-1, Math.floor(Number(range[1])));
    const visible = records.slice(lo, hi+1);
    document.querySelectorAll('#range-toolbar button').forEach(button => {
        const count = button.dataset.count === 'all' ? records.length : Math.min(records.length,Number(button.dataset.count));
        button.setAttribute('aria-pressed',String(hi===records.length-1 && visible.length===count));
    });
    if (!visible.length) {
        window.__volumeProfile = {first:lo,last:hi,volumes:[],centers:[],total:0,poc:null};
        document.getElementById('profile-status').textContent = '선택 범위에 봉이 없습니다.';
        Plotly.restyle(gd, {x:[[]], y:[[]]}, [profileIndex]); return;
    }
    let min = visible.reduce((v,r)=>Math.min(v,r[0]),Infinity), max = visible.reduce((v,r)=>Math.max(v,r[1]),-Infinity);
    if (max === min) { min -= Math.max(.01, Math.abs(min)*.001); max += Math.max(.01,Math.abs(max)*.001); }
    const step = (max-min)/binCount, volumes = new Array(binCount).fill(0);
    // With OHLCV only, approximate each candle's volume uniformly over its low/high.
    for (const [low, high, volume] of visible) {
        if (high===low) { volumes[Math.min(binCount-1,Math.max(0,Math.floor((low-min)/step)))] += volume; continue; }
        for (let b=0;b<binCount;b++) {
            const overlap = Math.max(0, Math.min(high,min+(b+1)*step)-Math.max(low,min+b*step));
            volumes[b] += volume * overlap/(high-low);
        }
    }
    const centers=volumes.map((_,b)=>min+(b+.5)*step);
    const poc=volumes.some(v=>v>0) ? volumes.indexOf(Math.max(...volumes)) : -1;
    window.__volumeProfile = {first:lo,last:hi,volumes,centers,total:visible.reduce((sum,r)=>sum+r[2],0),poc:centers[poc]};
    document.getElementById('profile-status').textContent = `표시 범위: ${dates[lo]} ~ ${dates[hi]} · ${visible.length}개 봉 · 추정 POC: ${poc<0?'거래량 없음':centers[poc].toFixed(2)}`;
    Plotly.restyle(gd, {x:[volumes], y:[centers], width:[step*.94], 'marker.color':[volumes.map((_,i)=>i===poc?'#fbbf24':'#475569')]}, [profileIndex]);
    const pad=(max-min)*.04;
    const ticks=[]; for(let i=lo;i<=hi;i+=Math.max(1,Math.ceil((hi-lo+1)/Math.max(3,Math.floor(gd.clientWidth/130))))) ticks.push(i);
    const update={'yaxis.range':[min-pad,max+pad], 'xaxis2.autorange':true};
    for (const [axis, columns] of [['yaxis3',[0]],['yaxis4',[1,2,3]],['yaxis5',[4,5,6]],['yaxis7',[7]]]) {
        const values = series.slice(lo,hi+1).flatMap(row=>columns.map(c=>row[c])).filter(v=>v!==null && Number.isFinite(v));
        if (!values.length) continue;
        let bottom=values.reduce((a,b)=>Math.min(a,b),Infinity), top=values.reduce((a,b)=>Math.max(a,b),-Infinity);
        if (axis!=='yaxis7') { bottom=Math.min(0,bottom); top=Math.max(0,top); }
        const padding=Math.max((top-bottom)*.08,Math.abs(top)*.001,.01);
        update[axis+'.range']=[bottom-padding,top+padding];
    }
    for (const axis of ['xaxis','xaxis3','xaxis4','xaxis5','xaxis6','xaxis7']) {
        update[axis+'.tickvals']=ticks; update[axis+'.ticktext']=ticks.map(i=>dates[i]);
    }
    busy=true;
    Plotly.relayout(gd,update).finally(()=>{busy=false;});
}
gd.on('plotly_relayout', event => {
    if (busy) return;
    const changed=Object.keys(event).find(k=>/^xaxis(?!2[.])\d*[.](range|autorange)/.test(k));
    if (!changed) return;
    const axis=changed.split('.')[0];
    let range = event[axis+'.autorange'] ? [-.5, records.length-.5] : event[axis+'.range'];
    if (!range && event[axis+'.range[0]']!==undefined) range=[event[axis+'.range[0]'],event[axis+'.range[1]']];
    if (!range) range=gd.layout[axis].range;
    updateProfile(range);
});
let resizeTimer;
window.addEventListener('resize',()=>{
    clearTimeout(resizeTimer);
    resizeTimer=setTimeout(()=>updateProfile(gd.layout.xaxis.range),200);
});
updateProfile([START, END]);
'''
    values = frame[['Volume','MACD6','Signal6','Histogram6','MACD','Signal','Histogram','OBV']].to_json(orient='values')
    script = (script.replace('RECORDS', json.dumps(records)).replace('OHLC', frame[['Open','High','Low','Close']].to_json(orient='values')).replace('SERIES',values).replace('DATES',json.dumps(dates))
              .replace('BINS', str(int(bins))).replace('PROFILE',str(profile_index))
              .replace('START',str(start-.5)).replace('END',str(len(frame)-.5)))
    html = fig.to_html(full_html=True, include_plotlyjs=True, div_id='analysis-chart', post_script=script,
                       config={'scrollZoom':True,'displaylogo':False,'responsive':True,'displayModeBar':True,
                               'modeBarButtonsToAdd':['drawline','drawrect','eraseshape'], 'toImageButtonOptions':{'filename':'chart-analysis'}})
    toolbar = '''<style>
    #range-toolbar {display:flex;justify-content:center;gap:6px;flex-wrap:wrap;padding:10px;border-bottom:1px solid #2a3140;}
    .modebar {background:#1e2533!important;border-radius:4px;}
    .modebar-btn path {fill:#b6c2d5!important;}
    .modebar-btn:hover path {fill:#fff!important;}
    #candle-readout {padding:10px 16px 4px;font-size:13px;line-height:1.8;font-variant-numeric:tabular-nums;}
    #range-toolbar button {background:#1e293b;color:#e2e8f0;border:1px solid #475569;border-radius:4px;padding:7px 16px;cursor:pointer;font-size:14px;}
    #range-toolbar button:hover {background:#334155;}
    #range-toolbar button[aria-pressed="true"] {background:#2563eb;border-color:#60a5fa;color:white;}
    #range-toolbar button:focus-visible {outline:2px solid #fbbf24;outline-offset:2px;}
    </style><nav id="range-toolbar" aria-label="차트 표시 범위">
    <button type="button" data-count="60" aria-pressed="true">최근 60봉</button>
    <button type="button" data-count="180" aria-pressed="false">최근 180봉</button>
    <button type="button" data-count="all" aria-pressed="false">전체</button>
    </nav><div id="candle-readout" aria-live="off"></div><div id="profile-status" style="padding:4px 16px 10px;font-size:12px;color:#a8b4c6"></div>'''
    return html.replace('<body>', '<body style="margin:0;background:#131722;color:#cbd5e1;font-family:sans-serif">'+toolbar)
