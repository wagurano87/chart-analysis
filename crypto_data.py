"""Public spot OHLCV only: no API keys, accounts or trading endpoints."""
import re
import time
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import pandas as pd
from analysis import validate_prices

CRYPTO_MARKETS = {'바이낸스', '업비트'}


def crypto_symbol(value, market):
    value=value.strip().upper()
    if market == '바이낸스':
        value=value.replace('/','').replace('-','')
        if not re.fullmatch(r'[A-Z0-9]{5,24}',value):
            raise ValueError('바이낸스 현물 거래쌍을 입력하세요. 예: BTCUSDT, ETHUSDT')
    else:
        value=value.replace('/','-')
        if not re.fullmatch(r'(KRW|BTC|USDT)-[A-Z0-9]{1,20}',value):
            raise ValueError('업비트 거래쌍을 입력하세요. 예: KRW-BTC, KRW-ETH')
    return value


def _get(url, params):
    request=Request(url+'?'+urlencode(params),headers={'User-Agent':'ChartAnalysis/1.0'})
    with urlopen(request,timeout=15) as response:
        return json.load(response)


def fetch_crypto(value, market, limit=1500):
    symbol=crypto_symbol(value,market)
    rows=[]
    cursor=None
    try:
        while len(rows)<limit:
            count=min(limit-len(rows),1000 if market=='바이낸스' else 200)
            if market=='바이낸스':
                params={'symbol':symbol,'interval':'1d','limit':count}
                if cursor is not None: params['endTime']=cursor
                batch=_get('https://api.binance.com/api/v3/klines',params)
                if not isinstance(batch,list): raise ValueError('거래쌍 응답이 올바르지 않습니다.')
                if not batch: break
                rows.extend([[pd.to_datetime(r[0],unit='ms'),*map(float,r[1:6])] for r in batch])
                next_cursor=int(batch[0][0])-1
            else:
                params={'market':symbol,'count':count}
                if cursor is not None: params['to']=cursor
                batch=_get('https://api.upbit.com/v1/candles/days',params)
                if not isinstance(batch,list): raise ValueError('거래쌍 응답이 올바르지 않습니다.')
                if not batch: break
                rows.extend([[pd.Timestamp(r['candle_date_time_utc']),r['opening_price'],r['high_price'],r['low_price'],r['trade_price'],r['candle_acc_trade_volume']] for r in batch])
                next_cursor=batch[-1]['candle_date_time_utc']+'Z'
            if cursor==next_cursor: break
            cursor=next_cursor
            if len(batch)<count: break
            if market=='업비트': time.sleep(.13)
    except Exception as error:
        raise RuntimeError(f'{market} 공개 시세 조회에 실패했습니다. 거래쌍·상장 상태와 거래소의 지역/IP 접근 제한을 확인하세요. 일부 데이터만으로 분석하지 않습니다.') from error
    if not rows: raise ValueError('해당 거래쌍의 일봉이 없습니다.')
    frame=pd.DataFrame(rows,columns=['Date','Open','High','Low','Close','Volume']).set_index('Date')
    frame=frame.loc[~frame.index.duplicated()].sort_index().tail(limit)
    return validate_prices(frame), f'{market} · {symbol}', symbol


def quote_currency(value,market):
    symbol=crypto_symbol(value,market)
    if market=='업비트': return symbol.split('-')[0]
    for quote in ['FDUSD','USDT','USDC','TUSD','BTC','ETH','BNB','EUR','TRY']:
        if symbol.endswith(quote): return quote
    return '호가 통화'
