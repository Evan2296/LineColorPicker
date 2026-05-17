#!/usr/bin/env python3
"""
color_tracer.py — Freehand pixel color sampler for macOS
---------------------------------------------------------
Just run:  python3 color_tracer.py
A file browser will open so you can pick your image.
The script auto-switches to a Python with tkinter if needed.

Controls:
  Left click    — add a point to your trace path
  Right click   — undo last point
  Enter         — sample all unique colors along the path
  R             — reset all points and start over
  Q / Escape    — quit
"""

import sys
import os
import subprocess

# ---------------------------------------------------------------------------
# Auto-select a Python that has tkinter if the current one doesn't.
# ---------------------------------------------------------------------------
def _ensure_tkinter():
    try:
        import tkinter  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    candidates = [
        "/opt/homebrew/bin/python3.11",
        "/opt/homebrew/bin/python3.12",
        "/opt/homebrew/bin/python3.10",
        "/opt/homebrew/bin/python3",
        "/usr/bin/python3",
    ]
    for py in candidates:
        if not os.path.exists(py):
            continue
        result = subprocess.run([py, "-c", "import tkinter"], capture_output=True)
        if result.returncode == 0:
            print(f"[color_tracer] Re-launching with {py} (has tkinter)...")
            os.execv(py, [py] + sys.argv)

    print(
        "\nERROR: Could not find a Python with tkinter.\n"
        "Fix:   brew install python-tk@3.11\n"
        "Then run this script again.\n"
    )
    sys.exit(1)

_ensure_tkinter()

# ---------------------------------------------------------------------------
# Normal imports
# ---------------------------------------------------------------------------
import io
import datetime
from PIL import Image, ImageTk, ImageDraw
import tkinter as tk
from tkinter import filedialog, messagebox

# ---------------------------------------------------------------------------
# Color math helpers
# ---------------------------------------------------------------------------

def sample_line(pixels, x0, y0, x1, y1, img_w, img_h):
    """Sample every pixel along a segment using Bresenham's algorithm."""
    samples = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        if 0 <= x < img_w and 0 <= y < img_h:
            px = pixels[x, y]
            samples.append((px[0], px[1], px[2]))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return samples


def deduplicate_ordered(colors):
    """Remove duplicates while preserving gradient progression order."""
    seen = set()
    result = []
    prev = None
    for c in colors:
        if c != prev and c not in seen:
            seen.add(c)
            result.append(c)
        prev = c
    return result


def rgb_to_hex(r, g, b):
    return f"#{r:02X}{g:02X}{b:02X}"


def sort_by_similarity(colors):
    """
    Re-order colors so visually similar ones sit next to each other.
    Uses a greedy nearest-neighbor traversal in RGB space, starting
    from the darkest color so the result reads dark → light naturally.
    """
    if len(colors) <= 1:
        return list(colors)
    remaining = list(colors)
    # Anchor: start from the darkest color
    remaining.sort(key=lambda c: c[0] + c[1] + c[2])
    sorted_colors = [remaining.pop(0)]
    while remaining:
        last = sorted_colors[-1]
        # Pick the closest unused color by squared RGB Euclidean distance
        closest_idx = min(
            range(len(remaining)),
            key=lambda i: (
                (remaining[i][0] - last[0]) ** 2 +
                (remaining[i][1] - last[1]) ** 2 +
                (remaining[i][2] - last[2]) ** 2
            )
        )
        sorted_colors.append(remaining.pop(closest_idx))
    return sorted_colors


# ---------------------------------------------------------------------------
# UI constants
# ---------------------------------------------------------------------------
BG_DARK      = "#0E1720"   # deep navy base
BG_MID       = "#141F2B"   # toolbar / button bar
BG_PANEL     = "#111A24"   # right panel
ACCENT       = "#FFD700"   # gold — primary action
ACCENT_DIM   = "#C9A800"   # gold hover
ACCENT_FG    = "#0E1720"   # text on gold buttons
TEXT_PRIMARY = "#C8DFF0"   # light sky — default label text
TEXT_DIM     = "#4A6A82"   # muted steel blue
TEXT_GREEN   = "#3CFFA0"   # success toast
TEXT_WARN    = "#FF7070"   # error toast

# Secondary button: dark-steel (Undo, Reset)
BTN_SEC_BG   = "#1A3348"
BTN_SEC_FG   = "#8BBDD8"
BTN_SEC_HOV  = "#254D6A"
BTN_SEC_ACT  = "#2E6080"

