"""
app.py — Main application window and all event-handling logic.

Responsibilities:
  - Open a file-picker so the user can choose an image
  - Build and lay out the tkinter window (toolbar, canvas, results panel, button bar)
  - Handle mouse events: add/undo trace points on the canvas
  - On Enter / Sample: walk every segment, collect unique colors, render results
  - Copy hex values to clipboard or export them to a .txt file

Entry point:  call main() from color_tracer.py
"""

import sys
import os
import datetime

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog

import theme as th
from color_utils import sample_line, deduplicate_ordered, rgb_to_hex, sort_by_similarity
from widgets import flat_button


# ---------------------------------------------------------------------------
# File picker — runs before the main window so it appears on top cleanly
# ---------------------------------------------------------------------------

def _pick_image():
    """
    Show a native open-file dialog and return the chosen path.
    Exits the process if the user cancels.
    """
    picker = tk.Tk()
    picker.withdraw()
    picker.attributes("-topmost", True)

    path = filedialog.askopenfilename(
        title="Choose an image to trace",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif"),
            ("All files", "*.*"),
        ],
    )
    picker.destroy()

    if not path:
        print("No file selected — exiting.")
        sys.exit(0)

    return path


# ---------------------------------------------------------------------------
# Window geometry helpers
# ---------------------------------------------------------------------------

def _compute_geometry(root, img_w, img_h):
    """
    Calculate the display scale and window size so the image fills the
    available screen space without overflowing macOS chrome.

    Returns:
        (scale, disp_w, disp_h, win_w, win_h)
    """
    root.update_idletasks()
    scr_w = root.winfo_screenwidth()  or 1440
    scr_h = root.winfo_screenheight() or 900

    CHROME_H = 180   # menu bar + title bar + dock + padding (macOS)
    avail_w  = max(600, scr_w - th.PANEL_W - th.PAD * 6)
    avail_h  = max(400, scr_h - CHROME_H - th.TOOLBAR_H - th.BTNBAR_H - th.PAD * 6)

    scale  = min(avail_w / img_w, avail_h / img_h)
    disp_w = int(img_w * scale)
    disp_h = int(img_h * scale)

    win_w  = min(disp_w + th.PANEL_W + th.PAD * 4 + 1, scr_w - th.PAD * 2)
    win_h  = min(disp_h + th.TOOLBAR_H + th.BTNBAR_H + th.PAD * 4, scr_h - CHROME_H)

    return scale, disp_w, disp_h, win_w, win_h


# ---------------------------------------------------------------------------
# Layout builders
# ---------------------------------------------------------------------------

def _build_layout(root):
    """
    Create and return the five top-level layout frames.

    Layout (top → bottom):
        top_bar  — filename + hint + point counter
        body     — left_col (canvas) | sep | right_col (results)
        btn_bar  — action buttons
    """
    top_bar = tk.Frame(root, bg=th.BG_MID, height=th.TOOLBAR_H)
    top_bar.pack(fill="x")
    top_bar.pack_propagate(False)

    body = tk.Frame(root, bg=th.BG_DARK)
    body.pack(fill="both", expand=True)

    left_col = tk.Frame(body, bg=th.BG_DARK)
    left_col.pack(side="left", fill="both", expand=True, padx=(th.PAD, 0), pady=th.PAD)

    # 1-px visual divider between canvas and results panel
    sep = tk.Frame(body, bg=th.COLOR_SEP, width=1)
    sep.pack(side="left", fill="y", pady=th.PAD)

    right_col = tk.Frame(body, bg=th.BG_PANEL, width=th.PANEL_W)
    right_col.pack(side="left", fill="y")
    right_col.pack_propagate(False)

    btn_bar = tk.Frame(root, bg=th.BG_MID, height=th.BTNBAR_H)
    btn_bar.pack(fill="x", side="bottom")
    btn_bar.pack_propagate(False)

    return top_bar, left_col, right_col, btn_bar


