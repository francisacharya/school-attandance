import nepali_datetime
from datetime import date

def ad_to_bs(ad_date_obj_or_str):
    """Converts Gregorian (AD) to Nepali (BS) string YYYY-MM-DD."""
    if not ad_date_obj_or_str:
        return ""
    try:
        if isinstance(ad_date_obj_or_str, str):
            # Expecting YYYY-MM-DD
            y, m, d = map(int, ad_date_obj_or_str.split('-'))
            ad_date = date(y, m, d)
        else:
            ad_date = ad_date_obj_or_str
            
        bs_date = nepali_datetime.date.from_datetime_date(ad_date)
        return bs_date.strftime('%Y-%m-%d')
    except Exception:
        return str(ad_date_obj_or_str)

def bs_to_ad(bs_str):
    """Converts Nepali (BS) string YYYY-MM-DD to Gregorian (AD) string YYYY-MM-DD."""
    if not bs_str:
        return ""
    try:
        y, m, d = map(int, bs_str.split('-'))
        bs_date = nepali_datetime.date(y, m, d)
        ad_date = bs_date.to_datetime_date()
        return ad_date.strftime('%Y-%m-%d')
    except Exception:
        return bs_str

def get_nepali_month_name(month_index):
    """1-indexed month name."""
    names = [
        "Baisakh", "Jestha", "Ashad", "Shrawan", "Bhadra", "Ashwin",
        "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
    ]
    if 1 <= month_index <= 12:
        return names[month_index - 1]
    return ""
