import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import pandas as pd
from crypto_data import crypto_symbol, fetch_crypto
from analysis import completed_daily_bars, resample_bars

class CryptoTests(unittest.TestCase):
    def test_symbols(self):
        self.assertEqual(crypto_symbol('btc/usdt','바이낸스'),'BTCUSDT')
        self.assertEqual(crypto_symbol('krw-btc','업비트'),'KRW-BTC')
        with self.assertRaises(ValueError):crypto_symbol('BTC','업비트')
    def test_binance_pages(self):
        rows=[[i*86400000,10,12,9,11,100] for i in range(1001)]
        with patch('crypto_data._get',side_effect=[rows[1:],rows[:1]]) as request:
            frame,_,_=fetch_crypto('BTCUSDT','바이낸스',1001)
            self.assertEqual(len(frame),1001)
            self.assertEqual(request.call_args_list[1].args[1]['endTime'],86400000-1)
    def test_upbit_fields(self):
        row={'candle_date_time_utc':'2026-10-30T00:00:00','opening_price':10,'high_price':12,'low_price':9,'trade_price':11,'candle_acc_trade_volume':100}
        with patch('crypto_data._get',return_value=[row]):
            frame,_,_=fetch_crypto('KRW-BTC','업비트')
            self.assertEqual(frame.iloc[0].Volume,100)
    def test_utc_completed_weeks(self):
        frame=pd.DataFrame({'Open':10,'High':12,'Low':9,'Close':11,'Volume':100},index=pd.date_range('2026-10-19',periods=15))
        now=datetime(2026,11,2,0,0,tzinfo=timezone.utc)
        daily=completed_daily_bars(frame,'업비트',now)
        self.assertEqual(len(daily),14)
        weekly=resample_bars(frame,'업비트','주봉',now)
        self.assertEqual(len(weekly),2)
        self.assertEqual(weekly.iloc[-1].Volume,700)
