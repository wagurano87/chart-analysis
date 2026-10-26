import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from data import demo_prices

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class AppTests(unittest.TestCase):
    def test_demo_analysis_is_usable_without_network(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        app.selectbox[0].select("가상 데이터 체험")
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 7)
        self.assertTrue(any("가상" in item.value for item in app.warning))
        self.assertTrue(any("매도 검토 경고" in item.value for item in app.error))
        self.assertEqual(len(app.get("iframe")), 1)

    def test_invalid_symbol_shows_error_without_results(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.text_input[0].set_value("<invalid>")
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("6자리" in item.value for item in app.error))
        self.assertEqual(len(app.metric), 0)

    def test_online_result_builds_tradingview_and_same_data_chart(self):
        with patch("data.fetch_prices", return_value=(demo_prices(), "005930.KS", "KRX:005930")):
            app = AppTest.from_file(APP, default_timeout=30).run()
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 7)
        self.assertEqual(len(app.get("iframe")), 2)
        self.assertIn('KRX:005930', app.get("iframe")[1].proto.srcdoc)

    def test_failed_request_clears_previous_signals(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.selectbox[0].select("가상 데이터 체험")
        app.button[0].click().run()
        self.assertEqual(len(app.metric), 7)
        app.selectbox[0].select("CSV 업로드")
        app.button[0].click().run()
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("CSV 파일" in item.value for item in app.error))

    def test_weekly_toggle_recalculates_existing_data(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.selectbox[0].select("가상 데이터 체험")
        app.button[0].click().run()
        daily_macd = app.metric[1].value
        app.radio[0].set_value("주봉").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 7)
        self.assertNotEqual(app.metric[1].value, daily_macd)
        self.assertTrue(any("주봉 종합" in v.value for v in app.subheader))
        self.assertIn('MACD 6', app.get('iframe')[0].proto.srcdoc)


if __name__ == "__main__":
    unittest.main()
