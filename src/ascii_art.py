"""Local generator: image -> animated ASCII SVG. Needs pillow and numpy."""
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps

SRC = sys.argv[1] if len(sys.argv) > 1 else "media/images/currents-cover.jpg"
OUT = sys.argv[2] if len(sys.argv) > 2 else "media/svg/currents.svg"

COLS, CW, LH, FS = 114, 4, 6, 6.4
RAMP = " .:-=+*#%@"

im = Image.open(SRC).convert("L")
rows = round(COLS * im.height / im.width * (CW / LH))

im_sharp = im.filter(ImageFilter.UnsharpMask(radius=4, percent=180, threshold=2))
im_eq = ImageOps.autocontrast(im_sharp, cutoff=2)
g = np.asarray(im_eq.resize((COLS, rows), Image.Resampling.LANCZOS), dtype=float) / 255.0

blur = np.asarray(im_eq.filter(ImageFilter.GaussianBlur(radius=32)).resize((COLS, rows), Image.Resampling.BILINEAR), dtype=float) / 255.0
g_mix = np.clip(g * 0.55 + (g - blur + 0.5) * 0.45, 0, 1)

lo, hi = np.percentile(g_mix, [5, 95])
lum = np.clip((g_mix - lo) / max(hi - lo, 1e-5), 0, 1)
lum = np.clip((lum - 0.45) * 1.65 + 0.5, 0, 1)

edges = np.asarray(im_sharp.filter(ImageFilter.FIND_EDGES).resize((COLS, rows), Image.Resampling.LANCZOS), dtype=float) / 255.0
edges = np.clip((edges - 0.12) * 2.0, 0, 1)
v = np.clip(lum - edges * 0.55, 0, 1)

W, H = COLS * CW + 20, rows * LH + 20
groups = []
for g_idx in range(0, rows, 2):
    pair = []
    for r in range(g_idx, min(g_idx + 2, rows)):
        row = "".join(RAMP[int(x * (len(RAMP) - 1))] for x in v[r])
        start, body = len(row) - len(row.lstrip()), row.strip()
        if not body:
            continue
        t = body.replace("&", "&amp;").replace("<", "&lt;")
        pair.append(f'<text x="{10 + start * CW}" y="{10 + (r + 1) * LH}" textLength="{len(body) * CW}">{t}</text>')
    if pair:
        delay = (g_idx // 2) * 0.025
        groups.append(f'<g class="r" style="animation-delay:{delay:.3f}s">{"".join(pair)}</g>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>
text{{font:{FS}px ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace;fill:#8b949e;white-space:pre}}
.r{{opacity:0;transform:translateY(4px);animation:in .5s cubic-bezier(.16,1,.3,1) forwards}}
@keyframes in{{to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.r{{animation:none;opacity:1;transform:none}}}}
</style>
<rect width="{W}" height="{H}" rx="10" fill="#0d1117" stroke="#30363d"/>
<g xml:space="preserve">
{chr(10).join(groups)}
</g>
</svg>'''

with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)
print(f"Generated {OUT}: {W}x{H}, {rows} rows, {COLS} cols")
