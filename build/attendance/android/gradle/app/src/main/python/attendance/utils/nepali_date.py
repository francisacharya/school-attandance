import nepali_datetime
from datetime import date

NEPALI_MONTHS = [
    "Baisakh", "Jestha", "Ashad", "Shrawan", "Bhadra", "Ashwin",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
]

def ad_to_bs(ad_str):
    """Converts AD string YYYY-MM-DD to BS string YYYY-MM-DD."""
    if not ad_str:
        return ""
    try:
        y, m, d = map(int, ad_str.split('-'))
        ad_date = date(y, m, d)
        bs_date = nepali_datetime.date.from_datetime_date(ad_date)
        return bs_date.strftime('%Y-%m-%d')
    except Exception:
        return ad_str

def bs_to_ad(bs_str):
    """Converts BS string YYYY-MM-DD to AD string YYYY-MM-DD."""
    if not bs_str:
        return ""
    try:
        y, m, d = map(int, bs_str.split('-'))
        bs_date = nepali_datetime.date(y, m, d)
        ad_date = bs_date.to_datetime_date()
        return ad_date.strftime('%Y-%m-%d')
    except Exception:
        return bs_str

def get_today_bs():
    """Returns today's date in BS as string YYYY-MM-DD."""
    return nepali_datetime.date.today().strftime('%Y-%m-%d')

def get_month_name(index):
    """1-indexed month name."""
    if 1 <= index <= 12:
        return NEPALI_MONTHS[index - 1]
    return ""
