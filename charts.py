"""Interactive multi-pane chart with viewport-dependent approximate volume profile."""
import json

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def chart_html(frame, timeframe, bins=32):
    x = list(range(len(frame)))
    dates = frame.index.strftime('%Y-%m-%d').tolist()
    fig = make_subplots(rows=6, cols=2, shared_xaxes=True, shared_yaxes=True,
                        column_widths=[.82, .18], row_heights=[.36, .12, .15, .15, .11, .11],
                        horizontal_spacing=.02, vertical_spacing=.035,
                        specs=[[{}, {}], [{}, None], [{}, None], [{}, None], [{}, None], [{}, None]])
    colors = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(frame.Close, frame.Open)]
    fig.add_trace(go.Candlestick(x=x, open=frame.Open, high=frame.High, low=frame.Low,
                                close=frame.Close, text=dates, name=timeframe,
                                increasing_line_color='#26a69a', decreasing_line_color='#ef5350'), row=1, col=1)
    for window, color in [(20, '#fbbf24'), (60, '#60a5fa'), (200, '#c084fc')]:
        fig.add_trace(go.Scatter(x=x, y=frame[f'MA{window}'], name=f'MA{window}',
                                line=dict(color=color, width=1), customdata=dates,
                                hovertemplate='%{customdata} MA'+str(window)+': %{y:.2f}<extra></extra>'), row=1, col=1)
    profile_index = len(fig.data)
    fig.add_trace(go.Bar(x=[], y=[], orientation='h', name='VRVP 추정',
                        marker_color='#475569', hovertemplate='가격 %{y:.2f}<br>추정 거래량 %{x:,.0f}<extra></extra>'), row=1, col=2)
    fig.add_trace(go.Bar(x=x, y=frame.Volume, name='거래량', marker_color=colors, customdata=dates,
                        hovertemplate='%{customdata}<br>거래량 %{y:,.0f}<extra></extra>'), row=2, col=1)
    for row, names, label in [(3, ('MACD6', 'Signal6', 'Histogram6'), '6,19,9'),
                               (4, ('MACD', 'Signal', 'Histogram'), '19,39,9')]:
        for name, color in zip(names[:2], ['#38bdf8', '#fb923c']):
            fig.add_trace(go.Scatter(x=x, y=frame[name], name=f'{name} ({label})', line=dict(color=color, width=1.5),
                                    customdata=dates, hovertemplate='%{customdata}<br>%{y:.4f}<extra>%{fullData.name}</extra>'), row=row, col=1)
        fig.add_trace(go.Bar(x=x, y=frame[names[2]], name=f'Histogram ({label})',
                            marker_color=['#26a69a' if v >= 0 else '#ef5350' for v in frame[names[2]]]), row=row, col=1)
    for row, name, color in [(5, 'RSI', '#c084fc'), (6, 'OBV', '#fbbf24')]:
        fig.add_trace(go.Scatter(x=x, y=frame[name], name=name, line=dict(color=color, width=1.5), customdata=dates,
                                hovertemplate='%{customdata}<br>'+name+': %{y:,.2f}<extra></extra>'), row=row, col=1)
    for value in (30, 70):
        fig.add_hline(y=value, line_dash='dot', line_color='#94a3b8', row=5, col=1)
    start = max(0, len(frame) - 180)
    ticks = list(range(0, len(frame), max(1, len(frame) // 15)))
    for row in range(1, 7):
        fig.update_xaxes(range=[start-.5, len(frame)-.5], tickvals=ticks, ticktext=[dates[i] for i in ticks],
                         showspikes=True, spikemode='across', spikesnap='cursor', spikethickness=1,
                         showgrid=True, gridcolor='#1e293b', row=row, col=1)
    for row, title in [(1, '가격'), (2, '거래량'), (3, 'MACD 6·19·9'), (4, 'MACD 19·39·9'), (5, 'RSI 14'), (6, 'OBV')]:
        fig.update_yaxes(title_text=title, gridcolor='#1e293b', fixedrange=False,
                         showspikes=True, spikemode='across', spikesnap='cursor', row=row, col=1)
    fig.update_yaxes(range=[0, 100], row=5, col=1)
    # Shared axes normally hide labels on upper panes. Keep dates directly below price.
    fig.update_xaxes(showticklabels=True, side='bottom', ticks='outside',
                     tickfont=dict(size=11), tickangle=0, row=1, col=1)
    fig.update_xaxes(title_text='VRVP 추정', showticklabels=False, row=1, col=2)
    fig.update_layout(height=1450, template='plotly_dark', paper_bgcolor='#0b1220', plot_bgcolor='#0b1220',
                      margin=dict(l=65,r=25,t=95,b=40), dragmode='pan', hovermode='x',
                      xaxis_rangeslider_visible=False, showlegend=True,
                      legend=dict(orientation='h',y=1.06,x=0,font=dict(size=10)),
                      newshape=dict(line_color='#eab308'), uirevision='chart')
    records = frame[['Low','High','Volume']].to_numpy().tolist()
    script = r'''
const gd = document.getElementById('analysis-chart');
const records = RECORDS;
const series = SERIES;
const dates = DATES;
const binCount = BINS;
const profileIndex = PROFILE;
let busy = false;
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
    const ticks=[]; for(let i=lo;i<=hi;i+=Math.max(1,Math.ceil((hi-lo+1)/9))) ticks.push(i);
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
updateProfile([START, END]);
'''
    values = frame[['Volume','MACD6','Signal6','Histogram6','MACD','Signal','Histogram','OBV']].to_json(orient='values')
    script = (script.replace('RECORDS', json.dumps(records)).replace('SERIES',values).replace('DATES',json.dumps(dates))
              .replace('BINS', str(int(bins))).replace('PROFILE',str(profile_index))
              .replace('START',str(start-.5)).replace('END',str(len(frame)-.5)))
    html = fig.to_html(full_html=True, include_plotlyjs=True, div_id='analysis-chart', post_script=script,
                       config={'scrollZoom':True,'displaylogo':False,'responsive':True,
                               'modeBarButtonsToAdd':['drawline','drawrect','eraseshape'], 'toImageButtonOptions':{'filename':'chart-analysis'}})
    toolbar = '''<style>
    #range-toolbar {display:flex;justify-content:center;gap:10px;flex-wrap:wrap;padding:12px;border-bottom:1px solid #334155;}
    #range-toolbar button {background:#1e293b;color:#e2e8f0;border:1px solid #475569;border-radius:6px;padding:9px 18px;cursor:pointer;font-size:14px;}
    #range-toolbar button:hover {background:#334155;}
    #range-toolbar button[aria-pressed="true"] {background:#2563eb;border-color:#60a5fa;color:white;}
    #range-toolbar button:focus-visible {outline:2px solid #fbbf24;outline-offset:2px;}
    </style><nav id="range-toolbar" aria-label="차트 표시 범위">
    <button type="button" data-count="60" aria-pressed="false">최근 60봉</button>
    <button type="button" data-count="180" aria-pressed="true">최근 180봉</button>
    <button type="button" data-count="all" aria-pressed="false">전체</button>
    </nav><div id="profile-status" style="padding:8px;font-size:13px"></div>'''
    return html.replace('<body>', '<body style="margin:0;background:#0b1220;color:#cbd5e1;font-family:sans-serif">'+toolbar)
