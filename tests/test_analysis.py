from datetime import datetime, timezone
import io
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from analysis import assess, completed_daily_bars, indicators, validate_prices
from data import demo_prices, fetch_prices, read_csv, symbols


class AnalysisTests(unittest.TestCase):
    def test_macd_matches_independent_recursive_ema(self):
        frame = demo_prices()
        actual = indicators(frame)
        def ema(values, span):
            output = [float(values[0])]
            for value in values[1:]:
                output.append(2 / (span + 1) * value + (1 - 2 / (span + 1)) * output[-1])
            return np.array(output)
        expected = ema(frame.Close.to_numpy(), 19) - ema(frame.Close.to_numpy(), 39)
        np.testing.assert_allclose(actual.MACD.iloc[38:], expected[38:])
        np.testing.assert_allclose(actual.Signal.iloc[46:], ema(expected[38:], 9)[8:])
        self.assertTrue(actual.Signal.iloc[:46].isna().all())

    def test_volume_baseline_excludes_current_day(self):
        frame = demo_prices()
        frame["Volume"] = 100
        frame.iloc[-1, frame.columns.get_loc("Volume")] = 1000
        result = indicators(frame)
        self.assertEqual(result.VolumeAvg20.iloc[-1], 100)
        self.assertEqual(result.VolumeRatio.iloc[-1], 10)

    def test_death_cross_is_risk(self):
        frame = indicators(demo_prices())
        frame.loc[frame.index[-2:], "MACD"] = [2, .5]
        frame.loc[frame.index[-2:], "Signal"] = [1, 1]
        result = assess(frame)
        self.assertEqual(result["level"], "위험")
        self.assertTrue(result["death_cross"])

    def test_zero_cross_is_risk(self):
        frame = indicators(demo_prices())
        frame.loc[frame.index[-2:], "MACD"] = [.1, -.1]
        self.assertTrue(assess(frame)["zero_cross"])
        self.assertEqual(assess(frame)["level"], "위험")

    def test_falling_alone_is_caution(self):
        frame = indicators(demo_prices())
        frame.loc[frame.index[-2:], "MACD"] = [3, 2]
        frame.loc[frame.index[-2:], "Signal"] = [1, 1]
        frame.loc[frame.index[-1], "VolumeRatio"] = 1
        result = assess(frame)
        self.assertTrue(result["falling"])
        self.assertEqual(result["level"], "주의")

    def test_price_drop_high_volume_escalates_falling_macd(self):
        frame = indicators(demo_prices())
        frame.loc[frame.index[-2:], "MACD"] = [3, 2]
        frame.loc[frame.index[-2:], "Signal"] = [1, 1]
        frame.loc[frame.index[-2:], "Close"] = [120, 110]
        frame.loc[frame.index[-1], "VolumeRatio"] = 1.5
        self.assertEqual(assess(frame)["level"], "위험")
        self.assertTrue(assess(frame)["distribution"])

    def test_rising_above_signal_has_no_bearish_warning(self):
        frame = indicators(demo_prices())
        frame.loc[frame.index[-2:], "MACD"] = [2, 3]
        frame.loc[frame.index[-2:], "Signal"] = [1, 1]
        frame.loc[frame.index[-1], "VolumeRatio"] = 1
        self.assertEqual(assess(frame)["level"], "뚜렷한 하향 경고 없음")

    def test_zero_average_volume_is_not_infinite(self):
        frame = demo_prices()
        frame["Volume"] = 0
        self.assertTrue(pd.isna(indicators(frame).VolumeRatio.iloc[-1]))

    def test_short_history_rejected(self):
        with self.assertRaises(ValueError):
            indicators(demo_prices().tail(40))

    def test_invalid_prices_and_duplicate_dates_rejected(self):
        frame = demo_prices()
        for column, value in [("Volume", -1), ("Close", 0), ("High", 1), ("Open", np.nan)]:
            invalid = frame.copy()
            invalid[column] = value
            with self.assertRaises(ValueError):
                validate_prices(invalid)
        with self.assertRaises(ValueError):
            validate_prices(pd.concat([frame, frame.tail(1)]))

    def test_intraday_excluded_and_after_close_included(self):
        frame = demo_prices().tail(2)
        frame.index = pd.to_datetime(["2026-10-22", "2026-10-23"])
        self.assertEqual(len(completed_daily_bars(frame, "한국", datetime(2026, 10, 23, 6, tzinfo=timezone.utc))), 1)
        self.assertEqual(len(completed_daily_bars(frame, "한국", datetime(2026, 10, 23, 7, tzinfo=timezone.utc))), 2)
        # US daylight saving: 20:30 UTC is 16:30 ET; wait until 17:00 ET.
        self.assertEqual(len(completed_daily_bars(frame, "미국", datetime(2026, 10, 23, 20, 30, tzinfo=timezone.utc))), 1)
        self.assertEqual(len(completed_daily_bars(frame, "미국", datetime(2026, 10, 23, 21, tzinfo=timezone.utc))), 2)

    def test_symbols_for_both_markets(self):
        self.assertEqual(symbols("005930", "한국"), (["005930.KS", "005930.KQ"], "KRX:005930"))
        self.assertEqual(symbols("brk.b", "미국", "NYSE"), (["BRK-B"], "NYSE:BRK.B"))
        for value, market in [("삼성전자", "한국"), ("<script>", "미국"), ("", "미국")]:
            with self.assertRaises(ValueError):
                symbols(value, market)

    def test_csv_round_trip(self):
        frame = demo_prices()
        result = read_csv(io.StringIO(frame.to_csv(index_label="Date")))
        self.assertEqual(len(result), len(frame))
        np.testing.assert_allclose(result.Close, frame.Close)
        with self.assertRaises(ValueError):
            read_csv(io.StringIO("Close,Volume\n100,1000"))

    def test_kosdaq_fallback_and_yahoo_multilevel_columns(self):
        frame = demo_prices()
        frame.columns = pd.MultiIndex.from_product([frame.columns, ["247540.KQ"]])
        with patch("yfinance.download", side_effect=[pd.DataFrame(), frame]) as download:
            result, provider, tv = fetch_prices("247540", "한국", "NASDAQ")
        self.assertEqual([call.args[0] for call in download.call_args_list], ["247540.KS", "247540.KQ"])
        self.assertEqual(provider, "247540.KQ")
        self.assertEqual(tv, "KRX:247540")
        self.assertEqual(len(result), 280)


if __name__ == "__main__":
    unittest.main()
