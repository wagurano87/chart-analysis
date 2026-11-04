import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import us_listings as us


class USDirectoryTests(unittest.TestCase):
    def test_parse_filters_test_issues_and_footer(self):
        data = b'Symbol|Security Name|Test Issue|ETF\nAAPL|Apple Inc.|N|N\nTEST|Test|Y|N\nQQQ|Fund|N|Y\nFile Creation Time: 11042026|||\n'
        rows = us.parse_listing(data, True)
        self.assertEqual([r['code'] for r in rows], ['AAPL', 'QQQ'])
        self.assertEqual(rows[1]['kind'], 'ETF')
        with self.assertRaises(ValueError):
            us.parse_listing(data.split(b'File Creation')[0], True)
        with self.assertRaises(ValueError):
            us.parse_listing(b'<html>error</html>', True)

    def test_other_exchange_class_symbols(self):
        data = b'NASDAQ Symbol|Security Name|Test Issue|ETF|Exchange\nBRK.B|Berkshire|N|N|N\nABC$A|Preferred|N|N|N\nSPY|Fund|N|Y|P\nFile Creation Time: 11042026||||\n'
        rows = us.parse_listing(data, False)
        self.assertEqual([r['code'] for r in rows], ['BRK-B', 'SPY'])
        self.assertEqual(rows[1]['exchange'], 'NYSE Arca')

    def test_failed_download_retains_cache(self):
        previous = {'updated_at': 12345, 'rows': []}
        with TemporaryDirectory() as folder, patch.object(us, 'CACHE', Path(folder)/'cache.json'), patch.object(us, '_snapshot', previous), patch.object(us, '_failed', False), patch.object(us, 'download_snapshot', side_effect=OSError('offline')):
            us.CACHE.write_text('previous')
            us.refresh()
            self.assertEqual(us.CACHE.read_text(), 'previous')
            self.assertEqual(us._snapshot, previous)
            self.assertTrue(us._failed)

    def test_validation_rejects_partial_directory(self):
        with self.assertRaises(ValueError):
            us.validate_snapshot({'updated_at': 1000, 'rows': []})

    def test_daily_and_retry_schedule(self):
        with patch.object(us, '_snapshot', {'updated_at': 100000, 'rows': []}), patch.object(us, '_future', None), patch.object(us, '_last_attempt', 0), patch.object(us, '_executor') as executor:
            with patch.object(us.time, 'time', return_value=100001):
                us.get_directory()
                executor.submit.assert_not_called()
            with patch.object(us.time, 'time', return_value=200000):
                us.get_directory()
                executor.submit.assert_called_once()
            executor.submit.return_value.done.return_value = True
            with patch.object(us.time, 'time', return_value=200100):
                us.get_directory()
                executor.submit.assert_called_once()
            with patch.object(us.time, 'time', return_value=204000):
                us.get_directory()
                self.assertEqual(executor.submit.call_count, 2)
