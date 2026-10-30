import unittest
import pandas as pd
from fundamentals import quarterly_metrics, positive_number

class FinancialTests(unittest.TestCase):
    def test_order_limit_and_margin(self):
        dates=pd.date_range('2023-03-31',periods=10,freq='QE')[::-1]
        frame=pd.DataFrame([[100]*10,[-10]*10],index=['Total Revenue','Operating Income'],columns=dates)
        result=quarterly_metrics(frame)
        self.assertEqual(len(result),8)
        self.assertTrue(result.index.is_monotonic_increasing)
        self.assertTrue((result['영업이익률']==-10).all())
    def test_missing_is_not_zero(self):
        frame=pd.DataFrame([[0,100]],index=['Total Revenue'],columns=['2025-03-31','2025-06-30'])
        result=quarterly_metrics(frame)
        self.assertTrue(result['영업이익률'].isna().all())
        self.assertTrue(result['영업이익'].isna().all())
    def test_invalid_peg(self):
        for value in [None,'N/A',0,-1,float('inf')]:
            self.assertIsNone(positive_number(value))
        self.assertEqual(positive_number('1.2'),1.2)

    def test_two_by_two_charts_with_provider_fixture(self):
        from pathlib import Path
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        from data import demo_prices
        dates=pd.date_range('2024-03-31',periods=8,freq='QE')
        frame=pd.DataFrame({'매출액':[100e6]*8,'영업이익':[10e6]*8,'영업이익률':[10.0]*8},index=dates)
        with patch('data.fetch_prices',return_value=(demo_prices(),'TEST.KS','KRX:TEST')), patch('fundamentals.fetch_fundamentals',return_value=(frame,'KRW',1.2)):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            app.button[0].click().run()
            app.button(key='load_financials').click().run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(len(app.get('plotly_chart')),4)

    def test_etf_has_specific_explanation_without_income_request(self):
        from unittest.mock import patch, PropertyMock
        from fundamentals import fetch_fundamentals, UnsupportedFinancials
        with patch('yfinance.Ticker') as factory:
            ticker=factory.return_value
            ticker.get_info.return_value={'quoteType':'ETF','longName':'Example International ETF'}
            income=PropertyMock(side_effect=AssertionError('ETF income must not be requested'))
            type(ticker).quarterly_income_stmt=income
            with self.assertRaisesRegex(UnsupportedFinancials,'기업 분기 손익계산서'):
                fetch_fundamentals('INTL')
            income.assert_not_called()

    def test_equity_with_missing_statement_is_distinguished(self):
        from unittest.mock import patch
        from fundamentals import fetch_fundamentals
        with patch('yfinance.Ticker') as factory:
            factory.return_value.get_info.return_value={'quoteType':'EQUITY'}
            factory.return_value.quarterly_income_stmt=pd.DataFrame()
            with self.assertRaisesRegex(ValueError,'반환하지 않았습니다'):
                fetch_fundamentals('AAPL')
