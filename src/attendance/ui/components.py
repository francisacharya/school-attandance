import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

# --- Material Design 3 (M3) Tokens ---
M3_PRIMARY = "#6750A4"
M3_ON_PRIMARY = "#FFFFFF"
M3_PRIMARY_CONTAINER = "#EADDFF"
M3_ON_PRIMARY_CONTAINER = "#21005D"
M3_SURFACE = "#FFFBFE"
M3_SURFACE_2 = "#F3EDF7"  # Elevated surface
M3_SURFACE_VARIANT = "#E7E0EC"
M3_ON_SURFACE = "#1C1B1F"
M3_ON_SURFACE_VARIANT = "#49454F"
M3_OUTLINE = "#79747E"
M3_SECONDARY_CONTAINER = "#E8DEF8"
M3_ON_SECONDARY_CONTAINER = "#1D192B"
M3_ERROR = "#B3261E"

# --- M3 Styled Components ---

def m3_card(style=None, margin=12):
    """M3 Elevated Card (Surface 2 with rounded corners simulation)."""
    # Note: Toga doesn't have native corner_radius yet on all platforms, 
    # but we use consistent margin and colored boxes to simulate M3.
    s = Pack(direction=COLUMN, background_color=M3_SURFACE_2, margin=margin)
    if style: s.update(**style)
    return toga.Box(style=s)

def m3_button(label, on_press=None, variant="filled", style=None):
    """M3 Buttons (Filled, Outlined, Text)."""
    s = Pack(margin=4)
    if variant == "filled":
        s.update(background_color=M3_PRIMARY, color=M3_ON_PRIMARY, font_weight="bold")
    elif variant == "tonal":
        s.update(background_color=M3_SECONDARY_CONTAINER, color=M3_ON_SECONDARY_CONTAINER)
    elif variant == "outlined":
        # Toga buttons don't support borders well, so we use surface variant as bg
        s.update(background_color=M3_SURFACE, color=M3_PRIMARY)
    else: # Text button
        s.update(color=M3_PRIMARY)
        
    if style: s.update(**style)
    return toga.Button(label, on_press=on_press, style=s)

def title_label(text, style=None):
    """M3 Headline Small / Title Large."""
    s = Pack(font_size=22, font_weight="bold", color=M3_ON_SURFACE, margin_bottom=16)
    if style: s.update(**style)
    return toga.Label(text, style=s)

def body_label(text, style=None):
    """M3 Body Medium."""
    s = Pack(font_size=14, color=M3_ON_SURFACE_VARIANT)
    if style: s.update(**style)
    return toga.Label(text, style=s)

def stat_card(label, value, color=M3_PRIMARY):
    """M3 Styled Statistics Card."""
    b = m3_card(style=Pack(margin=6, flex=1))
    b.add(toga.Label(str(value), style=Pack(font_size=24, font_weight="bold", color=color, margin_bottom=2)))
    b.add(toga.Label(label.upper(), style=Pack(font_size=10, font_weight="bold", color=M3_ON_SURFACE_VARIANT)))
    return b

def back_button(app):
    """M3 Text Button for navigation."""
    return toga.Button("← BACK", on_press=lambda w: app.show_dashboard(),
                       style=Pack(margin_bottom=12, color=M3_PRIMARY, font_weight="bold"))

def status_label():
    """M3 Label Small."""
    return toga.Label("", style=Pack(margin=4, font_size=11, color=M3_ON_SURFACE_VARIANT))

def scrollable(inner):
    """Themed scroll container."""
    sc = toga.ScrollContainer(horizontal=False, style=Pack(flex=1, background_color=M3_SURFACE))
    sc.content = inner
    return sc

class NepaliDatePicker:
    """M3-aligned Date Picker with tonal selections."""
    def __init__(self, label_text, initial_date=None, flex=1):
        import nepali_datetime
        from attendance.utils.nepali_date import get_today_bs
        
        self.box = toga.Box(style=Pack(direction=COLUMN, margin=6, flex=flex))
        self.box.add(toga.Label(label_text, style=Pack(font_size=12, font_weight="bold", color=M3_PRIMARY, margin_bottom=4)))
        
        controls = toga.Box(style=Pack(direction=ROW, align_items="center"))
        
        self.year_sel = toga.Selection(items=[str(y) for y in range(2070, 2096)], 
                                      style=Pack(width=75, margin_right=4, background_color=M3_SURFACE_VARIANT))
        self.month_sel = toga.Selection(items=[f"{m:02d}" for m in range(1, 13)], 
                                       style=Pack(width=55, margin_right=4, background_color=M3_SURFACE_VARIANT))
        self.day_sel = toga.Selection(style=Pack(width=55, margin_right=4, background_color=M3_SURFACE_VARIANT))
        
        def update_days(widget=None):
            y = int(self.year_sel.value)
            m = int(self.month_sel.value)
            days = 30
            for d in range(32, 28, -1):
                try:
                    nepali_datetime.date(y, m, d)
                    days = d
                    break
                except ValueError: continue
            cur_day = str(self.day_sel.value) if self.day_sel.value else "01"
            new_days = [f"{d:02d}" for d in range(1, days + 1)]
            self.day_sel.items = new_days
            if cur_day in new_days: self.day_sel.value = cur_day
            else: self.day_sel.value = new_days[-1]

        self.year_sel.on_change = update_days
        self.month_sel.on_change = update_days
        
        today_btn = toga.Button("TODAY", on_press=lambda w: self.set_today(), 
                                 style=Pack(width=65, font_size=10, color=M3_PRIMARY))
        
        controls.add(self.year_sel)
        controls.add(self.month_sel)
        controls.add(self.day_sel)
        controls.add(today_btn)
        self.box.add(controls)
        
        if not initial_date: initial_date = get_today_bs()
        self.set_date(initial_date)

    def set_date(self, date_str):
        if not date_str or len(date_str) < 10: return
        try:
            y, m, d = date_str.split("-")
            self.year_sel.value = y
            self.month_sel.value = m
            self.day_sel.value = d
        except: pass

    def set_today(self):
        from attendance.utils.nepali_date import get_today_bs
        self.set_date(get_today_bs())

    @property
    def value(self):
        return f"{self.year_sel.value}-{self.month_sel.value}-{self.day_sel.value}"
    
    @value.setter
    def value(self, val):
        self.set_date(val)
