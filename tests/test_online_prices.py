import unittest
from market_data import demo_prices, prepare_online_prices
from analysis import validate_prices

class OnlinePriceTests(unittest.TestCase):
    def test_float_noise_corrected(self):
        frame=demo_prices().tail(3)
        frame.iloc[0,frame.columns.get_loc('High')]=frame.Open.iloc[0]-1e-7
        result=prepare_online_prices(frame)
        self.assertEqual(len(result),3)
        self.assertEqual(result.High.iloc[0],result.Open.iloc[0])
        self.assertEqual(result.attrs['rounded_price_rows'],1)
    def test_bad_row_excluded_with_date_and_close_preserved(self):
        frame=demo_prices().tail(3)
        frame.iloc[0,frame.columns.get_loc('High')]=1
        result=prepare_online_prices(frame)
        self.assertEqual(len(result),2)
        self.assertEqual(result.attrs['excluded_price_dates'],[str(frame.index[0])[:10]])
        self.assertTrue(result.Close.equals(frame.Close.iloc[1:]))
        with self.assertRaises(ValueError): validate_prices(frame)
    def test_all_invalid_rejected(self):
        frame=demo_prices().tail(3)
        frame['High']=1
        with self.assertRaisesRegex(ValueError,'유효한'): prepare_online_prices(frame)

    def test_kosdaq_fallback_after_kospi_error(self):
        from unittest.mock import patch
        from market_data import fetch_prices
        with patch('yfinance.download', side_effect=[OSError('first candidate failed'), demo_prices()]) as download:
            frame, provider, _ = fetch_prices('290650', '한국', 'NASDAQ')
        self.assertFalse(frame.empty)
        self.assertEqual(provider, '290650.KQ')
        self.assertEqual([call.args[0] for call in download.call_args_list], ['290650.KS', '290650.KQ'])
