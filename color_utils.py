"""
color_utils.py — Pure color math helpers (no UI dependencies).

These functions are stateless and can be unit-tested independently
of tkinter or Pillow.
"""


def sample_line(pixels, x0, y0, x1, y1, img_w, img_h):
    """
    Return every RGB pixel along the segment (x0,y0)→(x1,y1) using
    Bresenham's line algorithm.  Pixels outside the image bounds are skipped.

    Args:
        pixels  : PIL PixelAccess object (img.load())
        x0, y0  : start coordinate (image space)
        x1, y1  : end coordinate (image space)
        img_w, img_h : image dimensions for bounds-checking

    Returns:
        list of (r, g, b) tuples
    """
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
    """
    Remove duplicate RGB tuples while preserving the gradient-progression
    order (first occurrence wins, consecutive duplicates are skipped).

    Args:
        colors : iterable of (r, g, b) tuples

    Returns:
        list of unique (r, g, b) tuples in original order
    """
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
    """Convert an (r, g, b) triplet to an uppercase CSS hex string."""
    return f"#{r:02X}{g:02X}{b:02X}"


def sort_by_similarity(colors):
    """
    Re-order colors so visually similar ones sit next to each other.

    Uses a greedy nearest-neighbor traversal in RGB space, anchored at
    the darkest color so the result naturally reads dark → light.

    Args:
        colors : list of (r, g, b) tuples

    Returns:
        new list with the same colors in perceptually sorted order
    """
    if len(colors) <= 1:
        return list(colors)

    remaining = list(colors)
    remaining.sort(key=lambda c: c[0] + c[1] + c[2])   # darkest first
    sorted_colors = [remaining.pop(0)]

    while remaining:
        last = sorted_colors[-1]
        # Squared Euclidean distance in RGB space (no sqrt needed for comparison)
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
