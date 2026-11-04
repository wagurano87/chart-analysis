import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from market_data import demo_prices

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class AppTests(unittest.TestCase):
    def test_binance_favorites_apply_and_analyze(self):
        with patch('market_data.fetch_prices', return_value=(demo_prices(), '바이낸스', 'BTCUSDT')) as fetch:
            app = AppTest.from_file(APP, default_timeout=30).run()
            for key, symbol in [('favorite_btc', 'BTCUSDT'), ('favorite_eth', 'ETHUSDT')]:
                app.button(key=key).click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox(key='analysis_market').value, '바이낸스')
                self.assertEqual(app.selectbox(key='analysis_mode').value, '온라인 시세')
                self.assertEqual(app.text_input(key='analysis_ticker').value, symbol)
                fetch.assert_called_with(symbol, '바이낸스', 'NASDAQ')
                self.assertEqual(len(app.get('iframe')), 1)
                with self.assertRaises(KeyError):
                    app.session_state['favorite_requested']

    def test_startup_with_old_data_module_present(self):
        import sys
        import types
        stale = types.ModuleType('data')
        with patch.dict(sys.modules, {'data': stale}):
            app = AppTest.from_file(APP, default_timeout=30).run()
            self.assertEqual(len(app.exception), 0)
            app.selectbox[0].select('가상 데이터 체험')
            next(b for b in app.button if b.label == "분석하기").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.get('iframe')), 1)

    def test_demo_analysis_is_usable_without_network(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        app.selectbox[0].select("가상 데이터 체험")
        next(b for b in app.button if b.label == "분석하기").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 7)
        self.assertTrue(any("가상" in item.value for item in app.warning))
        self.assertTrue(any("매도 검토 경고" in item.value for item in app.error))
        self.assertEqual(len(app.get("iframe")), 1)

    def test_invalid_symbol_shows_error_without_results(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.text_input[0].set_value("<invalid>")
        next(b for b in app.button if b.label == "분석하기").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("6자리" in item.value for item in app.error))
        self.assertEqual(len(app.metric), 0)

    def test_online_result_shows_only_analysis_chart(self):
        with patch("market_data.fetch_prices", return_value=(demo_prices(), "005930.KS", "KRX:005930")):
            app = AppTest.from_file(APP, default_timeout=30).run()
            next(b for b in app.button if b.label == "분석하기").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 7)
        self.assertEqual(len(app.get("iframe")), 1)
        self.assertIn('analysis-chart', app.get("iframe")[0].proto.srcdoc)
        self.assertNotIn('s3.tradingview.com', app.get("iframe")[0].proto.srcdoc)

    def test_failed_request_clears_previous_signals(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.selectbox[0].select("가상 데이터 체험")
        next(b for b in app.button if b.label == "분석하기").click().run()
        self.assertEqual(len(app.metric), 7)
        app.selectbox[0].select("CSV 업로드")
        next(b for b in app.button if b.label == "분석하기").click().run()
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("CSV 파일" in item.value for item in app.error))

    def test_weekly_toggle_recalculates_existing_data(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.selectbox[0].select("가상 데이터 체험")
        next(b for b in app.button if b.label == "분석하기").click().run()
        daily_macd = app.metric[1].value
        app.radio[0].set_value("주봉").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 7)
        self.assertNotEqual(app.metric[1].value, daily_macd)
        self.assertTrue(any("주봉 · 마지막 완료 봉" in v.value for v in app.caption))
        self.assertIn('MACD 6', app.get('iframe')[0].proto.srcdoc)


if __name__ == "__main__":
    unittest.main()
