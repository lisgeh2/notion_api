from datetime import date, datetime, time, timedelta

WINDOW_START = time(8, 0)
WINDOW_END = time(13, 0)
SLOT_MINUTES = 5
MAX_SCORE = 60


EVENING_WINDOW_START = time(22, 0)
EVENING_WINDOW_END = time(1, 0)      # next day
EVENING_SLOT_MINUTES = 5
EVENING_MAX_SCORE = 36               # 180 min / 5