def _build_toolbar(top_bar, filename):
    """
    Populate the top toolbar with the filename label, hint text, and
    a live point-counter label (returned for later updates).
    """
    # Point counter — packed right first so it always gets its space
    point_label = tk.Label(
        top_bar,
        text="0 points",
        fg=th.ACCENT, bg=th.BG_MID,
        font=th.FONT_MONO,
    )
    point_label.pack(side="right", padx=12, pady=6)

    # Truncate long filenames so they don't crowd out the hint text
    display_name = filename if len(filename) <= 36 else filename[:33] + "…"
    tk.Label(
        top_bar,
        text=f"  {display_name}",
        fg=th.TEXT_PRIMARY, bg=th.BG_MID,
        font=th.FONT_MONO_LG,
        anchor="w",
    ).pack(side="left", padx=(4, 0), pady=6)

    tk.Label(
        top_bar,
        text="L-click add  ·  R-click undo  ·  Enter sample  ·  R reset",
        fg=th.TEXT_DIM, bg=th.BG_MID,
        font=th.FONT_MONO_XS,
    ).pack(side="left", padx=12, pady=6)

    return point_label


def _build_right_panel(right_col):
    """
    Build the results panel: stats label, gradient strip, and scrollable
    swatch grid.

    Returns a dict of widget references needed by the rendering functions.
    """
    # -- Stats strip ----------------------------------------------------------
    stats_frame = tk.Frame(right_col, bg=th.BG_PANEL)
    stats_frame.pack(fill="x", padx=12, pady=(14, 6))

    stats_label = tk.Label(
        stats_frame,
        text="No colors sampled yet.",
        fg=th.TEXT_DIM, bg=th.BG_PANEL,
        font=th.FONT_MONO_SM, justify="left",
        wraplength=th.PANEL_W - 24,
    )
    stats_label.pack(anchor="w")

    # -- Gradient strip -------------------------------------------------------
    grad_frame = tk.Frame(right_col, bg=th.BG_PANEL)
    grad_frame.pack(fill="x", padx=12, pady=(0, 8))

    grad_canvas = tk.Canvas(
        grad_frame,
        height=th.GRAD_H, bg=th.COLOR_GRAD_BG,
        highlightthickness=1, highlightbackground=th.COLOR_GRAD_BORDER,
    )
    grad_canvas.pack(fill="x")

    # Placeholder until the user samples colors
    grad_canvas.create_rectangle(
        0, 0, th.PANEL_W - 24, th.GRAD_H,
        fill=th.COLOR_GRAD_BG, outline="",
    )
    grad_canvas.create_text(
        (th.PANEL_W - 24) // 2, th.GRAD_H // 2,
        text="gradient will appear here",
        fill=th.TEXT_DIM, font=th.FONT_MONO_XS,
        tags="grad_hint",
    )

    # -- Scrollable swatch grid -----------------------------------------------
    swatch_outer = tk.Frame(right_col, bg=th.BG_PANEL)
    swatch_outer.pack(fill="both", expand=True)

    swatch_canvas = tk.Canvas(swatch_outer, bg=th.BG_PANEL, highlightthickness=0)
    swatch_canvas.pack(fill="both", expand=True)

    swatch_frame = tk.Frame(swatch_canvas, bg=th.BG_PANEL)
    swatch_window = swatch_canvas.create_window((0, 0), window=swatch_frame, anchor="nw")

    # Keep the inner frame width in sync with the canvas width
    def _on_frame_configure(e):
        swatch_canvas.configure(scrollregion=swatch_canvas.bbox("all"))
        swatch_canvas.itemconfig(swatch_window, width=swatch_canvas.winfo_width())

    swatch_frame.bind("<Configure>", _on_frame_configure)
    swatch_canvas.bind("<Configure>",
        lambda e: swatch_canvas.itemconfig(swatch_window, width=e.width))

    # macOS trackpad scroll — use sign-only because delta values can be tiny
    def _on_mousewheel(e):
        swatch_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    swatch_canvas.bind("<MouseWheel>", _on_mousewheel)
    swatch_frame.bind("<MouseWheel>",  _on_mousewheel)
    swatch_outer.bind("<MouseWheel>",  _on_mousewheel)

    return {
        "stats_label":    stats_label,
        "grad_canvas":    grad_canvas,
        "swatch_canvas":  swatch_canvas,
        "swatch_frame":   swatch_frame,
        "on_mousewheel":  _on_mousewheel,
    }