# Utility button: slightly lighter navy (Copy, Export)
BTN_UTL_BG   = "#152A3C"
BTN_UTL_FG   = "#6AAEC8"
BTN_UTL_HOV  = "#1E3D55"
BTN_UTL_ACT  = "#274E68"

PANEL_W      = 320
TOOLBAR_H    = 38
BTNBAR_H     = 52
PAD          = 10

FONT_MONO    = ("Menlo", 10)
FONT_MONO_SM = ("Menlo", 9)
FONT_MONO_LG = ("Menlo", 12, "bold")
FONT_MONO_XS = ("Menlo", 8)


# ---------------------------------------------------------------------------
# Reusable flat button factory
#   style: "accent"  → gold fill (primary action)
#          "secondary" → dark steel (undo/reset)
#          "utility"   → dark navy  (copy/export)
# ---------------------------------------------------------------------------
def flat_button(parent, text, command, width=None, style="secondary"):
    styles = {
        "accent":    (ACCENT,      ACCENT_FG,   ACCENT_DIM,  ACCENT_DIM),
        "secondary": (BTN_SEC_BG,  BTN_SEC_FG,  BTN_SEC_HOV, BTN_SEC_ACT),
        "utility":   (BTN_UTL_BG,  BTN_UTL_FG,  BTN_UTL_HOV, BTN_UTL_ACT),
    }
    bg, fg, hov, act = styles.get(style, styles["secondary"])

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

    def on_enter(e):
        if btn["state"] != "disabled":
            btn.config(bg=hov)
    def on_leave(e):
        if btn["state"] != "disabled":
            btn.config(bg=bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
def main():

    # ── File picker ──────────────────────────────────────────────────────────
    picker = tk.Tk()
    picker.withdraw()
    picker.attributes("-topmost", True)

    image_path = filedialog.askopenfilename(
        title="Choose an image to trace",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif"),
            ("All files", "*.*"),
        ]
    )
    picker.destroy()

    if not image_path:
        print("No file selected — exiting.")
        sys.exit(0)

    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"Could not open image: {e}")
        sys.exit(1)

    img_w, img_h = img.size
    pixels = img.load()
    filename  = os.path.basename(image_path)
    image_dir = os.path.dirname(image_path)

    # ── Root window (hidden until laid out) ──────────────────────────────────
    root = tk.Tk()
    root.title(f"Color Tracer  ·  {filename}")
    root.configure(bg=BG_DARK)
    root.resizable(True, True)

    # Measure usable screen area (need to update once for accurate reading)
    root.update_idletasks()
    scr_w = root.winfo_screenwidth()
    scr_h = root.winfo_screenheight()

    # Fallback for systems that report 0 before window is fully mapped
    if scr_w < 100:
        scr_w = 1440
    if scr_h < 100:
        scr_h = 900

    # Reserve space for macOS chrome: menu bar + title bar + dock + padding
    CHROME_H = 180
    avail_w  = max(600, scr_w - PANEL_W - PAD * 6)
    avail_h  = max(400, scr_h - CHROME_H - TOOLBAR_H - BTNBAR_H - PAD * 6)

    # Allow upscaling small images to fill the available space (no 1.0 cap)
    scale    = min(avail_w / img_w, avail_h / img_h)
    disp_w   = int(img_w * scale)
    disp_h   = int(img_h * scale)

    img_display = img.resize((disp_w, disp_h), Image.LANCZOS)

    # Cap the window size explicitly so it never overflows the screen
    win_w = min(disp_w + PANEL_W + PAD * 4 + 1, scr_w - PAD * 2)
    win_h = min(disp_h + TOOLBAR_H + BTNBAR_H + PAD * 4, scr_h - CHROME_H)
    root.geometry(f"{win_w}x{win_h}")

    # ── Outer layout frames ───────────────────────────────────────────────────
    #  [ top_bar ──────────────────────────────── ]
    #  [ left_col (canvas) | right_col (results)  ]
    #  [ btn_bar ──────────────────────────────── ]

    top_bar = tk.Frame(root, bg=BG_MID, height=TOOLBAR_H)
    top_bar.pack(fill="x")
    top_bar.pack_propagate(False)

    body = tk.Frame(root, bg=BG_DARK)
    body.pack(fill="both", expand=True)

    left_col = tk.Frame(body, bg=BG_DARK)
    left_col.pack(side="left", fill="both", expand=True, padx=(PAD, 0), pady=PAD)

    sep = tk.Frame(body, bg="#2A2A2A", width=1)
    sep.pack(side="left", fill="y", pady=PAD)

    right_col = tk.Frame(body, bg=BG_PANEL, width=PANEL_W)
    right_col.pack(side="left", fill="y", padx=0, pady=0)
    right_col.pack_propagate(False)

    btn_bar = tk.Frame(root, bg=BG_MID, height=BTNBAR_H)
    btn_bar.pack(fill="x", side="bottom")
    btn_bar.pack_propagate(False)

    # ── Top toolbar ───────────────────────────────────────────────────────────
    # point counter packed first (right) so it always gets its space
    point_label = tk.Label(
        top_bar,
        text="0 points",
        fg=ACCENT, bg=BG_MID,
        font=FONT_MONO,
    )
    point_label.pack(side="right", padx=12, pady=6)

    # Truncate very long filenames so they don't crowd out the hint
    display_name = filename if len(filename) <= 36 else filename[:33] + "…"
    tk.Label(
        top_bar,
        text=f"  {display_name}",
        fg=TEXT_PRIMARY, bg=BG_MID,
        font=FONT_MONO_LG,
        anchor="w",
    ).pack(side="left", padx=(4, 0), pady=6)

    hint_label = tk.Label(
        top_bar,
        text="L-click add  ·  R-click undo  ·  Enter sample  ·  R reset",
        fg=TEXT_DIM, bg=BG_MID,
        font=FONT_MONO_XS,
    )
    hint_label.pack(side="left", padx=12, pady=6)

    # ── Canvas ────────────────────────────────────────────────────────────────
    canvas = tk.Canvas(
        left_col,
        width=disp_w, height=disp_h,
        bg="#000000", highlightthickness=0, cursor="crosshair",
    )
    # expand=True centers the fixed-size canvas in the (possibly larger) left_col
    canvas.pack(expand=True)

    photo = ImageTk.PhotoImage(img_display)
    canvas.create_image(0, 0, anchor="nw", image=photo)
    canvas.image = photo

    # ── Right panel internals ─────────────────────────────────────────────────
    # Stats strip
    stats_frame = tk.Frame(right_col, bg=BG_PANEL)
    stats_frame.pack(fill="x", padx=12, pady=(14, 6))

    stats_label = tk.Label(
        stats_frame,
        text="No colors sampled yet.",
        fg=TEXT_DIM, bg=BG_PANEL,
        font=FONT_MONO_SM, justify="left", wraplength=PANEL_W - 24,
    )
    stats_label.pack(anchor="w")

    # Gradient strip
    grad_frame = tk.Frame(right_col, bg=BG_PANEL)
    grad_frame.pack(fill="x", padx=12, pady=(0, 8))

    GRAD_H = 22
    grad_canvas = tk.Canvas(
        grad_frame,
        height=GRAD_H, bg="#2A2A2A",
        highlightthickness=1, highlightbackground="#333333",
    )
    grad_canvas.pack(fill="x")

    grad_placeholder = grad_canvas.create_rectangle(
        0, 0, PANEL_W - 24, GRAD_H,
        fill="#2A2A2A", outline="",
    )
    grad_canvas.create_text(
        (PANEL_W - 24) // 2, GRAD_H // 2,
        text="gradient will appear here",
        fill=TEXT_DIM, font=FONT_MONO_XS,
        tags="grad_hint",
    )

    # Scrollable swatch grid
    swatch_outer = tk.Frame(right_col, bg=BG_PANEL)
    swatch_outer.pack(fill="both", expand=True, padx=0, pady=0)

    swatch_canvas = tk.Canvas(
        swatch_outer, bg=BG_PANEL,
        highlightthickness=0,
    )
    swatch_canvas.pack(fill="both", expand=True)

    swatch_frame = tk.Frame(swatch_canvas, bg=BG_PANEL)
    swatch_window = swatch_canvas.create_window(
        (0, 0), window=swatch_frame, anchor="nw"
    )

    def _on_swatch_configure(e):
        swatch_canvas.configure(scrollregion=swatch_canvas.bbox("all"))
        swatch_canvas.itemconfig(swatch_window, width=swatch_canvas.winfo_width())

    swatch_frame.bind("<Configure>", _on_swatch_configure)
    swatch_canvas.bind("<Configure>",
        lambda e: swatch_canvas.itemconfig(swatch_window, width=e.width))

    # Mousewheel scroll on the swatch panel (fires on canvas, frame, and outer container)
    # Use sign-only (not /120) — macOS trackpad sends small delta values that round to 0
    def _on_mousewheel(e):
        swatch_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
    swatch_canvas.bind("<MouseWheel>", _on_mousewheel)
    swatch_frame.bind("<MouseWheel>", _on_mousewheel)
    swatch_outer.bind("<MouseWheel>", _on_mousewheel)

    # ── State ─────────────────────────────────────────────────────────────────
    points   = []
    dot_ids  = []
    line_ids = []
    last_hex_list = []   # persisted for copy/export

    # ── Toast notification ────────────────────────────────────────────────────
    _toast_after_id = [None]

    def show_toast(msg, color=TEXT_GREEN):
        toast = tk.Toplevel(root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)

        lbl = tk.Label(
            toast, text=f"  {msg}  ",
            bg="#222222", fg=color,
            font=FONT_MONO, relief="flat",
            padx=8, pady=6,
        )
        lbl.pack()

        # Position bottom-center of canvas area
        root.update_idletasks()
        rx = root.winfo_x() + PAD + disp_w // 2 - 80
        ry = root.winfo_y() + TOOLBAR_H + disp_h + 8
        toast.geometry(f"+{rx}+{ry}")

        if _toast_after_id[0]:
            root.after_cancel(_toast_after_id[0])
        _toast_after_id[0] = root.after(2000, toast.destroy)

    # ── Canvas coordinate helpers ─────────────────────────────────────────────
    def canvas_to_image(cx, cy):
        return int(cx / scale), int(cy / scale)

    # ── Drawing helpers ───────────────────────────────────────────────────────
    def add_point(cx, cy):
        r = 4
        dot = canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=ACCENT, outline="#FFFFFF", width=1,
        )
        dot_ids.append(dot)
        if points:
            px, py = points[-1]
            lid = canvas.create_line(
                px, py, cx, cy,
                fill=ACCENT, width=1.5, dash=(4, 3),
            )
            line_ids.append(lid)
        else:
            line_ids.append(None)
        canvas.create_text(
            cx + 8, cy - 8,
            text=str(len(points) + 1),
            fill=ACCENT, font=FONT_MONO_XS,
            anchor="w", tags="ptlabel",
        )
        points.append((cx, cy))
        point_label.config(text=f"{len(points)} point{'s' if len(points) != 1 else ''}")

    def undo_point(event=None):
        if not points:
            return
        points.pop()
        if dot_ids:
            canvas.delete(dot_ids.pop())
        if line_ids:
            lid = line_ids.pop()
            if lid is not None:
                canvas.delete(lid)
        canvas.delete("ptlabel")
        for i, (px, py) in enumerate(points):
            canvas.create_text(
                px + 8, py - 8,
                text=str(i + 1),
                fill=ACCENT, font=FONT_MONO_XS,
                anchor="w", tags="ptlabel",
            )
        point_label.config(text=f"{len(points)} point{'s' if len(points) != 1 else ''}")

    def reset(event=None):
        nonlocal points, dot_ids, line_ids, last_hex_list
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=photo)
        points, dot_ids, line_ids, last_hex_list = [], [], [], []
        point_label.config(text="0 points")
        stats_label.config(text="No colors sampled yet.")
        # Clear gradient
        grad_canvas.delete("all")
        grad_canvas.create_rectangle(
            0, 0, PANEL_W - 24, GRAD_H, fill="#2A2A2A", outline="")
        grad_canvas.create_text(
            (PANEL_W - 24) // 2, GRAD_H // 2,
            text="gradient will appear here",
            fill=TEXT_DIM, font=FONT_MONO_XS,
        )
        # Clear swatches
        for w in swatch_frame.winfo_children():
            w.destroy()
        _update_button_states()

    # ── Gradient strip renderer ───────────────────────────────────────────────
    def render_gradient(unique_colors):
        grad_canvas.update_idletasks()
        w = grad_canvas.winfo_width()
        if w < 4:
            w = PANEL_W - 24
        n = len(unique_colors)
        grad_canvas.delete("all")
        if n == 0:
            return
        if n == 1:
            r, g, b = unique_colors[0]
            grad_canvas.create_rectangle(0, 0, w, GRAD_H,
                                         fill=rgb_to_hex(r, g, b), outline="")
            return
        # Draw one vertical stripe per color (fast, no PIL needed)
        for i, (r, g, b) in enumerate(unique_colors):
            x0 = int(i * w / n)
            x1 = int((i + 1) * w / n)
            grad_canvas.create_rectangle(
                x0, 0, x1, GRAD_H,
                fill=rgb_to_hex(r, g, b), outline="",
            )

    # ── Swatch grid renderer ──────────────────────────────────────────────────
    SWATCH_SZ   = 36
    SWATCH_COLS = 4
    SWATCH_PAD  = 6

    def render_swatches(unique_colors):
        for w in swatch_frame.winfo_children():
            w.destroy()

        for idx, (r, g, b) in enumerate(unique_colors):
            col = idx % SWATCH_COLS
            row = idx // SWATCH_COLS
            hex_val = rgb_to_hex(r, g, b)

            cell = tk.Frame(swatch_frame, bg=BG_PANEL)
            cell.grid(
                row=row, column=col,
                padx=SWATCH_PAD, pady=SWATCH_PAD,
                sticky="nw",
            )

            # Colored square
            swatch = tk.Canvas(
                cell, width=SWATCH_SZ, height=SWATCH_SZ,
                bg=hex_val, highlightthickness=1,
                highlightbackground="#333333", cursor="hand2",
            )
            swatch.pack()

            # Hex label below
            lbl = tk.Label(
                cell, text=hex_val,
                fg=TEXT_DIM, bg=BG_PANEL,
                font=FONT_MONO_XS,
            )
            lbl.pack()

            # Click to copy individual swatch
            def _copy_swatch(hx=hex_val):
                root.clipboard_clear()
                root.clipboard_append(hx)
                show_toast(f"Copied {hx}")

            swatch.bind("<Button-1>", lambda e, hx=hex_val: _copy_swatch(hx))
            lbl.bind("<Button-1>",    lambda e, hx=hex_val: _copy_swatch(hx))

            # Propagate scroll from every child widget up to the swatch canvas
            cell.bind("<MouseWheel>",   _on_mousewheel)
            swatch.bind("<MouseWheel>", _on_mousewheel)
            lbl.bind("<MouseWheel>",    _on_mousewheel)

        swatch_canvas.yview_moveto(0)

    # ── Sample & output ───────────────────────────────────────────────────────
    def sample_and_output(event=None):
        nonlocal last_hex_list
        if len(points) < 2:
            show_toast("Need at least 2 points!", color="#FF6666")
            return

        all_colors = []
        for i in range(len(points) - 1):
            cx0, cy0 = points[i]
            cx1, cy1 = points[i + 1]
            ix0, iy0 = canvas_to_image(cx0, cy0)
            ix1, iy1 = canvas_to_image(cx1, cy1)
            all_colors.extend(sample_line(pixels, ix0, iy0, ix1, iy1, img_w, img_h))

        unique   = sort_by_similarity(deduplicate_ordered(all_colors))
        hex_list = [rgb_to_hex(*c) for c in unique]
        last_hex_list = hex_list

        # ── Terminal output (unchanged, power-user friendly) ──────────────
        print(f"\n{'='*60}")
        print(f"Color Tracer — {len(unique)} unique colors from {filename}")
        print(f"{'='*60}")
        print(f"Points: {len(points)}  |  Pixels sampled: {len(all_colors)}  |  Unique: {len(unique)}")
        print(f"\n--- HEX values (gradient order) ---")
        print(", ".join(hex_list))
        print(f"\n--- RGB breakdown ---")
        for r, g, b in unique:
            print(f"  rgb({r:3d}, {g:3d}, {b:3d})   {rgb_to_hex(r,g,b)}")
        print(f"{'='*60}\n")

        # ── Stats line ────────────────────────────────────────────────────
        stats_label.config(
            text=(
                f"{len(unique)} unique colors  ·  "
                f"{len(all_colors):,} px sampled  ·  "
                f"{len(points)} points"
            ),
            fg=TEXT_PRIMARY,
        )

        # ── Gradient strip ────────────────────────────────────────────────
        render_gradient(unique)

        # ── Swatch grid ───────────────────────────────────────────────────
        render_swatches(unique)

        # ── Overlay colored dots on canvas path ───────────────────────────
        step = max(1, len(all_colors) // 300)
        for i in range(0, len(all_colors), step):
            r, g, b = all_colors[i]
            progress = i / len(all_colors)
            seg = min(int(progress * (len(points) - 1)), len(points) - 2)
            t   = (progress * (len(points) - 1)) - seg
            x0_, y0_ = points[seg]
            x1_, y1_ = points[seg + 1]
            cx_ = x0_ + t * (x1_ - x0_)
            cy_ = y0_ + t * (y1_ - y0_)
            canvas.create_oval(
                cx_ - 2, cy_ - 2, cx_ + 2, cy_ + 2,
                fill=f"#{r:02X}{g:02X}{b:02X}", outline="", width=0,
            )

        _update_button_states()
        show_toast(f"✓  {len(unique)} colors sampled")

    # ── Copy all hex to clipboard ─────────────────────────────────────────────
    def copy_hex(event=None):
        if not last_hex_list:
            show_toast("No colors to copy yet.", color="#FF6666")
            return
        text = ", ".join(last_hex_list)
        root.clipboard_clear()
        root.clipboard_append(text)
        show_toast(f"✓  Copied {len(last_hex_list)} hex values")

    # ── Auto-export .txt next to source image ─────────────────────────────────
    def export_txt(event=None):
        if not last_hex_list:
            show_toast("No colors to export yet.", color="#FF6666")
            return

        base   = os.path.splitext(filename)[0]
        stamp  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_fn = f"{base}_colors_{stamp}.txt"
        out_path = os.path.join(image_dir, out_fn)

        unique_rgb = []
        # Rebuild RGB from hex list
        for hx in last_hex_list:
            hx = hx.lstrip("#")
            unique_rgb.append(tuple(int(hx[i:i+2], 16) for i in (0, 2, 4)))

        lines = [
            f"Color Tracer Export",
            f"Source : {filename}",
            f"Date   : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Colors : {len(last_hex_list)} unique",
            "",
            "--- HEX (gradient order) ---",
            ", ".join(last_hex_list),
            "",
            "--- HEX list (one per line) ---",
        ]
        lines += last_hex_list
        lines += [
            "",
            "--- RGB breakdown ---",
        ]
        for (r, g, b), hx in zip(unique_rgb, last_hex_list):
            lines.append(f"  rgb({r:3d}, {g:3d}, {b:3d})   {hx}")

        try:
            with open(out_path, "w") as f:
                f.write("\n".join(lines))
            show_toast(f"✓  Saved {out_fn}")
            print(f"[color_tracer] Exported → {out_path}")
        except Exception as e:
            show_toast("Export failed — check terminal", color="#FF6666")
            print(f"[color_tracer] Export error: {e}")

    # ── Button bar ────────────────────────────────────────────────────────────
    btn_inner = tk.Frame(btn_bar, bg=BG_MID)
    btn_inner.pack(side="left", fill="y", padx=PAD, pady=6)

    btn_sample = flat_button(btn_inner, "▶  Sample Colors", sample_and_output, style="accent")
    btn_sample.pack(side="left", padx=(0, 8))

    btn_undo = flat_button(btn_inner, "↩  Undo Point", undo_point, style="secondary")
    btn_undo.pack(side="left", padx=(0, 6))

    btn_reset = flat_button(btn_inner, "⟳  Reset", reset, style="secondary")
    btn_reset.pack(side="left", padx=(0, 6))

    btn_right = tk.Frame(btn_bar, bg=BG_MID)
    btn_right.pack(side="right", fill="y", padx=PAD, pady=6)

    btn_export = flat_button(btn_right, "💾  Export .txt", export_txt, style="utility")
    btn_export.pack(side="right", padx=(6, 0))

    btn_copy = flat_button(btn_right, "📋  Copy Hex", copy_hex, style="utility")
    btn_copy.pack(side="right", padx=(0, 6))

    def _update_button_states():
        has = bool(last_hex_list)
        btn_copy.config(
            state="normal" if has else "disabled",
            fg=BTN_UTL_FG if has else TEXT_DIM,
            bg=BTN_UTL_BG if has else BG_MID,
        )
        btn_export.config(
            state="normal" if has else "disabled",
            fg=BTN_UTL_FG if has else TEXT_DIM,
            bg=BTN_UTL_BG if has else BG_MID,
        )

    _update_button_states()

    # ── Key bindings ──────────────────────────────────────────────────────────
    canvas.bind("<Button-1>", lambda e: add_point(e.x, e.y))
    canvas.bind("<Button-2>", lambda e: undo_point())
    canvas.bind("<Button-3>", lambda e: undo_point())
    root.bind("<Return>",   sample_and_output)
    root.bind("<KP_Enter>", sample_and_output)
    root.bind("r",          reset)
    root.bind("R",          reset)
    root.bind("q",          lambda e: root.destroy())
    root.bind("Q",          lambda e: root.destroy())
    root.bind("<Escape>",   lambda e: root.destroy())

    root.mainloop()


if __name__ == "__main__":
    main()
