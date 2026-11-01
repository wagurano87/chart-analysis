import unittest
from unittest.mock import patch
from pathlib import Path
from symbol_search import search_symbols, normalize_quotes
from streamlit.testing.v1 import AppTest

class SearchTests(unittest.TestCase):
    def test_korean_alias_offline(self):
        with patch('yfinance.Search',side_effect=AssertionError('offline')):
            result,_=search_symbols('삼성전자')
            self.assertEqual(result[0][1],'005930')
            self.assertEqual(search_symbols('엔비디아')[0][0][1],'NVDA')
    def test_exchange_filter(self):
        result=normalize_quotes([
            {'symbol':'000660.KS','quoteType':'EQUITY'},
            {'symbol':'TEST','exchange':'NYQ','quoteType':'EQUITY'},
            {'symbol':'TEST.L','exchange':'LSE','quoteType':'EQUITY'},
            {'symbol':'TEST','exchange':'NYQ','quoteType':'EQUITY'}])
        self.assertEqual([v[1] for v in result],['000660','TEST'])
    def test_apply_updates_market_and_ticker(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
        app.text_input[1].set_value('엔비디아')
        app.button[1].click().run()
        next(b for b in app.button if b.label=='선택 종목 입력').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input(key='analysis_ticker').value,'NVDA')
        self.assertEqual(app.selectbox(key='analysis_market').value,'미국')
