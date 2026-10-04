import math
from datetime import date, datetime, time, timedelta

from astral import Observer
from astral.sun import sunrise, sunset
from tzlocal import get_localzone


class NightSchedule:
    def __init__(self, settings, timezone=None):
        latitude = settings.get("latitude")
        longitude = settings.get("longitude")
        if (
            not isinstance(latitude, (int, float))
            or isinstance(latitude, bool)
            or not math.isfinite(latitude)
            or not -90 <= latitude <= 90
        ):
            raise ValueError("night_schedule.latitude must be between -90 and 90")
        if (
            not isinstance(longitude, (int, float))
            or isinstance(longitude, bool)
            or not math.isfinite(longitude)
            or not -180 <= longitude <= 180
        ):
            raise ValueError("night_schedule.longitude must be between -180 and 180")

        self.observer = Observer(latitude=float(latitude), longitude=float(longitude))
        self.timezone = timezone or get_localzone()
        self.sunrise_offset = timedelta(
            minutes=self._read_offset(settings.get("sunrise_offset_minutes", 0), "sunrise")
        )
        self.sunset_offset = timedelta(
            minutes=self._read_offset(settings.get("sunset_offset_minutes", 0), "sunset")
        )
        self.retry_interval = timedelta(minutes=30)

    @staticmethod
    def _read_offset(value, label):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError(f"night_schedule.{label}_offset_minutes must be finite")
        return float(value)

    def _night_window(self, start_date):
        start = sunset(
            self.observer,
            date=start_date,
            tzinfo=self.timezone,
        ) + self.sunset_offset
        end = sunrise(
            self.observer,
            date=start_date + timedelta(days=1),
            tzinfo=self.timezone,
        ) + self.sunrise_offset
        if end <= start:
            return None
        return start, end

    def window_at(self, now=None):
        now = now or datetime.now(self.timezone)
        if now.tzinfo is None:
            now = now.replace(tzinfo=self.timezone)
        else:
            now = now.astimezone(self.timezone)

        active_windows = []
        upcoming_starts = []
        for day_offset in range(-2, 4):
            start_date = now.date() + timedelta(days=day_offset)
            try:
                window = self._night_window(start_date)
            except (ValueError, OverflowError):
                continue
            if window is None:
                continue
            start, end = window
            if start <= now < end:
                active_windows.append(window)
            elif start > now:
                upcoming_starts.append(start)

        if active_windows:
            return max(active_windows, key=lambda window: window[0]), None
        if upcoming_starts:
            return None, min(upcoming_starts)
        return None, now + self.retry_interval