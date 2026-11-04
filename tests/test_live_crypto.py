import unittest
from unittest.mock import patch
import pandas as pd
from market_data import demo_prices
from live_crypto import live_indicators, merge_recent, message_html
from analysis import indicators


class LiveCryptoTests(unittest.TestCase):
    def raw(self, frequency='D'):
        raw = demo_prices().copy()
        raw.index = pd.date_range('2020-01-01', periods=len(raw), freq=frequency)
        return raw

    def test_latest_candle_replaced_not_duplicated(self):
        raw = self.raw()
        recent = raw.tail(2).copy()
        recent.iloc[-1, recent.columns.get_loc('Volume')] = 98765
        merged = merge_recent(raw, recent)
        self.assertEqual(len(merged), len(raw))
        self.assertEqual(merged.Volume.iloc[-1], 98765)
        self.assertTrue(merged.iloc[:-2].equals(raw.iloc[:-2]))

    def test_signals_only_confirm_on_close_for_all_intervals(self):
        for timeframe, frequency in [('일봉','D'), ('4시간봉','4h'), ('주봉','D')]:
            raw = self.raw(frequency)
            now = raw.index[-1] + pd.Timedelta(hours=1)
            def flagged(*args):
                result = indicators(*args)
                result['DIBuySignal'] = True
                result['MACD19SellSignal'] = True
                return result
            with patch('live_crypto.indicators', side_effect=flagged):
                frame, pending = live_indicators(raw, timeframe, '바이낸스', 14, 14, 14, now)
                self.assertEqual(pending, 1)
                self.assertFalse(frame.DIBuySignal.iloc[-1])
                self.assertFalse(frame.MACD19SellSignal.iloc[-1])
                self.assertTrue(frame.DIBuySignal.iloc[-2])
                closed, pending = live_indicators(raw, timeframe, '바이낸스', 14, 14, 14, now + pd.Timedelta(days=8))
                self.assertEqual(pending, 0)
                self.assertTrue(closed.DIBuySignal.iloc[-1])

    def test_long_gap_and_script_escaping(self):
        raw = self.raw()
        recent = raw.tail(1).copy()
        recent.index += pd.Timedelta(days=40)
        with self.assertRaises(ValueError):
            merge_recent(raw, recent)
        html = message_html({'error':'</script><script>alert(1)</script>'})
        self.assertEqual(html.count('</script>'), 1)

    def test_streamlit_poll_renders_delivery_frame(self):
        from streamlit.testing.v1 import AppTest
        raw = self.raw()
        with patch('live_crypto.fetch_crypto', return_value=(raw.tail(30), 'test', 'BTCUSDT')):
            app = AppTest.from_string('''
import streamlit as st
import pandas as pd
from market_data import demo_prices
from live_crypto import render_live_updates
raw=demo_prices()
raw.index=pd.date_range('2020-01-01',periods=len(raw),freq='D')
render_live_updates(raw,'BTCUSDT','바이낸스','일봉',32,20,(14,14,14),'test-token')
''', default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get('iframe')), 1)
        self.assertIn('chart-live', app.get('iframe')[0].proto.srcdoc)
        self.assertIn('"payload"', app.get('iframe')[0].proto.srcdoc)
