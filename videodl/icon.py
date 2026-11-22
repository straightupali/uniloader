"""App icon, drawn with Pillow (no image files needed). Pick a style with ICON_STYLE."""
from PIL import Image, ImageChops, ImageDraw

from .paths import ASSETS

ICON_STYLE = "A"
INDIGO, VIOLET = (99, 102, 241), (168, 85, 247)
CORAL, PINK = (251, 113, 133), (236, 72, 153)
INK = (17, 19, 28)


def _gradient(s, c1, c2):
    """Diagonal gradient from top-left (c1) to bottom-right (c2)."""
    g = Image.linear_gradient("L").rotate(-45, expand=True)
    w, h = g.size
    g = g.crop((w // 4, h // 4, w * 3 // 4, h * 3 // 4)).resize((s, s))
    return Image.composite(Image.new("RGBA", (s, s), c2 + (255,)), Image.new("RGBA", (s, s), c1 + (255,)), g)


def _squircle(s):
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.235), fill=255)
    return m


def _line(d, pts, w, fill=255):
    d.line(pts, fill=fill, width=int(w), joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=fill)


def _arrow_mask(s, tray=True, scale=1.0, cy=0.5):
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    w, cx = s * 0.085 * scale, s / 2
    top, tip = s * (cy - 0.24 * scale), s * (cy + 0.09 * scale)
    d.rounded_rectangle([cx - w / 2, top - w / 2, cx + w / 2, tip], radius=w / 2, fill=255)  # shaft
    arm = s * 0.155 * scale
    _line(d, [(cx - arm, tip - arm), (cx, tip), (cx + arm, tip - arm)], w)               # head
    if tray:
        y, half, tw = s * (cy + 0.235 * scale), s * 0.2 * scale, w * 0.85
        d.rounded_rectangle([cx - half - tw / 2, y - tw / 2, cx + half + tw / 2, y + tw / 2],
                            radius=tw / 2, fill=255)
    return m


def _draw(style, s):
    shape = _squircle(s)
    if style == "A":    # indigo-violet tile, white arrow into a tray
        img = _gradient(s, INDIGO, VIOLET)
        img.paste((255, 255, 255, 255), mask=_arrow_mask(s))
    elif style == "B":  # play button with a download badge
        img = _gradient(s, CORAL, PINK)
        m = Image.new("L", (s, s), 0)
        d = ImageDraw.Draw(m)
        tri = [(s * 0.36, s * 0.27), (s * 0.36, s * 0.73), (s * 0.74, s * 0.5)]
        d.polygon(tri, fill=255)
        lw = s * 0.07
        d.line(tri + [tri[0]], fill=255, width=int(lw), joint="curve")
        for x, y in tri:  # round the corners
            d.ellipse([x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2], fill=255)
        img.paste((255, 255, 255, 255), mask=m)
        r, bx, by = s * 0.17, s * 0.74, s * 0.74
        badge = Image.new("L", (s, s), 0)
        ImageDraw.Draw(badge).ellipse([bx - r, by - r, bx + r, by + r], fill=255)
        img.paste(INK + (255,), mask=badge)
        a = _arrow_mask(s, tray=False, scale=0.42, cy=0.74).transform(
            (s, s), Image.AFFINE, (1, 0, -(bx - s / 2), 0, 1, 0))
        img.paste((255, 255, 255, 255), mask=a)
    elif style == "C":  # dark tile, gradient arrow
        img = Image.new("RGBA", (s, s), INK + (255,))
        img.paste(_gradient(s, INDIGO, VIOLET), mask=_arrow_mask(s))
    else:               # "D": light tile, gradient ring + arrow
        img = Image.new("RGBA", (s, s), (248, 249, 252, 255))
        ring = Image.new("L", (s, s), 0)
        d = ImageDraw.Draw(ring)
        d.ellipse([s * 0.16, s * 0.16, s * 0.84, s * 0.84], fill=255)
        d.ellipse([s * 0.235, s * 0.235, s * 0.765, s * 0.765], fill=0)
        both = ImageChops.lighter(ring, _arrow_mask(s, tray=False, scale=0.78, cy=0.47))
        img.paste(_gradient(s, INDIGO, VIOLET), mask=both)
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, mask=shape)
    return out


def make_icon(size=256, style=None):
    big = _draw(style or ICON_STYLE, size * 4)  # draw 4x bigger, then shrink = smooth edges
    return big.resize((size, size), Image.LANCZOS)


def icon_image(size=64):
    try:
        return Image.open(ASSETS / "icon.png").convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        return make_icon(size)
