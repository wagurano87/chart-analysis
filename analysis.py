"""Daily price indicators. No network or UI dependencies."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


def validate_prices(frame):
    frame = frame.copy()
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not set(required).issubset(frame.columns):
        raise ValueError("Date, Open, High, Low, Close, Volume 열이 필요합니다.")
    dates = pd.to_datetime(frame.index, errors="coerce")
    if dates.isna().any():
        raise ValueError("해석할 수 없는 날짜가 있습니다.")
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    frame.index = dates.normalize()
    if frame.index.duplicated().any():
        raise ValueError("같은 날짜의 행이 중복되어 있습니다. 일봉 데이터만 입력하세요.")
    frame = frame[required].apply(pd.to_numeric, errors="coerce").sort_index()
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("가격·거래량에 빈 값 또는 숫자가 아닌 값이 있습니다.")
    if (frame[["Open", "High", "Low", "Close"]] <= 0).any().any() or (frame.Volume < 0).any():
        raise ValueError("가격은 양수, 거래량은 0 이상이어야 합니다.")
    if ((frame.High < frame[["Open", "Close", "Low"]].max(axis=1)) |
            (frame.Low > frame[["Open", "Close", "High"]].min(axis=1))).any():
        raise ValueError("고가·저가와 시가·종가의 관계가 올바르지 않습니다.")
    return frame


def completed_daily_bars(frame, market, now=None):
    """Conservatively omit today's daily bar until after regular-session close."""
    zone = ZoneInfo("Asia/Seoul" if market == "한국" else "America/New_York")
    local_now = (now or datetime.now(zone)).astimezone(zone)
    # Allow for provider publishing lag. US half-day bars wait until this cutoff too.
    cutoff = time(16, 0) if market == "한국" else time(17, 0)
    days = frame.index.date
    allowed = days <= local_now.date() if local_now.time() >= cutoff else days < local_now.date()
    return frame.loc[allowed].copy()


def indicators(frame):
    if len(frame) < 120:
        raise ValueError("안정적인 지표 계산을 위해 선택한 주기의 완료된 봉이 최소 120개 필요합니다. 주봉은 약 3년 이상의 일봉을 입력하세요.")
    result = frame.copy()
    close = result.Close
    result["MACD"] = (close.ewm(span=19, adjust=False, min_periods=19).mean()
                      - close.ewm(span=39, adjust=False, min_periods=39).mean())
    result["Signal"] = result.MACD.ewm(span=9, adjust=False, min_periods=9).mean()
    result["Histogram"] = result.MACD - result.Signal
    result["MACD6"] = (close.ewm(span=6, adjust=False, min_periods=6).mean()
                       - close.ewm(span=19, adjust=False, min_periods=19).mean())
    result["Signal6"] = result.MACD6.ewm(span=9, adjust=False, min_periods=9).mean()
    result["Histogram6"] = result.MACD6 - result.Signal6
    result["RSI"] = rsi(close)
    result["OBV"] = (np.sign(close.diff()).fillna(0) * result.Volume).cumsum()
    for window in (20, 60, 200):
        result[f"MA{window}"] = close.rolling(window).mean()
    # Compare against prior sessions: today's volume must not inflate its own baseline.
    result["VolumeAvg20"] = result.Volume.shift(1).rolling(20).mean()
    result["VolumeRatio"] = result.Volume / result.VolumeAvg20.replace(0, np.nan)
    return result


def rsi(close, period=14):
    """Wilder smoothing seeded with the first period's simple average."""
    changes = close.diff()
    gains, losses = changes.clip(lower=0), -changes.clip(upper=0)
    output = pd.Series(np.nan, index=close.index)
    if len(close) <= period:
        return output
    gain, loss = gains.iloc[1:period + 1].mean(), losses.iloc[1:period + 1].mean()
    for index in range(period, len(close)):
        if index > period:
            gain = (gain * (period - 1) + gains.iloc[index]) / period
            loss = (loss * (period - 1) + losses.iloc[index]) / period
        output.iloc[index] = (50 if gain == loss == 0 else 100 if loss == 0
                             else 100 - 100 / (1 + gain / loss))
    return output


def resample_bars(daily, market, timeframe, now=None):
    if timeframe == "일봉":
        return daily.copy()
    if timeframe != "주봉":
        raise ValueError("지원하지 않는 주기입니다.")
    if daily.empty:
        return daily.copy()
    zone = ZoneInfo("Asia/Seoul" if market == "한국" else "America/New_York")
    local = (now or datetime.now(zone)).astimezone(zone)
    cutoff = time(16) if market == "한국" else time(17)
    weekly = daily.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min",
                                          "Close": "last", "Volume": "sum"}).dropna()
    # Friday label represents the week, not necessarily the last actual trade date.
    # Holiday weeks are conservatively held until the normal Friday cutoff.
    available = weekly.index.date < local.date()
    if local.time() >= cutoff:
        available = weekly.index.date <= local.date()
    # Don't include the first potentially partial week of a clipped history window.
    first_monday = daily.index.min().to_period("W-SUN").start_time
    if daily.index.min() > first_monday:
        weekly = weekly.loc[weekly.index >= first_monday + pd.Timedelta(days=7)]
        available = weekly.index.date < local.date() if local.time() < cutoff else weekly.index.date <= local.date()
    return weekly.loc[available]


def assess(frame):
    last, prev = frame.iloc[-1], frame.iloc[-2]
    falling = bool(last.MACD < prev.MACD)
    death_cross = bool(prev.MACD >= prev.Signal and last.MACD < last.Signal)
    zero_cross = bool(prev.MACD >= 0 and last.MACD < 0)
    below_signal = bool(last.MACD < last.Signal)
    falling_three = bool((frame.MACD.diff().iloc[-3:] < 0).all())
    hist_weakening = bool(last.Histogram < prev.Histogram)
    price_down = bool(last.Close < prev.Close)
    heavy = bool(pd.notna(last.VolumeRatio) and last.VolumeRatio >= 1.5)
    distribution = price_down and heavy
    # Deterministic rules, not a prediction or a statistically fitted sell probability.
    if death_cross or zero_cross or (falling and distribution):
        level = "위험"
    elif falling or below_signal or distribution:
        level = "주의"
    else:
        level = "뚜렷한 하향 경고 없음"
    reasons = []
    if falling:
        reasons.append("MACD(19,39,9)선이 직전 봉보다 하락했습니다.")
    if falling_three:
        reasons.append("MACD(19,39,9)선이 3개 봉 연속 하락했습니다.")
    if death_cross:
        reasons.append("MACD선이 시그널선을 아래로 돌파했습니다(데드크로스).")
    elif below_signal:
        reasons.append("MACD선이 시그널선 아래에 머물고 있습니다.")
    if zero_cross:
        reasons.append("MACD선이 0선을 아래로 돌파했습니다.")
    if distribution:
        reasons.append("종가 하락과 평소 대비 1.5배 이상의 거래량이 함께 나타났습니다.")
    if hist_weakening:
        reasons.append("MACD 히스토그램이 감소했습니다. 이것만으로 매도 신호로 판정하지 않습니다.")
    if not reasons:
        reasons.append("설정된 하향 경고 조건이 현재 발생하지 않았습니다. 매수 신호를 뜻하지 않습니다.")
    return {"level": level, "reasons": reasons, "falling": falling,
            "death_cross": death_cross, "zero_cross": zero_cross,
            "distribution": distribution, "below_signal": below_signal}
