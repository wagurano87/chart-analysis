"""Symbol validation and Yahoo Finance daily-data adapter."""
import re

import numpy as np
import pandas as pd

from analysis import validate_prices


# 사용자가 넣은 코드를 검증하고 Yahoo가 사용하는 형식으로 바꿉니다. 한국은 코스피(.KS)와 코스닥(.KQ) 후보를 만듭니다.
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


# 주식은 Yahoo, 코인은 거래소 어댑터에 맡깁니다. 한국의 첫 거래소 후보가 실패하면 다음 후보도 확인합니다.
def fetch_prices(value, market, exchange):
    from crypto_data import CRYPTO_MARKETS, fetch_crypto
    if market in CRYPTO_MARKETS:
        return fetch_crypto(value, market)
    import yfinance as yf

    candidates, tv_symbol = symbols(value, market, exchange)
    connection_error = None
    for symbol in candidates:
        try:
            frame = yf.download(symbol, period="5y", interval="1d", auto_adjust=True,
                                progress=False, threads=False, timeout=15)
        except Exception as error:
            connection_error = error
            continue
        if frame.empty:
            continue
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        return prepare_online_prices(frame), symbol, tv_symbol
    if connection_error is not None:
        raise RuntimeError("시세 제공처에 연결할 수 없습니다. 네트워크 상태를 확인하거나 CSV를 사용하세요.") from connection_error
    raise ValueError("일봉을 받지 못했습니다. 종목코드, 제공처 장애 또는 네트워크 제한을 확인하세요. CSV 입력도 지원합니다.")


# 온라인 시세의 아주 작은 반올림 오차만 보정하고, 그 외 모순된 봉은 제외 사실을 기록합니다. 임의 가격을 만들어 채우지 않습니다.
def prepare_online_prices(frame):
    """Tolerate float rounding only; exclude inconsistent online candles explicitly."""
    frame = frame.copy()
    required = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not set(required).issubset(frame.columns):
        return validate_prices(frame)
    frame[required] = frame[required].apply(pd.to_numeric, errors='coerce')
    prices = frame[['Open', 'High', 'Low', 'Close']]
    upper = prices.max(axis=1)
    lower = prices.min(axis=1)
    # One millionth of price (0.0001%): numerical noise, not a market tick.
    tolerance = prices.abs().max(axis=1) * 1e-6
    invalid = (~np.isfinite(frame[required]).all(axis=1) |
               (prices <= 0).any(axis=1) | (frame.Volume < 0) |
               ((upper-frame.High) > tolerance) | ((frame.Low-lower) > tolerance))
    excluded = [str(date)[:10] for date in frame.index[invalid]]
    frame = frame.loc[~invalid].copy()
    if frame.empty:
        raise ValueError('제공처에서 받은 시세에 유효한 가격 데이터가 없습니다. 잠시 후 다시 조회하세요.')
    rounded = ((frame.High < upper.loc[frame.index]) | (frame.Low > lower.loc[frame.index])).sum()
    frame['High'] = upper.loc[frame.index]
    frame['Low'] = lower.loc[frame.index]
    frame = validate_prices(frame)
    frame.attrs['excluded_price_dates'] = excluded
    frame.attrs['rounded_price_rows'] = int(rounded)
    return frame


# 업로드한 CSV의 Date 열을 날짜 인덱스로 바꾸고 가격 검사를 거칩니다. CSV는 프로그램 코드로 실행되지 않습니다.
def read_csv(file):
    frame = pd.read_csv(file)
    if "Date" not in frame.columns:
        raise ValueError("CSV에 Date 열이 필요합니다.")
    return validate_prices(frame.set_index("Date"))


# 네트워크 없이 화면을 시험할 가상 데이터를 만듭니다. 실제 주가와 혼동하면 안 됩니다.
def demo_prices():
    """Clearly synthetic sample with a late downturn; never a real stock quote."""
    rng = np.random.default_rng(42)
    close = np.r_[np.linspace(80, 160, 1260), np.linspace(160, 120, 40)]
    close = close + rng.normal(0, .3, len(close))
    opening = close * 1.002
    volume = rng.integers(80000, 120000, len(close))
    volume[-1] = 250000
    return pd.DataFrame({"Open": opening, "High": opening * 1.01,
                         "Low": close * .99, "Close": close, "Volume": volume},
                        index=pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=len(close)))


# 주식의 정규장 1시간봉을 장 시작 기준으로 묶습니다. 마지막 묶음은 4시간보다 짧을 수 있습니다.
def stock_four_hour(symbol, market, now=None):
    """Session-aligned 4h bars, with the shorter closing session bar retained."""
    import yfinance as yf
    zone='Asia/Seoul' if market=='한국' else 'America/New_York'
    try:
        raw=yf.download(symbol,period='1y',interval='1h',auto_adjust=True,progress=False,threads=False,timeout=15)
    except Exception as error:
        raise RuntimeError('주식 시간봉 조회에 실패했습니다. 제공처 연결을 확인하세요.') from error
    if raw.empty: raise ValueError('이 종목의 시간봉을 제공처에서 받지 못했습니다.')
    if isinstance(raw.columns,pd.MultiIndex): raw.columns=raw.columns.get_level_values(0)
    if raw.index.tz is None: raw.index=raw.index.tz_localize(zone)
    else: raw.index=raw.index.tz_convert(zone)
    raw=raw.between_time('09:00' if market=='한국' else '09:30','15:30' if market=='한국' else '16:00',inclusive='left')
    current=pd.Timestamp.now(tz=zone) if now is None else pd.Timestamp(now).tz_convert(zone)
    # Conservative: don't use today's data until the regular-session safety cutoff.
    cutoff=16 if market=='한국' else 17
    if current.hour<cutoff: raw=raw.loc[raw.index.normalize()<current.normalize()]
    raw=raw.loc[raw.index<=current]
    groups=[day.resample('4h',origin='start_day',offset='9h' if market=='한국' else '9h30min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna() for _,day in raw.groupby(raw.index.date)]
    if not groups: raise ValueError('완료된 정규장 시간봉이 부족합니다.')
    frame=pd.concat(groups)
    return validate_prices(frame,normalize_dates=False)
