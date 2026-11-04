import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from listing_cache import ListingCache, validate_timestamp


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data = {'updated_at': 100000, 'rows': [{'name': 'example'}]}
        self.cache = ListingCache(Path(self.folder.name)/'cache.json', Mock(return_value=self.data),
                                  lambda data: (validate_timestamp(data) or data), 'Test')
        self.addCleanup(self.cache.executor.shutdown)

    def test_refresh_and_failure_keep_last_success(self):
        self.cache.refresh()
        self.assertEqual(json.loads(self.cache.path.read_text()), self.data)
        self.cache.download.side_effect = OSError('offline')
        self.cache.refresh()
        self.assertEqual(self.cache.snapshot, self.data)
        self.assertEqual(json.loads(self.cache.path.read_text()), self.data)
        self.assertTrue(self.cache.failed)

    def test_disk_failure_still_uses_download(self):
        with patch.object(Path, 'mkdir', side_effect=OSError('read only')):
            self.cache.refresh()
        self.assertEqual(self.cache.snapshot, self.data)
        self.assertTrue(self.cache.disk_failed)
        self.assertFalse(self.cache.failed)

    def test_corrupt_disk_recovers_and_schedule_throttles(self):
        self.cache.path.write_text('{broken')
        with patch.object(self.cache, 'executor') as executor:
            executor.submit.return_value.done.return_value = False
            with patch('listing_cache.time.time', return_value=200000):
                rows, _ = self.cache.get()
                self.assertEqual(rows, [])
                self.cache.get()
                executor.submit.assert_called_once()
            executor.submit.return_value.done.return_value = True
            with patch('listing_cache.time.time', return_value=200100):
                self.cache.get()
                executor.submit.assert_called_once()
            with patch('listing_cache.time.time', return_value=204000):
                self.cache.get()
                self.assertEqual(executor.submit.call_count, 2)

    def test_fresh_disk_not_downloaded_and_next_day_refreshes(self):
        self.cache.path.write_text(json.dumps(self.data))
        with patch.object(self.cache, 'executor') as executor:
            with patch('listing_cache.time.time', return_value=100001):
                rows, _ = self.cache.get()
                self.assertEqual(rows, self.data['rows'])
                executor.submit.assert_not_called()
            with patch('listing_cache.time.time', return_value=200000):
                self.cache.get()
                executor.submit.assert_called_once()

    def test_invalid_timestamp_rejected(self):
        for stamp in [float('nan'), float('inf'), -1, 10**20, 'today']:
            with self.assertRaises(ValueError):
                validate_timestamp({'updated_at': stamp})
