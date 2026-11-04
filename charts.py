"""Interactive multi-pane chart with viewport-dependent approximate volume profile."""
import json

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from analysis import MA_WINDOWS


def chart_html(frame, timeframe, bins=32, adx_threshold=20):
    x = list(range(len(frame)))
    dates = frame.index.strftime('%Y-%m-%d %H:%M' if timeframe=='4시간봉' else '%Y-%m-%d').tolist()
    fig = make_subplots(rows=7, cols=2, shared_xaxes=True, shared_yaxes=True,
                        column_widths=[.88, .12], row_heights=[.40, .06, .12, .12, .08, .08, .14],
                        horizontal_spacing=.075, vertical_spacing=.027,
                        specs=[[{}, {}], [{}, None], [{}, None], [{}, None], [{}, None], [{}, None], [{}, None]])
    colors = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(frame.Close, frame.Open)]
    fig.add_trace(go.Candlestick(x=x, open=frame.Open, high=frame.High, low=frame.Low,
                                close=frame.Close, text=dates, name=timeframe,
                                increasing=dict(line=dict(color='#26a69a', width=2), fillcolor='#26a69a'),
                                decreasing=dict(line=dict(color='#ef5350', width=2), fillcolor='#ef5350')), row=1, col=1)
    ma_colors = ['#34d399', '#fbbf24', '#60a5fa', '#fb923c', '#c084fc', '#f472b6']
    for window, color in zip(MA_WINDOWS, ma_colors):
        fig.add_trace(go.Scatter(x=x, y=frame[f'MA{window}'], name=f'MA{window}',
                                line=dict(color=color, width=2), customdata=dates,
                                hovertemplate='%{customdata} MA'+str(window)+': %{y:.2f}<extra></extra>'), row=1, col=1)
    profile_index = len(fig.data)
    fig.add_trace(go.Bar(x=[], y=[], orientation='h', name='VRVP 추정',
                        marker_color='#475569', hovertemplate='가격 %{y:.2f}<br>추정 거래량 %{x:,.0f}<extra></extra>'), row=1, col=2)
    fig.add_trace(go.Bar(x=x, y=frame.Volume, name='거래량', marker_color=colors, customdata=dates,
                        hovertemplate='%{customdata}<br>거래량 %{y:,.0f}<extra></extra>'), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=frame.VolumeAvg20, name='직전 20봉 평균 거래량',
                            line=dict(color='#e2b45d', width=1.2), customdata=dates,
                            hovertemplate='%{customdata}<br>직전 20봉 평균 %{y:,.0f}<extra></extra>'), row=2, col=1)
    for row, names, label in [(3, ('MACD6', 'Signal6', 'Histogram6'), '6,19,9'),
                               (4, ('MACD', 'Signal', 'Histogram'), '19,39,9')]:
        for name, color in zip(names[:2], ['#38bdf8', '#fb923c']):
            fig.add_trace(go.Scatter(x=x, y=frame[name], name=f'{name} ({label})', line=dict(color=color, width=2),
                                    customdata=dates, hovertemplate='%{customdata}<br>%{y:.4f}<extra>%{fullData.name}</extra>'), row=row, col=1)
        histogram = frame[names[2]]
        histogram_colors = [('#26a69a' if v >= prev else '#b2dfdb') if v >= 0
                            else ('#ef5350' if v < prev else '#ef9a9a')
                            for v, prev in zip(histogram, histogram.shift(1))]
        fig.add_trace(go.Bar(x=x, y=histogram, name=f'Histogram ({label})',
                            marker_color=histogram_colors, customdata=dates,
                            hovertemplate='%{customdata}<br>오실레이터 %{y:.4f}<extra></extra>'), row=row, col=1)
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
    for name,color in [('PlusDI','#34d399'),('MinusDI','#f87171'),('ADX','#fbbf24'),('ADXR','#c084fc')]:
        fig.add_trace(go.Scatter(x=x,y=frame[name],name=name,line=dict(color=color,width=2),customdata=dates,
            hovertemplate='%{customdata}<br>'+name+': %{y:.2f}<extra></extra>'),row=7,col=1)
    fig.add_hline(y=adx_threshold,line_dash='dot',line_color='#94a3b8',row=7,col=1)
    for value in (30, 70):
        fig.add_hline(y=value, line_dash='dot', line_color='#94a3b8', row=5, col=1)
    start = max(0, len(frame) - 60)
    ticks = list(range(0, len(frame), max(1, len(frame) // 15)))
    for row in range(1, 8):
        fig.update_xaxes(range=[start-.5, len(frame)-.5], tickvals=ticks, ticktext=[dates[i] for i in ticks],
                         showspikes=False,
                         showgrid=True, gridcolor='#242b38', row=row, col=1)
    for row, title in [(1, '가격'), (2, '거래량'), (3, 'MACD 6·19·9'), (4, 'MACD 19·39·9'), (5, 'RSI 14'), (6, 'OBV'), (7, 'ADX / ADXR / DI')]:
        fig.update_yaxes(title_text=None, side='right', tickfont=dict(size=12, color='#cbd5e1'),
                         nticks=5, gridcolor='#242b38', fixedrange=False,
                         showspikes=False, zerolinecolor='#475569', row=row, col=1)
    for row, title in [(1, f'{timeframe} 이동평균'), (2, '거래량'),
                       (3, 'MACD 6 · 19 · 9'), (4, 'MACD 19 · 39 · 9'), (5, 'RSI 14'), (6, 'OBV'), (7, 'ADX / ADXR / DI')]:
        axis = fig.layout['yaxis' if row == 1 else f'yaxis{row+1}']
        text = '<b>'+title+'</b>'
        if row == 7:
            text='<b>ADX · ADXR</b> <span style="color:#34d399">+DI</span> <span style="color:#f87171">−DI</span> <span style="color:#fbbf24">ADX</span> <span style="color:#c084fc">ADXR</span>'
        if row in (3,4):
            text += '  <span style="color:#38bdf8">MACD</span>  <span style="color:#fb923c">Signal</span>'
        if row == 1:
            text = '<b>'+timeframe+'</b>  ' + '  '.join(
                f'<span style="color:{color}">MA{window}</span>'
                for window, color in zip(MA_WINDOWS, ma_colors))
        fig.add_annotation(x=0, y=axis.domain[1], xref='paper', yref='paper', text=text,
                           showarrow=False, xanchor='left', yanchor='bottom', yshift=5,
                           font=dict(size=12,color='#e2e8f0'))
    fig.add_annotation(x=1, y=1, xref='paper',yref='paper',text='VRVP · 추정',
                       showarrow=False,xanchor='right',yanchor='bottom',yshift=5,font=dict(size=11,color='#94a3b8'))
    fig.add_hrect(y0=30, y1=70, fillcolor='#a78bfa', opacity=.08, line_width=0, row=5,col=1)
    fig.update_yaxes(range=[0, 100], tickvals=[30,50,70], row=5, col=1)
    fig.update_yaxes(showticklabels=False, row=1, col=2)
    last_color = '#26a69a' if frame.Close.iloc[-1] >= frame.Close.iloc[-2] else '#ef5350'
    fig.add_shape(type='line', xref='x domain', x0=0, x1=1, yref='y',
                  y0=float(frame.Close.iloc[-1]), y1=float(frame.Close.iloc[-1]),
                  line=dict(color=last_color, width=1, dash='dot'), editable=False)
    fig.add_annotation(x=1, xref='x domain', y=float(frame.Close.iloc[-1]), yref='y',
                       text=f'{frame.Close.iloc[-1]:,.2f}', showarrow=False, xanchor='left',
                       bgcolor=last_color, borderpad=4, font=dict(color='white', size=12),
                       name='last-close')
    # Only drawings added by the user can be selected or deleted.
    fig.update_shapes(editable=False)
    # Shared axes normally hide labels on upper panes. Keep dates directly below price.
    fig.update_xaxes(showticklabels=True, side='bottom', ticks='outside',
                     tickfont=dict(size=11), tickangle=0, row=1, col=1)
    fig.update_xaxes(title_text=None, showticklabels=False, row=1, col=2)
    fig.update_layout(height=1320, template='plotly_dark', paper_bgcolor='#131722', plot_bgcolor='#131722',
                      margin=dict(l=12,r=12,t=32,b=30), dragmode='pan', hovermode='closest',
                      xaxis_rangeslider_visible=False, showlegend=False, font=dict(family='Arial, sans-serif',size=12,color='#cbd5e1'),
                      hoverlabel=dict(bgcolor='#222b3b',font_size=13),
                      newshape=dict(line_color='#eab308'), uirevision='chart')
    records = frame[['Low','High','Volume']].to_numpy().tolist()
    script = r'''
const gd = document.getElementById('analysis-chart');
const records = RECORDS;
const ohlc = OHLC;
const series = SERIES;
const averages = AVERAGES;
const dates = DATES;
const binCount = BINS;
const profileIndex = PROFILE;
let busy = false;
let averagesVisible = true;
let fitNextRange = false;
const protectedShapeCount = (gd.layout.shapes || []).length;
let shapeCount = protectedShapeCount;
let selectedShape = null;
let deletingShape = false;
let measuring = false;
let fibonacci = false;
function refreshMeasurements() {
    const annotations=(gd.layout.annotations || []).filter(a=>!/^measure-|^fib-/.test(String(a.name || '')));
    (gd.layout.shapes || []).forEach((shape,i)=>{
        if(shape.name==='fibonacci') {
            const levels=[0,.236,.382,.5,.618,.786,1];
            const colors=['#94a3b8','#f87171','#fb923c','#facc15','#34d399','#60a5fa','#c084fc'];
            levels.forEach((level,j)=>{
                const price=shape.y1+(shape.y0-shape.y1)*level;
                annotations.push({name:`fib-${i}-${j}`,x:shape.x1,y:price,xref:shape.xref,yref:shape.yref,
                    ax:shape.x0,ay:price,axref:shape.xref,ayref:shape.yref,
                    text:`${(level*100).toFixed(1)}% · ${number(price,Math.abs(price)>=1?2:8)}`,
                    showarrow:true,arrowhead:0,arrowwidth:1.5,arrowcolor:colors[j],
                    standoff:0,startstandoff:0,bgcolor:'#131722',borderpad:2,
                    font:{size:11,color:colors[j]},captureevents:false});
            });
            return;
        }
        if(shape.name!=='measurement') return;
        const start=Math.round(shape.x0), end=Math.round(shape.x1);
        if(!dates[start] || !dates[end] || !shape.y0) return;
        const change=(shape.y1/shape.y0-1)*100;
        const segment=records.slice(Math.min(start,end),Math.max(start,end)+1);
        const high=Math.max(...segment.map(r=>r[1])), low=Math.min(...segment.map(r=>r[0]));
        annotations.push({name:'measure-'+i,x:shape.x1,y:shape.y1,xref:shape.xref,yref:shape.yref,
            text:`${dates[start]} → ${dates[end]}<br>시작 ${number(shape.y0)} → 끝 ${number(shape.y1)}<br>구간 고가 ${number(high)} · 저가 ${number(low)}<br>${change>=0?'+':''}${change.toFixed(2)}% · ${Math.abs(end-start)}봉 · ${Math.round(Math.abs(Date.parse(dates[end])-Date.parse(dates[start]))/86400000)}일`,
            showarrow:true,arrowhead:0,ax:0,ay:change>=0?-40:40,bgcolor:'#24385c',borderpad:5,font:{color:'#fff',size:12}});
    });
    Plotly.relayout(gd,{annotations});
}

gd.tabIndex = 0;
gd.setAttribute('aria-label','분석 차트. 추세선 선택 후 Delete로 삭제, Escape로 선택 해제');
function showShapeSelection() {
    gd.querySelectorAll('.shape-group[data-index]').forEach(node=>{
        node.classList.toggle('selected-drawing', Number(node.dataset.index)===selectedShape);
    });
    const picker=document.getElementById('drawing-picker');
    const drawings=(gd.layout.shapes || []).slice(protectedShapeCount);
    const signature=JSON.stringify(drawings.map(s=>[s.name,s.type]));
    if(picker.dataset.signature!==signature) {
        picker.replaceChildren(new Option('도형 선택', ''));
        drawings.forEach((shape,i)=>{
            const label=shape.name==='fibonacci'?'피보나치':shape.name==='measurement'?'측정':shape.type==='rect'?'사각형':'추세선';
            picker.add(new Option(`${i+1}. ${label}`,String(i+protectedShapeCount)));
        });
        picker.dataset.signature=signature;
    }
    picker.value=selectedShape===null?'':String(selectedShape);
    picker.disabled=!drawings.length;
    document.getElementById('clear-drawings').disabled=!drawings.length || deletingShape;
    document.getElementById('delete-shape').disabled=selectedShape===null || deletingShape;
    document.getElementById('drawing-status').textContent=selectedShape===null
        ? '차트 휠: 시간축 확대 · 오른쪽 눈금 휠: 세로 확대 · Shift+휠: 좌우 이동 · 도형 선택 후 Del 삭제'
        : '도형 선택됨 · 선택 삭제 버튼 또는 Delete로 삭제';
}
function selectShape(index) {
    selectedShape=Number.isInteger(index) && index>=protectedShapeCount &&
        index<(gd.layout.shapes || []).length ? index : null;
    showShapeSelection();
}
gd.addEventListener('pointerdown',event=>{
    if(event.button!==0) return;
    const shape=event.target.closest('.shape-group[data-index]');
    selectShape(shape ? Number(shape.dataset.index) : null);
    gd.focus({preventScroll:true});
},true);
// Plotly rebuilds its SVG paths when a drawing is activated by a click.
gd.addEventListener('click',()=>requestAnimationFrame(showShapeSelection),true);
gd.on('plotly_afterplot',showShapeSelection);
gd.on('plotly_relayout',event=>{
    if(!Object.keys(event).some(key=>key==='shapes' || key.startsWith('shapes['))) return;
    const count=(gd.layout.shapes || []).length;
    const added=count>shapeCount;
    if(count>shapeCount) {
        if(fibonacci && gd.layout.shapes[count-1].yref==='y') {
            const shape=gd.layout.shapes[count-1];
            shape.name='fibonacci';
            shape.line={...shape.line,dash:'dot',color:'#94a3b8'};
        }
        if(measuring && gd.layout.shapes[count-1].yref==='y') {
            const shape=gd.layout.shapes[count-1];
            shape.name='measurement';
            shape.type='rect';
            shape.fillcolor='rgba(96,165,250,0.10)';
            shape.line={...shape.line,dash:'solid',color:'#60a5fa'};
        }
        selectShape(count-1);
        gd.focus({preventScroll:true});
    } else if(count<shapeCount) selectShape(null);
    shapeCount=count;
    if(added) {measuring=false;fibonacci=false;Plotly.relayout(gd,{dragmode:'pan'});}
    showShapeSelection();
    refreshMeasurements();
});
async function deleteSelectedShape() {
    const index=selectedShape, shapes=gd.layout.shapes || [];
    if(deletingShape || index===null || index<protectedShapeCount || index>=shapes.length) return;
    deletingShape=true;
    selectShape(null);
    try {
        await Plotly.relayout(gd,{shapes:shapes.filter((_,i)=>i!==index)});
    } finally {
        deletingShape=false;
        showShapeSelection();
        gd.focus({preventScroll:true});
    }
}
gd.addEventListener('keydown',event=>{
    if(event.target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])')) return;
    if(event.key==='Escape') selectShape(null);
    if(event.key==='Delete' && !event.repeat && !event.ctrlKey && !event.altKey && !event.metaKey && selectedShape!==null) {
        event.preventDefault();
        event.stopPropagation();
        deleteSelectedShape();
    }
});
document.getElementById('delete-shape').addEventListener('click',deleteSelectedShape);
document.getElementById('drawing-picker').addEventListener('change',event=>{
    selectShape(event.target.value===''?null:Number(event.target.value));
});
document.getElementById('clear-drawings').addEventListener('click',async()=>{
    if(deletingShape) return;
    deletingShape=true;selectShape(null);measuring=false;fibonacci=false;
    try {await Plotly.relayout(gd,{shapes:(gd.layout.shapes || []).slice(0,protectedShapeCount),dragmode:'pan'});}
    finally {deletingShape=false;showShapeSelection();}
});
showShapeSelection();
const number = (n, digits=2) => n===null || !Number.isFinite(n) ? '—' :
    Number(n).toLocaleString('ko-KR',{maximumFractionDigits:digits});
function showCandle(index) {
    const i=Math.min(ohlc.length-1,Math.max(0,Math.round(index))), row=ohlc[i];
    const f=n=>Number(n).toLocaleString(undefined,{maximumFractionDigits:2});
    const change=i ? (row[3]/ohlc[i-1][3]-1)*100 : 0;
    const readout=document.getElementById('candle-readout');
    readout.textContent=`${dates[i]}   시 ${f(row[0])}   고 ${f(row[1])}   저 ${f(row[2])}   종 ${f(row[3])}   ${change>=0?'+':''}${change.toFixed(2)}%   거래량 ${f(records[i][2])}`;
    readout.style.color=change>=0?'#5dd6be':'#ff858d';
    const values=series[i];
    document.getElementById('indicator-readout').textContent=
        `MACD 6·19·9  ${number(values[1],4)} / ${number(values[2],4)} / ${number(values[3],4)}     ·     MACD 19·39·9  ${number(values[4],4)} / ${number(values[5],4)} / ${number(values[6],4)}     ·     RSI ${number(values[8])}     ·     OBV ${number(values[7],0)}`;
}
gd.on('plotly_hover',event=>{if(event.points.length && event.points[0].curveNumber!==profileIndex) showCandle(event.points[0].x);});
gd.on('plotly_unhover',()=>showCandle(records.length-1));
showCandle(records.length-1);
// A DOM overlay keeps the cursor aligned across every pane without a Plotly redraw.
gd.style.position='relative';
for (const id of ['cross-v','cross-h','cross-date','cross-value']) {
    const node=document.createElement('div'); node.id=id; node.className='crosshair'; gd.appendChild(node);
}
function hideCrosshair() {
    gd.querySelectorAll('.crosshair').forEach(node=>node.style.display='none');
}
let cursorFrame;
gd.addEventListener('pointermove',event=>{
    cancelAnimationFrame(cursorFrame);
    cursorFrame=requestAnimationFrame(()=>{
        const bounds=gd.getBoundingClientRect(), px=event.clientX-bounds.left, py=event.clientY-bounds.top;
        const layout=gd._fullLayout, axis=layout.xaxis;
        const pane=['yaxis','yaxis3','yaxis4','yaxis5','yaxis6','yaxis7','yaxis8']
            .map(name=>layout[name]).find(a=>py>=a._offset && py<=a._offset+a._length);
        if (!pane || px<axis._offset || px>axis._offset+axis._length) { hideCrosshair(); return; }
        const index=Math.round(axis.p2l(px-axis._offset));
        if(index<0 || index>=records.length) { hideCrosshair(); return; }
        showCandle(index);
        const x=axis._offset+axis.l2p(index);
        const set=(id,style,text)=>{const node=document.getElementById(id);Object.assign(node.style,{display:'block',...style});if(text!==undefined)node.textContent=text;};
        set('cross-v',{left:x+'px',top:layout._size.t+'px',height:layout._size.h+'px'});
        set('cross-h',{left:axis._offset+'px',top:py+'px',width:axis._length+'px'});
        set('cross-date',{left:Math.max(50,Math.min(gd.clientWidth-60,x))+'px',top:(layout.yaxis._offset+layout.yaxis._length+3)+'px'},dates[index]);
        set('cross-value',{left:(axis._offset+axis._length+2)+'px',top:py+'px'},number(pane.p2l(py-pane._offset)));
    });
});
gd.addEventListener('pointerleave',()=>{cancelAnimationFrame(cursorFrame);hideCrosshair();showCandle(records.length-1);});
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{
    measuring=false;
    fibonacci=false;
    Plotly.relayout(gd,{dragmode:button.dataset.mode});
}));
document.getElementById('measure-tool').addEventListener('click',()=>{
    measuring=true;
    fibonacci=false;
    Plotly.relayout(gd,{dragmode:'drawline'});
});
document.getElementById('fib-tool').addEventListener('click',()=>{
    measuring=false;fibonacci=true;
    Plotly.relayout(gd,{dragmode:'drawline'});
});
function syncTools() {
    document.getElementById('fib-tool').setAttribute('aria-pressed',String(fibonacci));
    document.getElementById('measure-tool').setAttribute('aria-pressed',String(measuring));
    document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(!measuring && !fibonacci && gd.layout.dragmode===button.dataset.mode)));
}
gd.on('plotly_relayout',syncTools);
syncTools();
document.getElementById('reset-view').addEventListener('click',()=>{
    hideCrosshair();
    measuring=false;
    fibonacci=false;
    fitNextRange=true;
    Plotly.relayout(gd,{'xaxis.range':[Math.max(-.5,records.length-60-.5),records.length-.5],dragmode:'pan'});
});
document.getElementById('toggle-ma').addEventListener('click',event=>{
    averagesVisible=!averagesVisible;
    event.currentTarget.setAttribute('aria-pressed',String(averagesVisible));
    Plotly.restyle(gd,{visible:averagesVisible},gd.data.map((trace,i)=>/^MA[0-9]+$/.test(trace.name)?i:-1).filter(i=>i>=0)).then(()=>updateProfile(gd.layout.xaxis.range));
});
document.getElementById('save-image').addEventListener('click',()=>{
    Plotly.downloadImage(gd,{format:'png',filename:'chart-analysis',scale:2});
});
document.querySelectorAll('#range-toolbar button').forEach(button => {
    button.addEventListener('click', () => {
        fitNextRange=true;
        const count = button.dataset.count === 'all' ? records.length : Number(button.dataset.count);
        Plotly.relayout(gd, {'xaxis.range':[Math.max(-.5,records.length-count-.5),records.length-.5]});
    });
});
document.getElementById('fit-price').addEventListener('click',()=>updateProfile(gd.layout.xaxis.range,true));
function updateProfile(range, fitPrice=true) {
    const lo = Math.max(0, Math.ceil(Number(range[0]))), hi = Math.min(records.length-1, Math.floor(Number(range[1])));
    const visible = hi>=lo ? records.slice(lo, hi+1) : [];
    document.querySelectorAll('#range-toolbar button').forEach(button => {
        const count = button.dataset.count === 'all' ? records.length : Math.min(records.length,Number(button.dataset.count));
        button.setAttribute('aria-pressed',String(hi===records.length-1 && visible.length===count));
    });
    if (!visible.length) {
        window.__volumeProfile = {first:lo,last:hi,volumes:[],centers:[],total:0,poc:null};
        document.getElementById('profile-status').textContent = '선택 범위에 봉이 없습니다.';
        document.getElementById('drawdown-status').textContent='선택 범위에 최고·최저가 정보가 없습니다.';
        const annotations=(gd.layout.annotations || []).filter(a=>!String(a.name || '').startsWith('extreme-'));
        busy=true;
        Plotly.update(gd,{x:[[]],y:[[]]},{annotations},[profileIndex]).finally(()=>{busy=false;});
        return;
    }
    let min = visible.reduce((v,r)=>Math.min(v,r[0]),Infinity), max = visible.reduce((v,r)=>Math.max(v,r[1]),-Infinity);
    const visiblePeak=max, visibleLow=min;
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
    const profileUpdate={x:[volumes], y:[centers], width:[step*.94], 'marker.color':[volumes.map((_,i)=>i===poc?'#fbbf24':'#475569')]};
    let priceMin=min, priceMax=max;
    if(averagesVisible) {
        for(const row of averages.slice(lo,hi+1)) for(const value of row) {
            if(value!==null && Number.isFinite(value)) {priceMin=Math.min(priceMin,value);priceMax=Math.max(priceMax,value);}
        }
    }
    const peakIndex=lo+visible.findIndex(row=>row[1]===visiblePeak);
    const drawdown=(ohlc[ohlc.length-1][3]/visiblePeak-1)*100;
    document.getElementById('drawdown-status').textContent=`표시 구간 최고가 ${number(visiblePeak)} (${dates[peakIndex]}) → 마지막 완료 봉 종가 ${number(ohlc[ohlc.length-1][3])}: ${drawdown>=0?'+':''}${drawdown.toFixed(2)}% · 마지막 완료 봉 ${dates[dates.length-1]}`;
    const pad=(priceMax-priceMin)*.05;
    const ticks=[]; for(let i=lo;i<=hi;i+=Math.max(1,Math.ceil((hi-lo+1)/Math.max(3,Math.floor(gd.clientWidth/130))))) ticks.push(i);
    const update={'xaxis2.autorange':true};
    if(fitPrice) {update['yaxis.range']=[priceMin-pad,priceMax+pad];update['yaxis6.range']=[0,100];}
    const lastClose=ohlc[ohlc.length-1][3];
    const troughIndex=lo+visible.findIndex(row=>row[0]===visibleLow);
    const annotations=(gd.layout.annotations || []).filter(a=>!String(a.name || '').startsWith('extreme-'));
    for(const [name,index,price,offset] of [['high',peakIndex,visiblePeak,45],['low',troughIndex,visibleLow,-45]]) {
        const percent=(lastClose/price-1)*100;
        annotations.push({name:'extreme-'+name,x:index,y:price,xref:'x',yref:'y',
            text:`${name==='high'?'최고':'최저'} ${number(price)} → 현재 ${percent>=0?'+':''}${percent.toFixed(2)}%`,
            showarrow:true,arrowhead:2,ax:index>(lo+hi)/2?-70:70,ay:offset,
            bgcolor:'#1e293b',borderpad:4,font:{size:11,color:name==='high'?'#fda4af':'#6ee7b7'}});
    }
    update.annotations=annotations;
    const lastLabel=gd.layout.annotations.findIndex(a=>a.name==='last-close');
    const priceRange=fitPrice?[priceMin-pad,priceMax+pad]:gd.layout.yaxis.range;
    annotations[lastLabel].visible=lastClose>=priceRange[0] && lastClose<=priceRange[1];
    for (const [axis, columns] of [['yaxis3',[0,9]],['yaxis4',[1,2,3]],['yaxis5',[4,5,6]],['yaxis7',[7]],['yaxis8',[10,11,12,13]]]) {
        const values = series.slice(lo,hi+1).flatMap(row=>columns.map(c=>row[c])).filter(v=>v!==null && Number.isFinite(v));
        if (axis==='yaxis8') values.push(ADX_THRESHOLD);
        if (!values.length) continue;
        let bottom=values.reduce((a,b)=>Math.min(a,b),Infinity), top=values.reduce((a,b)=>Math.max(a,b),-Infinity);
        if (axis!=='yaxis7') { bottom=Math.min(0,bottom); top=Math.max(0,top); }
        const padding=Math.max((top-bottom)*.08,Math.abs(top)*.001,.01);
        if(fitPrice) update[axis+'.range']=[bottom-padding,top+padding];
    }
    for (const axis of ['xaxis','xaxis3','xaxis4','xaxis5','xaxis6','xaxis7','xaxis8']) {
        // Set the matched root axis too; otherwise Plotly can restore its old range
        // when another pane is relaid out (e.g. after switching from all to 60 bars).
        if(gd.layout[axis].range.some((v,i)=>v!==range[i])) update[axis+'.range']=range;
        update[axis+'.autorange']=false;
        update[axis+'.tickvals']=ticks; update[axis+'.ticktext']=ticks.map(i=>dates[i]);
    }
    busy=true;
    Plotly.update(gd,profileUpdate,update,[profileIndex]).finally(()=>{busy=false;});
}
let profileTimer;
function scheduleProfile(range) {
    clearTimeout(profileTimer);
    profileTimer=setTimeout(()=>{if(busy) scheduleProfile(range); else {const fit=fitNextRange;fitNextRange=false;updateProfile(range,fit);}},140);
}
gd.on('plotly_relayout', event => {
    if (busy) return;
    const changed=Object.keys(event).find(k=>/^xaxis(?!2[.])\d*[.](range|autorange)/.test(k));
    if (!changed) return;
    hideCrosshair();
    const axis=changed.split('.')[0];
    let range = event[axis+'.autorange'] ? [-.5, records.length-.5] : event[axis+'.range'];
    if (!range && event[axis+'.range[0]']!==undefined) range=[event[axis+'.range[0]'],event[axis+'.range[1]']];
    if (!range) range=gd.layout[axis].range;
    scheduleProfile(range);
});
// Coalesce high-frequency trackpad/wheel events; never overlap Plotly redraws.
let wheelTarget=null, wheelFrame=null, wheelDrawing=false;
let verticalTargets={};
const timeAxes=['xaxis','xaxis3','xaxis4','xaxis5','xaxis6','xaxis7','xaxis8'];
function boundedRange(left,width) {
    width=Math.max(Math.min(10,records.length),Math.min(records.length+10,width));
    left=Math.max(-5.5,Math.min(records.length+4.5-width,left));
    return [left,left+width];
}
function renderWheel() {
    wheelFrame=null;
    if(!wheelTarget && !Object.keys(verticalTargets).length) return;
    if(busy || wheelDrawing) {wheelFrame=requestAnimationFrame(renderWheel);return;}
    const range=wheelTarget ? wheelTarget.slice() : null;
    const vertical={...verticalTargets};
    wheelDrawing=true;
    const update={};
    if(range) timeAxes.forEach(axis=>{update[axis+'.range']=range;update[axis+'.autorange']=false;});
    Object.entries(vertical).forEach(([axis,values])=>{update[axis+'.range']=values;update[axis+'.autorange']=false;});
    Plotly.relayout(gd,update).finally(()=>{
        wheelDrawing=false;
        Object.entries(vertical).forEach(([axis,values])=>{
            if(verticalTargets[axis]===values) delete verticalTargets[axis];
        });
        if(range && wheelTarget && wheelTarget.every((v,i)=>v===range[i])) wheelTarget=null;
        if(wheelTarget || Object.keys(verticalTargets).length) {
            wheelFrame=requestAnimationFrame(renderWheel);
        } else {wheelTarget=null;scheduleProfile(gd.layout.xaxis.range);}
    });
}
document.addEventListener('pointerdown',()=>{
    wheelTarget=null;
    verticalTargets={};
    if(wheelFrame) cancelAnimationFrame(wheelFrame);
    wheelFrame=null;
},true);
// Explicit hit targets cover the actual tick labels, including label overflow.
const verticalAxes=['yaxis','yaxis3','yaxis4','yaxis5','yaxis6','yaxis7','yaxis8'];
function positionAxisControls() {
    const layout=gd._fullLayout;
    if(!layout) return;
    verticalAxes.forEach(key=>{
        let control=gd.querySelector('[data-wheel-axis="'+key+'"]');
        if(!control) {
            control=document.createElement('div');
            control.dataset.wheelAxis=key;
            control.className='axis-wheel-control';
            control.title='드래그: 세로 확대·축소 · 휠: 세로 확대·축소 · 세로 맞춤: 복원';
            let drag=null;
            control.addEventListener('pointerdown',event=>{
                if(event.button!==0) return;
                event.preventDefault();event.stopPropagation();
                clearTimeout(profileTimer);hideCrosshair();
                const axis=gd._fullLayout[key];
                drag={id:event.pointerId,y:event.clientY,range:gd.layout[key].range.slice(),height:axis._length};
                control.setPointerCapture(event.pointerId);
                control.classList.add('axis-dragging');
            });
            control.addEventListener('pointermove',event=>{
                if(!drag || drag.id!==event.pointerId) return;
                event.preventDefault();event.stopPropagation();
                const center=(drag.range[0]+drag.range[1])/2;
                const factor=Math.exp(Math.max(-6,Math.min(6,(event.clientY-drag.y)/drag.height*2)));
                const half=(drag.range[1]-drag.range[0])*factor/2;
                verticalTargets[key]=[center-half,center+half];
                if(!wheelFrame && !wheelDrawing) wheelFrame=requestAnimationFrame(renderWheel);
            });
            const finish=event=>{
                if(!drag || drag.id!==event.pointerId) return;
                drag=null;
                control.classList.remove('axis-dragging');
                if(control.hasPointerCapture(event.pointerId)) control.releasePointerCapture(event.pointerId);
            };
            control.addEventListener('pointerup',finish);
            control.addEventListener('pointercancel',finish);
            control.addEventListener('lostpointercapture',finish);
            gd.appendChild(control);
        }
        const a=layout[key], right=layout.xaxis._offset+layout.xaxis._length;
        const ticks=gd.querySelectorAll('.'+(key==='yaxis'?'y':key.replace('axis',''))+'tick text');
        let edge=right+64;
        const box=gd.getBoundingClientRect();
        ticks.forEach(t=>{edge=Math.max(edge,t.getBoundingClientRect().right-box.left+8);});
        Object.assign(control.style,{left:(right-4)+'px',top:a._offset+'px',
            width:Math.min(gd.clientWidth-right+4,edge-right+4)+'px',height:a._length+'px'});
    });
}
gd.on('plotly_afterplot',positionAxisControls);
positionAxisControls();
gd.addEventListener('wheel',event=>{
    if(event.ctrlKey || event.metaKey) return;
    const rect=gd.getBoundingClientRect(), layout=gd._fullLayout, axis=layout.xaxis;
    const px=event.clientX-rect.left, py=event.clientY-rect.top;
    const right=axis._offset+axis._length;
    const gutterEnd=Math.min(gd.clientWidth,layout.xaxis2._offset);
    const hitAxis=event.target.closest('[data-wheel-axis]')?.dataset.wheelAxis;
    const verticalAxis=hitAxis || verticalAxes.find(key=>{
        const a=layout[key];return py>=a._offset && py<=a._offset+a._length;
    });
    if(verticalAxis && (hitAxis || (px>=right-4 && px<gutterEnd))) {
        event.preventDefault();event.stopPropagation();
        clearTimeout(profileTimer);hideCrosshair();
        const a=layout[verticalAxis], values=verticalTargets[verticalAxis] || gd.layout[verticalAxis].range;
        const fraction=1-(py-a._offset)/a._length, width=values[1]-values[0];
        const unit=event.deltaMode===1?16:event.deltaMode===2?gd.clientHeight:1;
        const delta=Math.max(-120,Math.min(120,event.deltaY*unit));
        const reference=Math.max(Math.abs(values[0]),Math.abs(values[1]),1);
        const span=Math.max(reference*1e-8,Math.min(reference*1e6,width*Math.exp(delta*.0015)));
        const anchor=values[0]+fraction*width;
        verticalTargets[verticalAxis]=[anchor-fraction*span,anchor+(1-fraction)*span];
        if(!wheelFrame && !wheelDrawing) wheelFrame=requestAnimationFrame(renderWheel);
        return;
    }
    if(px<axis._offset || px>axis._offset+axis._length || py<layout._size.t || py>layout._size.t+layout._size.h) return;
    event.preventDefault();
    event.stopPropagation();
    clearTimeout(profileTimer);
    hideCrosshair();
    const range=wheelTarget || gd.layout.xaxis.range;
    const width=range[1]-range[0], fraction=(px-axis._offset)/axis._length;
    const unit=event.deltaMode===1?16:event.deltaMode===2?gd.clientHeight:1;
    const horizontal=event.shiftKey || Math.abs(event.deltaX)>Math.abs(event.deltaY);
    const raw=(horizontal && event.deltaX ? event.deltaX : event.deltaY)*unit;
    const delta=Math.max(-120,Math.min(120,raw));
    if(horizontal) wheelTarget=boundedRange(range[0]+delta*width/600,width);
    else {
        const nextWidth=Math.max(Math.min(10,records.length),Math.min(records.length+10,width*Math.exp(delta*.0015)));
        wheelTarget=boundedRange(range[0]+fraction*(width-nextWidth),nextWidth);
    }
    if(!wheelFrame && !wheelDrawing) wheelFrame=requestAnimationFrame(renderWheel);
},{passive:false,capture:true});
// Touch gestures are handled before Plotly's one-finger drag recognizer.
let pinch=null, finishingPinch=false;
function touchGeometry(touches) {
    const box=gd.getBoundingClientRect(), a=touches[0], b=touches[1];
    return {x:(a.clientX+b.clientX)/2-box.left,y:(a.clientY+b.clientY)/2-box.top,
        distance:Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY)};
}
gd.addEventListener('touchstart',event=>{
    if(!['pan','zoom'].includes(gd.layout.dragmode)) return;
    if(event.touches.length===1) {event.stopPropagation();return;}
    if(event.touches.length!==2) return;
    const point=touchGeometry(event.touches), layout=gd._fullLayout, x=layout.xaxis;
    const key=verticalAxes.find(key=>{const a=layout[key];return point.y>=a._offset && point.y<=a._offset+a._length;});
    if(!key || point.x<x._offset || point.x>x._offset+x._length || point.distance<10) return;
    event.preventDefault();event.stopPropagation();
    clearTimeout(profileTimer);hideCrosshair();
    const y=layout[key], xr=gd.layout.xaxis.range.slice(), yr=gd.layout[key].range.slice();
    pinch={key,distance:point.distance,xrange:xr,yrange:yr,
        xanchor:xr[0]+(point.x-x._offset)/x._length*(xr[1]-xr[0]),
        yanchor:yr[0]+(1-(point.y-y._offset)/y._length)*(yr[1]-yr[0])};
    finishingPinch=true;
},{passive:false,capture:true});
gd.addEventListener('touchmove',event=>{
    if(!pinch || event.touches.length!==2) {
        if(finishingPinch) {event.preventDefault();event.stopPropagation();}
        else if(['pan','zoom'].includes(gd.layout.dragmode)) event.stopPropagation();
        return;
    }
    event.preventDefault();event.stopPropagation();
    clearTimeout(profileTimer);
    const point=touchGeometry(event.touches), x=gd._fullLayout.xaxis,y=gd._fullLayout[pinch.key];
    const ratio=Math.max(.01,Math.min(100,pinch.distance/Math.max(10,point.distance)));
    const width=Math.max(Math.min(10,records.length),Math.min(records.length+10,(pinch.xrange[1]-pinch.xrange[0])*ratio));
    const xf=(point.x-x._offset)/x._length, yf=1-(point.y-y._offset)/y._length;
    wheelTarget=boundedRange(pinch.xanchor-xf*width,width);
    const height=(pinch.yrange[1]-pinch.yrange[0])*ratio;
    verticalTargets[pinch.key]=[pinch.yanchor-yf*height,pinch.yanchor+(1-yf)*height];
    if(!wheelFrame && !wheelDrawing) wheelFrame=requestAnimationFrame(renderWheel);
},{passive:false,capture:true});
function endPinch(event) {
    if(finishingPinch) {event.stopPropagation();}
    if(event.touches.length<2) pinch=null;
    if(event.touches.length===0) finishingPinch=false;
}
gd.addEventListener('touchend',endPinch,{capture:true});
gd.addEventListener('touchcancel',event=>{pinch=null;finishingPinch=false;},{capture:true});
let resizeTimer;
window.addEventListener('resize',()=>{
    clearTimeout(resizeTimer);
    resizeTimer=setTimeout(()=>scheduleProfile(gd.layout.xaxis.range),200);
});
updateProfile([START, END]);
'''
    values = frame[['Volume','MACD6','Signal6','Histogram6','MACD','Signal','Histogram','OBV','RSI','VolumeAvg20','PlusDI','MinusDI','ADX','ADXR']].to_json(orient='values')
    script = (script.replace('RECORDS', json.dumps(records)).replace('OHLC', frame[['Open','High','Low','Close']].to_json(orient='values')).replace('SERIES',values).replace('DATES',json.dumps(dates))
              .replace('AVERAGES', frame[[f'MA{window}' for window in MA_WINDOWS]].to_json(orient='values'))
              .replace('ADX_THRESHOLD', str(float(adx_threshold))).replace('BINS', str(int(bins))).replace('PROFILE',str(profile_index))
              .replace('START',str(start-.5)).replace('END',str(len(frame)-.5)))
    html = fig.to_html(full_html=True, include_plotlyjs=True, div_id='analysis-chart', post_script=script,
                       config={'scrollZoom':False,'displaylogo':False,'responsive':True,'displayModeBar':False,
                               'modeBarButtonsToAdd':['drawline','drawrect','eraseshape'], 'toImageButtonOptions':{'filename':'chart-analysis'}})
    toolbar = '''<style>
    * {box-sizing:border-box;}
    #chart-toolbar {display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;padding:6px 10px;background:#171c28;border-bottom:1px solid #2a3140;}
    #range-toolbar,#tools {display:flex;gap:3px;flex-wrap:wrap;}
    #tools {width:100%;border-top:1px solid #2a3140;padding-top:4px;}
    #drawing-picker {background:#1e293b;color:#e2e8f0;border:1px solid #475569;border-radius:4px;padding:6px;max-width:180px;}
    @media(pointer:coarse){#chart-toolbar button,#drawing-picker{min-height:44px;}}
    #candle-readout {padding:8px 14px 2px;font-size:13px;line-height:1.7;font-variant-numeric:tabular-nums;min-height:32px;}
    #indicator-readout {padding:2px 14px;font-size:11px;color:#c4b5fd;line-height:1.7;min-height:23px;font-variant-numeric:tabular-nums;}
    #chart-toolbar button {background:transparent;color:#cbd5e1;border:1px solid transparent;border-radius:4px;padding:6px 9px;cursor:pointer;font-size:12px;}
    #chart-toolbar button:hover {background:#293346;color:white;}
    #chart-toolbar button[aria-pressed="true"] {background:#24385c;color:#93bbff;border-color:#3b5989;}
    #chart-toolbar button:focus-visible {outline:2px solid #fbbf24;outline-offset:2px;}
    #chart-toolbar button:disabled {opacity:.4;cursor:default;}
    #analysis-chart:focus {outline:none;}
    #analysis-chart:focus-visible {outline:1px solid #60a5fa;outline-offset:-1px;}
    .selected-drawing path {filter:drop-shadow(0 0 3px #93c5fd);stroke:#93c5fd!important;}
    #drawing-status {padding:2px 14px;font-size:11px;color:#94a3b8;}
    .axis-wheel-control {position:absolute;z-index:30;pointer-events:auto;cursor:ns-resize;background:transparent;touch-action:none;user-select:none;}
    .axis-wheel-control:hover,.axis-wheel-control.axis-dragging {background:rgba(96,165,250,.12);border-right:2px solid #60a5fa;}
    #analysis-chart .nsewdrag {touch-action:pan-y;}
    .crosshair {position:absolute;pointer-events:none;z-index:20;display:none;}
    #cross-v {border-left:1px dashed #959eaf;}
    #cross-h {border-top:1px dashed #959eaf;}
    #cross-date,#cross-value {background:#364155;color:#fff;padding:3px 5px;font-size:11px;white-space:nowrap;border-radius:2px;}
    #cross-date {transform:translateX(-50%);}
    #cross-value {transform:translateY(-50%);}
    @media(max-width:650px) {#chart-toolbar{justify-content:flex-start;}#chart-toolbar button{padding:6px;}#indicator-readout{font-size:10px;}}
    </style><div id="chart-toolbar"><nav id="range-toolbar" aria-label="차트 표시 범위">
    <button type="button" data-count="60" aria-pressed="true">최근 60봉</button>
    <button type="button" data-count="180" aria-pressed="false">최근 180봉</button>
    <button type="button" data-count="all" aria-pressed="false">전체</button>
    </nav><nav id="tools" aria-label="차트 조작 도구">
    <button type="button" data-mode="pan" aria-pressed="true" title="차트 안에서 상하좌우 드래그로 이동">이동</button>
    <button type="button" data-mode="zoom" aria-pressed="false" title="드래그한 구간 확대">확대</button>
    <button type="button" id="fib-tool" aria-pressed="false" title="가격 차트에서 시작점부터 끝점까지 드래그 · 기준선 선택 후 Del 삭제">피보나치 되돌림</button>
    <button type="button" id="measure-tool" aria-pressed="false" title="시작 가격에서 끝 가격으로 드래그">측정 ↗</button>
    <button type="button" data-mode="drawline" aria-pressed="false">추세선</button>
    <button type="button" data-mode="drawrect" aria-pressed="false">사각형</button>
    <button type="button" id="delete-shape" disabled title="선택한 도형 삭제 (Delete)">선택 삭제</button>
    <select id="drawing-picker" aria-label="삭제할 도형 선택"><option value="">도형 선택</option></select>
    <button type="button" id="clear-drawings" disabled title="직접 그린 도형만 모두 삭제">도형 전체 삭제</button>
    <button type="button" id="toggle-ma" aria-pressed="true" title="이동평균선 표시 전환">MA</button>
    <button type="button" id="fit-price" title="표시 구간에 세로 눈금 맞추기">세로 맞춤</button>
    <button type="button" id="reset-view" title="최근 60봉과 자동 눈금으로 돌아가기">기본 보기</button>
    <button type="button" id="save-image" title="차트를 PNG 이미지로 저장">PNG 저장</button>
    </nav></div><div id="candle-readout" aria-live="off"></div><div id="indicator-readout" aria-live="off"></div><div id="drawing-status" role="status"></div><div id="drawdown-status" style="padding:3px 14px;font-size:12px;color:#93c5fd"></div><div id="profile-status" style="padding:3px 14px 6px;font-size:11px;color:#8e9bb0"></div>'''
    return html.replace('<body>', '<body style="margin:0;background:#131722;color:#cbd5e1;font-family:sans-serif">'+toolbar)
