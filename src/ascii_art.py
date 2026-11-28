"""Generates a compact Retro CRT Amber ASCII SVG from an album cover or image."""
from __future__ import annotations

import html
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from crt_svg import (
    AMBER_BRIGHT,
    AMBER_CORE,
    AMBER_DIM,
    AMBER_MID,
    FONT_STACK,
    PANEL_DIVIDER,
    _crt_chrome,
    _crt_defs,
)

RAMP = " .:-=+*#%@"


def _tier_color(val: float) -> str:
    if val >= 0.72:
        return AMBER_BRIGHT
    if val >= 0.38:
        return AMBER_CORE
    return AMBER_MID


def _build_spans(row_vals: np.ndarray, row_y: float, x_off: float, cw: float) -> list[str]:
    """Group adjacent non-space runs by amber brightness tier for crisp SVG text."""
    spans: list[str] = []
    n = len(row_vals)
    idx = 0
    while idx < n:
        ch = RAMP[int(row_vals[idx] * (len(RAMP) - 1))]
        if ch == " ":
            idx += 1
            continue
        tier = _tier_color(float(row_vals[idx]))
        start = idx
        chars = [ch]
        idx += 1
        while idx < n:
            nxt = RAMP[int(row_vals[idx] * (len(RAMP) - 1))]
            if nxt == " " or _tier_color(float(row_vals[idx])) != tier:
                break
            chars.append(nxt)
            idx += 1
        body = html.escape("".join(chars), quote=True)
        sx = x_off + start * cw
        sw = len(chars) * cw
        spans.append(
            f'<text x="{sx:.1f}" y="{row_y:.1f}" textLength="{sw:.1f}" fill="{tier}">{body}</text>'
        )
    return spans


def render_currents_crt(
    src_path: str | Path = "media/images/currents-cover.jpg",
    out_path: str | Path = "media/svg/currents_crt.svg",
) -> str:
    """Convert image into a compact Retro CRT Amber ASCII terminal SVG (350x356)."""
    w, h = 350, 356
    prefix = "cur"
    cols, cw, lh, fs = 76, 3.55, 5.1, 5.4

    im = Image.open(src_path).convert("L")
    rows = min(53, round(cols * im.height / im.width * (cw / lh)))

    im_sharp = im.filter(ImageFilter.UnsharpMask(radius=4, percent=180, threshold=2))
    im_eq = ImageOps.autocontrast(im_sharp, cutoff=2)
    g = np.asarray(im_eq.resize((cols, rows), Image.Resampling.LANCZOS), dtype=float) / 255.0

    blur = (
        np.asarray(
            im_eq.filter(ImageFilter.GaussianBlur(radius=32)).resize((cols, rows), Image.Resampling.BILINEAR),
            dtype=float,
        )
        / 255.0
    )
    g_mix = np.clip(g * 0.55 + (g - blur + 0.5) * 0.45, 0, 1)

    lo, hi = np.percentile(g_mix, [5, 95])
    lum = np.clip((g_mix - lo) / max(hi - lo, 1e-5), 0, 1)
    lum = np.clip((lum - 0.45) * 1.65 + 0.5, 0, 1)

    edges = (
        np.asarray(
            im_sharp.filter(ImageFilter.FIND_EDGES).resize((cols, rows), Image.Resampling.LANCZOS),
            dtype=float,
        )
        / 255.0
    )
    edges = np.clip((edges - 0.12) * 2.0, 0, 1)
    v = np.clip(lum - edges * 0.55, 0, 1)

    art_w = cols * cw
    art_h = rows * lh
    x_off = (w - art_w) / 2
    y_off = 47 + max(0.0, (272 - art_h) / 2)

    groups = []
    for g_idx in range(0, rows, 2):
        pair = []
        for r in range(g_idx, min(g_idx + 2, rows)):
            pair.extend(_build_spans(v[r], y_off + (r + 1) * lh, x_off, cw))
        if pair:
            delay = (g_idx // 2) * 0.025
            groups.append(f'<g class="r" style="animation-delay:{delay:.3f}s">{"".join(pair)}</g>')

    chrome_base, chrome_overlay = _crt_chrome(
        prefix,
        w,
        h,
        "MUSIC // Tame Impala",
        "ASCII ART",
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
text{{font-family:{FONT_STACK}}}
.bar-t{{font-size:11px;font-weight:700;fill:{AMBER_CORE};letter-spacing:0.3px}}
.bar-r{{font-size:10px;fill:{AMBER_MID};letter-spacing:0.3px}}
.asc-art text{{font-size:{fs}px;white-space:pre}}
.foot-k{{font-size:10.5px;font-weight:700;fill:{AMBER_CORE}}}
.foot-v{{font-size:10.5px;fill:{AMBER_BRIGHT}}}
.foot-d{{font-size:9.5px;fill:{AMBER_DIM}}}
.r{{opacity:0.2;transform:translateY(3px);animation:in .45s cubic-bezier(.16,1,.3,1) forwards}}
.led{{animation:led-pulse 2.2s ease-in-out infinite}}
@keyframes in{{to{{opacity:1;transform:none}}}}
@keyframes led-pulse{{0%,100%{{opacity:1}}50%{{opacity:0.42}}}}
@media (prefers-reduced-motion:reduce){{.r,.led{{animation:none;opacity:1;transform:none}}}}
</style>
{_crt_defs(prefix, w, h)}
{chrome_base}
<g clip-path="url(#{prefix}-scr)">
  <g class="asc-art" xml:space="preserve">
    {chr(10).join(groups)}
  </g>
  <line x1="22" y1="322" x2="{w - 22}" y2="322" stroke="{PANEL_DIVIDER}" stroke-width="1"/>
  <text x="24" y="337" class="foot-k">&gt; album: <tspan class="foot-v">Currents</tspan></text>
  <text x="{w - 24}" y="337" text-anchor="end" class="foot-d">[ASCII]</text>
</g>
{chrome_overlay}
</svg>'''

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    return svg


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "media/images/currents-cover.jpg"
    out = sys.argv[2] if len(sys.argv) > 2 else "media/svg/currents_crt.svg"
    render_currents_crt(src, out)
    print(f"Generated {out}")
