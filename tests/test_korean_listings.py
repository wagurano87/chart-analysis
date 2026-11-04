import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import korean_listings as kl


def snapshot():
    rows = []
    for market, base, count in [('코스피', 100000, 500), ('코스닥', 200000, 500), ('코넥스', 300000, 20)]:
        rows.extend({'name': f'회사{i}', 'code': str(base+i), 'exchange': market} for i in range(count))
    return {'updated_at': 100000, 'rows': rows}


class DirectoryTests(unittest.TestCase):
    def test_parse_encoding_and_leading_zero(self):
        html = '<table><tr><th>회사명</th><th>종목코드</th></tr><tr><td>LG전자</td><td>066570</td></tr></table>'
        for encoding in ['utf-8', 'cp949']:
            self.assertEqual(kl.parse_listing(html.encode(encoding), '코스피'),
                             [{'name': 'LG전자', 'code': '066570', 'exchange': '코스피'}])
        with self.assertRaises(ValueError):
            kl.parse_listing(b'<html>blocked</html>', '코스피')

    def test_partial_directory_rejected(self):
        data = snapshot()
        kl.validate_snapshot(data)
        data['rows'] = data['rows'][:500]
        with self.assertRaises(ValueError):
            kl.validate_snapshot(data)

    def test_refresh_and_failure_preserve_disk_and_memory(self):
        with TemporaryDirectory() as directory, patch.object(kl, 'CACHE', Path(directory)/'list.json'), patch.object(kl, '_snapshot', None), patch.object(kl, '_failed', False):
            data = snapshot()
            with patch.object(kl, 'download_snapshot', return_value=data):
                kl.refresh()
            self.assertEqual(json.loads(kl.CACHE.read_text()), data)
            with patch.object(kl, 'download_snapshot', side_effect=OSError('offline')):
                kl.refresh()
            self.assertEqual(kl._snapshot, data)
            self.assertEqual(json.loads(kl.CACHE.read_text()), data)
            self.assertTrue(kl._failed)

    def test_daily_refresh_and_retry_throttle(self):
        with patch.object(kl, '_snapshot', snapshot()), patch.object(kl, '_future', None), patch.object(kl, '_last_attempt', 0), patch.object(kl, '_executor') as executor:
            with patch.object(kl.time, 'time', return_value=100001):
                kl.get_directory()
                executor.submit.assert_not_called()
            with patch.object(kl.time, 'time', return_value=200000):
                kl.get_directory()
                executor.submit.assert_called_once()
            executor.submit.return_value.done.return_value = True
            with patch.object(kl.time, 'time', return_value=200100):
                kl.get_directory()
                executor.submit.assert_called_once()
            with patch.object(kl.time, 'time', return_value=204000):
                kl.get_directory()
                self.assertEqual(executor.submit.call_count, 2)
