"""Shared daily directory cache: non-blocking refresh and last-good fallback."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import math
from pathlib import Path
from threading import Lock
import time
from zoneinfo import ZoneInfo

DAY = 86400
RETRY = 3600


def validate_timestamp(data):
    stamp = data.get('updated_at') if isinstance(data, dict) else None
    if (not isinstance(stamp, (float, int)) or not math.isfinite(stamp)
            or stamp <= 0 or stamp > time.time() + 300):
        raise ValueError('Invalid directory timestamp')


class ListingCache:
    def __init__(self, path, download, validate, label):
        self.path = Path(path)
        self.download = download
        self.validate = validate
        self.label = label
        self.lock = Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=self.path.stem)
        self.future = None
        self.last_attempt = 0
        self.snapshot = None
        self.failed = False
        self.disk_failed = False

    def refresh(self):
        try:
            data = self.validate(self.download())
        except Exception:
            with self.lock:
                self.failed = True
            return
        disk_failed = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            temporary.replace(self.path)
        except OSError:
            # A read-only/full disk must not discard a valid downloaded directory.
            disk_failed = True
        with self.lock:
            self.snapshot = data
            self.failed = False
            self.disk_failed = disk_failed

    def get(self):
        now = time.time()
        with self.lock:
            if self.snapshot is None:
                try:
                    self.snapshot = self.validate(json.loads(self.path.read_text(encoding='utf-8')))
                except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
                    self.snapshot = {'updated_at': 0, 'rows': []}
            stamp = self.snapshot['updated_at']
            stale = now - stamp >= DAY
            running = self.future is not None and not self.future.done()
            if stale and not running and now - self.last_attempt >= RETRY:
                self.last_attempt = now
                self.future = self.executor.submit(self.refresh)
                running = True
            rows = list(self.snapshot['rows'])
            if stamp:
                date = datetime.fromtimestamp(stamp, ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M')
                message = f'{self.label} {len(rows):,}개 · 갱신 {date} (한국 시간)'
                if stale:
                    message += ' · 이전 목록 사용 중'
            else:
                message = f'{self.label} 준비 중 · 현재 기본 종목만 표시합니다.'
            if running:
                message += ' · 백그라운드 갱신 중 · 완료 후 자동 반영됩니다.'
            elif self.failed:
                message += ' · 갱신 연결 실패, 1시간 후 다음 이용 시 재시도'
            if self.disk_failed:
                message += ' · 임시 메모리 사용 중 (캐시 파일 저장 실패)'
            return rows, message
