"""
widgets.py — Reusable tkinter widget factories.

Keeps button-creation logic in one place so hover/active styles
stay consistent everywhere they're used.
"""

import tkinter as tk
from theme import (
    ACCENT, ACCENT_FG, ACCENT_DIM,
    BTN_SEC_BG, BTN_SEC_FG, BTN_SEC_HOV, BTN_SEC_ACT,
    BTN_UTL_BG, BTN_UTL_FG, BTN_UTL_HOV, BTN_UTL_ACT,
    FONT_MONO,
)


def flat_button(parent, text, command, width=None, style="secondary"):
    """
    Create a borderless tkinter Button with hover and active colour transitions.

    Styles:
        "accent"    — caramel fill, used for the primary "Sample Colors" action
        "secondary" — dark chocolate, used for Undo and Reset
        "utility"   — deep mocha, used for Copy Hex and Export .txt

    Args:
        parent  : tkinter parent widget
        text    : button label string
        command : callable invoked on click
        width   : optional character width (passed to tk.Button)
        style   : one of "accent", "secondary", "utility"

    Returns:
        Configured tk.Button instance
    """
    style_map = {
        "accent":    (ACCENT,      ACCENT_FG,   ACCENT_DIM,  ACCENT_DIM),
        "secondary": (BTN_SEC_BG,  BTN_SEC_FG,  BTN_SEC_HOV, BTN_SEC_ACT),
        "utility":   (BTN_UTL_BG,  BTN_UTL_FG,  BTN_UTL_HOV, BTN_UTL_ACT),
    }
    bg, fg, hov, act = style_map.get(style, style_map["secondary"])

    kw = dict(
        text=text, command=command,
        bg=bg, fg=fg,
        font=FONT_MONO, relief="flat",
        bd=0, padx=12, pady=7,
        cursor="hand2",
        activebackground=act,
        activeforeground=fg,
    )
    if width:
        kw["width"] = width

    btn = tk.Button(parent, **kw)

    # Hover highlight — skip while disabled so the button stays visually muted
    def on_enter(e):
        if btn["state"] != "disabled":
            btn.config(bg=hov)

    def on_leave(e):
        if btn["state"] != "disabled":
            btn.config(bg=bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn
