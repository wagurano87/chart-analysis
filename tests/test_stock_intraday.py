import unittest
from unittest.mock import patch
import pandas as pd
from market_data import stock_four_hour

class StockIntradayTests(unittest.TestCase):
    def test_session_bars_across_dst(self):
        index=pd.date_range('2026-10-30 09:30',periods=7,freq='h',tz='America/New_York').append(pd.date_range('2026-11-02 09:30',periods=7,freq='h',tz='America/New_York'))
        raw=pd.DataFrame({'Open':10.,'High':12.,'Low':9.,'Close':11.,'Volume':100.},index=index)
        with patch('yfinance.download',return_value=raw):
            result=stock_four_hour('AAPL','미국',pd.Timestamp('2026-11-02 17:00',tz='America/New_York'))
            self.assertEqual(result.index.strftime('%H:%M').tolist(),['09:30','13:30','09:30','13:30'])
            self.assertEqual(result.Volume.tolist(),[400,300,400,300])
            before=stock_four_hour('AAPL','미국',pd.Timestamp('2026-11-02 12:00',tz='America/New_York'))
            self.assertEqual(len(before),2)