# ---------------------------------------------------------------------------
# Toast notification
# ---------------------------------------------------------------------------

def _make_toast(root, disp_w, disp_h):
    """
    Return a show_toast(msg, color) callable that pops a small borderless
    overlay at the bottom of the canvas area and auto-dismisses after 2 s.
    """
    _after_id = [None]

    def show_toast(msg, color=th.TEXT_GREEN):
        toast = tk.Toplevel(root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)

        tk.Label(
            toast, text=f"  {msg}  ",
            bg=th.COLOR_TOAST_BG, fg=color,
            font=th.FONT_MONO, relief="flat",
            padx=8, pady=6,
        ).pack()

        root.update_idletasks()
        rx = root.winfo_x() + th.PAD + disp_w // 2 - 80
        ry = root.winfo_y() + th.TOOLBAR_H + disp_h + 8
        toast.geometry(f"+{rx}+{ry}")

        if _after_id[0]:
            root.after_cancel(_after_id[0])
        _after_id[0] = root.after(2000, toast.destroy)

    return show_toast


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_gradient(grad_canvas, unique_colors):
    """
    Draw a segmented color strip across the gradient canvas.
    Each sampled color gets an equal-width vertical band.
    """
    grad_canvas.update_idletasks()
    w = grad_canvas.winfo_width() or (th.PANEL_W - 24)
    n = len(unique_colors)
    grad_canvas.delete("all")

    if n == 0:
        return
    if n == 1:
        r, g, b = unique_colors[0]
        grad_canvas.create_rectangle(0, 0, w, th.GRAD_H,
                                     fill=rgb_to_hex(r, g, b), outline="")
        return

    for i, (r, g, b) in enumerate(unique_colors):
        x0 = int(i * w / n)
        x1 = int((i + 1) * w / n)
        grad_canvas.create_rectangle(x0, 0, x1, th.GRAD_H,
                                     fill=rgb_to_hex(r, g, b), outline="")


def _render_swatches(root, swatch_frame, swatch_canvas, on_mousewheel,
                     unique_colors, show_toast):
    """
    Populate the swatch grid with one colored tile per unique color.
    Clicking any tile or its hex label copies that hex value to the clipboard.
    """
    for w in swatch_frame.winfo_children():
        w.destroy()

    for idx, (r, g, b) in enumerate(unique_colors):
        col     = idx % th.SWATCH_COLS
        row     = idx // th.SWATCH_COLS
        hex_val = rgb_to_hex(r, g, b)

        cell = tk.Frame(swatch_frame, bg=th.BG_PANEL)
        cell.grid(row=row, column=col,
                  padx=th.SWATCH_PAD, pady=th.SWATCH_PAD, sticky="nw")

        # Colored square
        swatch = tk.Canvas(
            cell, width=th.SWATCH_SZ, height=th.SWATCH_SZ,
            bg=hex_val, highlightthickness=1,
            highlightbackground=th.COLOR_SWATCH_BDR, cursor="hand2",
        )
        swatch.pack()

        # Hex label beneath the square
        lbl = tk.Label(
            cell, text=hex_val,
            fg=th.TEXT_DIM, bg=th.BG_PANEL,
            font=th.FONT_MONO_XS,
        )
        lbl.pack()

        # Click → copy this individual hex value
        def _copy(hx=hex_val):
            root.clipboard_clear()
            root.clipboard_append(hx)
            show_toast(f"Copied {hx}")

        swatch.bind("<Button-1>", lambda e, hx=hex_val: _copy(hx))
        lbl.bind("<Button-1>",    lambda e, hx=hex_val: _copy(hx))

        # Forward scroll events up to the swatch canvas
        cell.bind("<MouseWheel>",   on_mousewheel)
        swatch.bind("<MouseWheel>", on_mousewheel)
        lbl.bind("<MouseWheel>",    on_mousewheel)

    swatch_canvas.yview_moveto(0)


# ---------------------------------------------------------------------------
# Export helper
# ---------------------------------------------------------------------------

