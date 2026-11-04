import unittest
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

    def test_validation_rejects_partial_directory(self):
        with self.assertRaises(ValueError):
            us.validate_snapshot({'updated_at': 1000, 'rows': []})
