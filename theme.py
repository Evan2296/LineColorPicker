"""
theme.py — UI color palette, layout constants, and font definitions.

All visual styling lives here. Change a value once and it propagates
across every widget in the app.

Palette: caramel / chocolate / mocha / earth tones
"""

# ---------------------------------------------------------------------------
# Background tones (dark → mid → panel)
# ---------------------------------------------------------------------------
BG_DARK      = "#1A0F07"   # deep espresso — root window base
BG_MID       = "#261508"   # dark chocolate — toolbar and button bar
BG_PANEL     = "#200E06"   # dark cocoa — right results panel

# ---------------------------------------------------------------------------
# Accent (caramel) — used for the primary action button, dots, and lines
# ---------------------------------------------------------------------------
ACCENT       = "#C8813A"   # warm caramel
ACCENT_DIM   = "#A86828"   # deeper caramel for hover state
ACCENT_FG    = "#1A0F07"   # dark espresso text drawn on top of caramel

# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
TEXT_PRIMARY = "#E8D2A8"   # warm parchment cream — main labels
TEXT_DIM     = "#7A5C38"   # muted mocha brown — secondary / hint text
TEXT_GREEN   = "#8DC060"   # earthy sage green — success toasts
TEXT_WARN    = "#D06848"   # terra cotta — error toasts

# ---------------------------------------------------------------------------
# Secondary buttons: dark chocolate (Undo, Reset)
# ---------------------------------------------------------------------------
BTN_SEC_BG   = "#3A2010"
BTN_SEC_FG   = "#C09060"
BTN_SEC_HOV  = "#4E2E18"   # hover
BTN_SEC_ACT  = "#623820"   # active / pressed

# ---------------------------------------------------------------------------
# Utility buttons: deep mocha (Copy Hex, Export .txt)
# ---------------------------------------------------------------------------
BTN_UTL_BG   = "#2C1A0C"
BTN_UTL_FG   = "#A07848"
BTN_UTL_HOV  = "#3E2412"   # hover
BTN_UTL_ACT  = "#502E18"   # active / pressed

# ---------------------------------------------------------------------------
# Decorative / border colours used inline in widgets
# ---------------------------------------------------------------------------
COLOR_SEP         = "#3A2010"   # 1 px column separator between canvas and panel
COLOR_GRAD_BG     = "#2C1A0C"   # gradient strip empty background
COLOR_GRAD_BORDER = "#3A2010"   # gradient strip border
COLOR_SWATCH_BDR  = "#3A2010"   # swatch tile border
COLOR_TOAST_BG    = "#2C1A0C"   # toast popup background

# ---------------------------------------------------------------------------
# Layout dimensions (pixels)
# ---------------------------------------------------------------------------
PANEL_W   = 320   # width of the right results panel
TOOLBAR_H = 38    # height of the top toolbar
BTNBAR_H  = 52    # height of the bottom button bar
PAD       = 10    # general padding unit

GRAD_H       = 22   # height of the gradient preview strip
SWATCH_SZ    = 36   # swatch square side length
SWATCH_COLS  = 4    # number of swatch columns in the grid
SWATCH_PAD   = 6    # padding between swatch cells

# ---------------------------------------------------------------------------
# Fonts (Menlo keeps the hex labels monospaced and readable)
# ---------------------------------------------------------------------------
FONT_MONO    = ("Menlo", 10)
FONT_MONO_SM = ("Menlo", 9)
FONT_MONO_LG = ("Menlo", 12, "bold")
FONT_MONO_XS = ("Menlo", 8)