def _export_txt(image_dir, filename, last_hex_list, show_toast):
    """Write sampled hex/RGB values to a timestamped .txt file next to the source image."""
    base     = os.path.splitext(filename)[0]
    stamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_fn   = f"{base}_colors_{stamp}.txt"
    out_path = os.path.join(image_dir, out_fn)

    # Rebuild (r, g, b) from the stored hex strings
    unique_rgb = []
    for hx in last_hex_list:
        h = hx.lstrip("#")
        unique_rgb.append(tuple(int(h[i:i+2], 16) for i in (0, 2, 4)))

    lines = [
        "Color Tracer Export",
        f"Source : {filename}",
        f"Date   : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Colors : {len(last_hex_list)} unique",
        "",
        "--- HEX (gradient order) ---",
        ", ".join(last_hex_list),
        "",
        "--- HEX list (one per line) ---",
        *last_hex_list,
        "",
        "--- RGB breakdown ---",
        *[f"  rgb({r:3d}, {g:3d}, {b:3d})   {hx}"
          for (r, g, b), hx in zip(unique_rgb, last_hex_list)],
    ]

    try:
        with open(out_path, "w") as f:
            f.write("\n".join(lines))
        show_toast(f"✓  Saved {out_fn}")
        print(f"[color_tracer] Exported → {out_path}")
    except Exception as e:
        show_toast("Export failed — check terminal", color=th.TEXT_WARN)
        print(f"[color_tracer] Export error: {e}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    # -- 1. Pick an image file ------------------------------------------------
    image_path = _pick_image()

    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"Could not open image: {e}")
        sys.exit(1)

    img_w, img_h = img.size
    pixels    = img.load()
    filename  = os.path.basename(image_path)
    image_dir = os.path.dirname(image_path)

    # -- 2. Build the main window ---------------------------------------------
    root = tk.Tk()
    root.title(f"Color Tracer  ·  {filename}")
    root.configure(bg=th.BG_DARK)
    root.resizable(True, True)

    scale, disp_w, disp_h, win_w, win_h = _compute_geometry(root, img_w, img_h)
    root.geometry(f"{win_w}x{win_h}")

    img_display = img.resize((disp_w, disp_h), Image.LANCZOS)

    # -- 3. Lay out frames ----------------------------------------------------
    top_bar, left_col, right_col, btn_bar = _build_layout(root)

    # -- 4. Toolbar -----------------------------------------------------------
    point_label = _build_toolbar(top_bar, filename)

    # -- 5. Image canvas ------------------------------------------------------
    canvas = tk.Canvas(
        left_col,
        width=disp_w, height=disp_h,
        bg="#000000", highlightthickness=0, cursor="crosshair",
    )
    canvas.pack(expand=True)   # expand=True centers it inside left_col

    photo = ImageTk.PhotoImage(img_display)
    canvas.create_image(0, 0, anchor="nw", image=photo)
    canvas.image = photo   # keep a reference so Python doesn't GC it

    # -- 6. Results panel -----------------------------------------------------
    panel = _build_right_panel(right_col)
    stats_label   = panel["stats_label"]
    grad_canvas   = panel["grad_canvas"]
    swatch_canvas = panel["swatch_canvas"]
    swatch_frame  = panel["swatch_frame"]
    on_mousewheel = panel["on_mousewheel"]

    # -- 7. Toast helper ------------------------------------------------------
    show_toast = _make_toast(root, disp_w, disp_h)

    # -- 8. Mutable state (lists used so inner functions can rebind them) ------
    points       = []
    dot_ids      = []
    line_ids     = []
    last_hex_list = []

    # ── Canvas coordinate conversion ─────────────────────────────────────────
    def canvas_to_image(cx, cy):
        """Convert display-canvas coordinates to source-image coordinates."""
        return int(cx / scale), int(cy / scale)

    # ── Trace point management ────────────────────────────────────────────────
    def add_point(cx, cy):
        """Place a numbered dot on the canvas and connect it to the previous point."""
        r   = 4
        dot = canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=th.ACCENT, outline="#FFFFFF", width=1,
        )
        dot_ids.append(dot)

        if points:
            px, py = points[-1]
            lid = canvas.create_line(px, py, cx, cy,
                                     fill=th.ACCENT, width=1.5, dash=(4, 3))
            line_ids.append(lid)
        else:
            line_ids.append(None)

        canvas.create_text(
            cx + 8, cy - 8,
            text=str(len(points) + 1),
            fill=th.ACCENT, font=th.FONT_MONO_XS,
            anchor="w", tags="ptlabel",
        )
        points.append((cx, cy))
        point_label.config(text=f"{len(points)} point{'s' if len(points) != 1 else ''}")

    def undo_point(event=None):
        """Remove the most recently placed point and redraw remaining labels."""
        if not points:
            return
        points.pop()
        if dot_ids:
            canvas.delete(dot_ids.pop())
        if line_ids:
            lid = line_ids.pop()
            if lid is not None:
                canvas.delete(lid)

        # Redraw all numeric labels to keep numbering consecutive
        canvas.delete("ptlabel")
        for i, (px, py) in enumerate(points):
            canvas.create_text(
                px + 8, py - 8,
                text=str(i + 1),
                fill=th.ACCENT, font=th.FONT_MONO_XS,
                anchor="w", tags="ptlabel",
            )
        point_label.config(text=f"{len(points)} point{'s' if len(points) != 1 else ''}")

    def reset(event=None):
        """Clear all points, results, and reset the UI to its initial state."""
        nonlocal points, dot_ids, line_ids, last_hex_list
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=photo)
        points, dot_ids, line_ids, last_hex_list = [], [], [], []
        point_label.config(text="0 points")
        stats_label.config(text="No colors sampled yet.")

        # Restore gradient placeholder
        grad_canvas.delete("all")
        grad_canvas.create_rectangle(
            0, 0, th.PANEL_W - 24, th.GRAD_H,
            fill=th.COLOR_GRAD_BG, outline="",
        )
        grad_canvas.create_text(
            (th.PANEL_W - 24) // 2, th.GRAD_H // 2,
            text="gradient will appear here",
            fill=th.TEXT_DIM, font=th.FONT_MONO_XS,
        )

        for w in swatch_frame.winfo_children():
            w.destroy()

        _update_button_states()

    # ── Sample & output ───────────────────────────────────────────────────────
    def sample_and_output(event=None):
        """
        Walk every segment of the trace path, collect unique pixel colors,
        sort them perceptually, then update the gradient strip and swatch grid.
        """
        nonlocal last_hex_list

        if len(points) < 2:
            show_toast("Need at least 2 points!", color=th.TEXT_WARN)
            return

        # Collect raw pixel colors from every segment
        all_colors = []
        for i in range(len(points) - 1):
            cx0, cy0 = points[i]
            cx1, cy1 = points[i + 1]
            ix0, iy0 = canvas_to_image(cx0, cy0)
            ix1, iy1 = canvas_to_image(cx1, cy1)
            all_colors.extend(sample_line(pixels, ix0, iy0, ix1, iy1, img_w, img_h))

        unique        = sort_by_similarity(deduplicate_ordered(all_colors))
        last_hex_list = [rgb_to_hex(*c) for c in unique]

        # Terminal output for power users
        print(f"\n{'='*60}")
        print(f"Color Tracer — {len(unique)} unique colors from {filename}")
        print(f"{'='*60}")
        print(f"Points: {len(points)}  |  Pixels sampled: {len(all_colors)}  |  Unique: {len(unique)}")
        print("\n--- HEX values (gradient order) ---")
        print(", ".join(last_hex_list))
        print("\n--- RGB breakdown ---")
        for r, g, b in unique:
            print(f"  rgb({r:3d}, {g:3d}, {b:3d})   {rgb_to_hex(r,g,b)}")
        print(f"{'='*60}\n")

        # Update stats strip
        stats_label.config(
            text=(f"{len(unique)} unique colors  ·  "
                  f"{len(all_colors):,} px sampled  ·  "
                  f"{len(points)} points"),
            fg=th.TEXT_PRIMARY,
        )

        _render_gradient(grad_canvas, unique)
        _render_swatches(root, swatch_frame, swatch_canvas,
                         on_mousewheel, unique, show_toast)

        # Overlay actual pixel colors as tiny dots along the trace path
        step = max(1, len(all_colors) // 300)
        for i in range(0, len(all_colors), step):
            r, g, b    = all_colors[i]
            progress   = i / len(all_colors)
            seg        = min(int(progress * (len(points) - 1)), len(points) - 2)
            t          = (progress * (len(points) - 1)) - seg
            x0_, y0_   = points[seg]
            x1_, y1_   = points[seg + 1]
            cx_        = x0_ + t * (x1_ - x0_)
            cy_        = y0_ + t * (y1_ - y0_)
            canvas.create_oval(cx_ - 2, cy_ - 2, cx_ + 2, cy_ + 2,
                               fill=f"#{r:02X}{g:02X}{b:02X}", outline="", width=0)

        _update_button_states()
        show_toast(f"✓  {len(unique)} colors sampled")

    # ── Clipboard / export actions ────────────────────────────────────────────
    def copy_hex(event=None):
        """Copy all sampled hex values (comma-separated) to the clipboard."""
        if not last_hex_list:
            show_toast("No colors to copy yet.", color=th.TEXT_WARN)
            return
        root.clipboard_clear()
        root.clipboard_append(", ".join(last_hex_list))
        show_toast(f"✓  Copied {len(last_hex_list)} hex values")

    def export_txt(event=None):
        """Write sampled colors to a .txt file next to the source image."""
        if not last_hex_list:
            show_toast("No colors to export yet.", color=th.TEXT_WARN)
            return
        _export_txt(image_dir, filename, last_hex_list, show_toast)

    # ── Button bar ────────────────────────────────────────────────────────────
    btn_inner = tk.Frame(btn_bar, bg=th.BG_MID)
    btn_inner.pack(side="left", fill="y", padx=th.PAD, pady=6)

    btn_sample = flat_button(btn_inner, "▶  Sample Colors", sample_and_output, style="accent")
    btn_sample.pack(side="left", padx=(0, 8))

    btn_undo = flat_button(btn_inner, "↩  Undo Point", undo_point, style="secondary")
    btn_undo.pack(side="left", padx=(0, 6))

    btn_reset = flat_button(btn_inner, "⟳  Reset", reset, style="secondary")
    btn_reset.pack(side="left", padx=(0, 6))

    btn_right = tk.Frame(btn_bar, bg=th.BG_MID)
    btn_right.pack(side="right", fill="y", padx=th.PAD, pady=6)

    btn_export = flat_button(btn_right, "💾  Export .txt", export_txt, style="utility")
    btn_export.pack(side="right", padx=(6, 0))

    btn_copy = flat_button(btn_right, "📋  Copy Hex", copy_hex, style="utility")
    btn_copy.pack(side="right", padx=(0, 6))

    def _update_button_states():
        """Dim Copy and Export buttons when there are no results to act on."""
        has = bool(last_hex_list)
        btn_copy.config(
            state="normal" if has else "disabled",
            fg=th.BTN_UTL_FG if has else th.TEXT_DIM,
            bg=th.BTN_UTL_BG if has else th.BG_MID,
        )
        btn_export.config(
            state="normal" if has else "disabled",
            fg=th.BTN_UTL_FG if has else th.TEXT_DIM,
            bg=th.BTN_UTL_BG if has else th.BG_MID,
        )

    _update_button_states()

    # ── Keyboard shortcuts ────────────────────────────────────────────────────
    canvas.bind("<Button-1>", lambda e: add_point(e.x, e.y))
    canvas.bind("<Button-2>", lambda e: undo_point())   # middle click (some mice)
    canvas.bind("<Button-3>", lambda e: undo_point())   # right click
    root.bind("<Return>",   sample_and_output)
    root.bind("<KP_Enter>", sample_and_output)
    root.bind("r",          reset)
    root.bind("R",          reset)
    root.bind("q",          lambda e: root.destroy())
    root.bind("Q",          lambda e: root.destroy())
    root.bind("<Escape>",   lambda e: root.destroy())

    root.mainloop()
