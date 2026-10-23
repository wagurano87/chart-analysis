"""Symbol validation and Yahoo Finance daily-data adapter."""
import re

import numpy as np
import pandas as pd

from analysis import validate_prices


def symbols(value, market, exchange="NASDAQ"):
    value = value.strip().upper()
    if market == "한국":
        if not re.fullmatch(r"\d{6}", value):
            raise ValueError("한국 종목은 6자리 코드로 입력하세요. 예: 005930, 247540")
        return [value + ".KS", value + ".KQ"], "KRX:" + value
    if exchange not in {"NASDAQ", "NYSE", "AMEX"}:
        raise ValueError("지원하지 않는 미국 거래소입니다.")
    if not re.fullmatch(r"[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,3})?", value):
        raise ValueError("미국 종목 티커를 입력하세요. 예: AAPL, NVDA, BRK.B")
    return [value.replace(".", "-")], exchange + ":" + value.replace("-", ".")


def fetch_prices(value, market, exchange):
    import yfinance as yf

    candidates, tv_symbol = symbols(value, market, exchange)
    for symbol in candidates:
        try:
            frame = yf.download(symbol, period="2y", interval="1d", auto_adjust=True,
                                progress=False, threads=False, timeout=15)
        except Exception as error:
            raise RuntimeError("시세 제공처에 연결할 수 없습니다. 네트워크 상태를 확인하거나 CSV를 사용하세요.") from error
        if frame.empty:
            continue
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        return validate_prices(frame), symbol, tv_symbol
    raise ValueError("일봉을 받지 못했습니다. 종목코드, 제공처 장애 또는 네트워크 제한을 확인하세요. CSV 입력도 지원합니다.")


def read_csv(file):
    frame = pd.read_csv(file)
    if "Date" not in frame.columns:
        raise ValueError("CSV에 Date 열이 필요합니다.")
    return validate_prices(frame.set_index("Date"))


def demo_prices():
    """Clearly synthetic sample with a late downturn; never a real stock quote."""
    rng = np.random.default_rng(42)
    close = np.r_[np.linspace(80, 160, 240), np.linspace(160, 120, 40)]
    close = close + rng.normal(0, .3, len(close))
    opening = close * 1.002
    volume = rng.integers(80000, 120000, len(close))
    volume[-1] = 250000
    return pd.DataFrame({"Open": opening, "High": opening * 1.01,
                         "Low": close * .99, "Close": close, "Volume": volume},
                        index=pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=len(close)))
