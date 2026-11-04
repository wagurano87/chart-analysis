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
            for query in ['대한광통신', '대한 광통신', '010170', 'Taihan Fiberoptics']:
                self.assertEqual(search_symbols(query)[0][0][:3], ('대한광통신', '010170', '한국'))
    def test_exchange_filter(self):
        result=normalize_quotes([
            {'symbol':'000660.KS','quoteType':'EQUITY'},
            {'symbol':'TEST','exchange':'NYQ','quoteType':'EQUITY'},
            {'symbol':'TEST.L','exchange':'LSE','quoteType':'EQUITY'},
            {'symbol':'TEST','exchange':'NYQ','quoteType':'EQUITY'}])
        self.assertEqual([v[1] for v in result],['000660','TEST'])
    def test_apply_updates_market_and_ticker(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
        for query, code, market in [('인텔', 'INTC', '미국'), ('삼성전자 ·', '005930', '한국')]:
            picker=app.selectbox(key='symbol_entry')
            label=next(v for v in picker.options if v.startswith(query))
            picker.select(label).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['analysis_ticker'], code)
            self.assertEqual(app.selectbox(key='analysis_market').value, market)
        self.assertFalse(any(e.label == '🔎 종목명으로 코드 찾기' for e in app.expander))

    def test_remote_candidates_require_selection(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
        with patch('symbol_search.search_symbols', return_value=([('Example', 'EXM', '미국', 'EQUITY')], '')):
            app.selectbox(key='symbol_entry').options.append('Example')
            app.selectbox(key='symbol_entry').set_value('Example').run()
        self.assertTrue(next(b for b in app.button if b.label == '분석하기').disabled)
        app.selectbox(key='symbol_entry').select('Example · EXM · 미국').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['analysis_ticker'], 'EXM')
        self.assertEqual(app.selectbox(key='analysis_market').value, '미국')
        self.assertFalse(next(b for b in app.button if b.label == '분석하기').disabled)
