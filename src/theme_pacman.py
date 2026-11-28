"""Applies the GitHub Dark Blue CRT theme to Pac-Man contribution graph SVGs."""
from __future__ import annotations

from pathlib import Path
import re
import sys

DARK_BLUE_MAP: dict[str, str] = {
    "#0e4429": "#0c2d6b",
    "#006d32": "#1f6feb",
    "#26a641": "#58a6ff",
    "#39d353": "#79c0ff",
    "#8b949e": "#7da5d8",
    "#ffffff": "#388bfd",
}

LIGHT_BLUE_MAP: dict[str, str] = {
    "#9be9a8": "#b6e3ff",
    "#40c463": "#54aeff",
    "#30a14e": "#0969da",
    "#216e39": "#0a3069",
}

FONT_STACK = "'Cascadia Mono','JetBrains Mono','Fira Code',Consolas,'SFMono-Regular',ui-monospace,monospace"


def _remap_colors(svg: str, color_map: dict[str, str]) -> str:
    pattern = re.compile("|".join(re.escape(k) for k in color_map), re.IGNORECASE)
    return pattern.sub(lambda m: color_map[m.group(0).lower()], svg)


def _clean_inner_body(inner: str) -> str:
    """Strip legacy wrappers and redundant 100% background rect before framing."""
    inner = re.sub(r"<style>\.pac-in\{.*?</style>", "", inner, count=1, flags=re.DOTALL)
    if inner.startswith('<g class="pac-in">') and inner.endswith("</g>"):
        inner = inner[len('<g class="pac-in">') : -len("</g>")]
    inner = re.sub(
        r'<rect\s+width="100%"\s+height="100%"\s+fill="#0d1117"\s*/?>',
        "",
        inner,
        count=1,
        flags=re.IGNORECASE,
    )
    return inner


def theme_pacman_svg(svg_text: str, dark: bool = True) -> str:
    """Recolor contribution tiles & walls to GitHub Blue inside a unified 860px CRT card."""
    color_map = DARK_BLUE_MAP if dark else LIGHT_BLUE_MAP
    recolored = _remap_colors(svg_text, color_map)

    if not dark:
        if "pac-in" not in recolored:
            css = (
                "<style>.pac-in{opacity:0;transform:translateY(8px);"
                "animation:pacIn .6s cubic-bezier(.16,1,.3,1) .15s forwards}"
                "@keyframes pacIn{to{opacity:1;transform:none}}"
                "@media(prefers-reduced-motion:reduce){.pac-in{animation:none;opacity:1;transform:none}}</style>"
                '<g class="pac-in">'
            )
            recolored = recolored.replace(">", ">" + css, 1)
            end_idx = recolored.rfind("</svg>")
            if end_idx != -1:
                recolored = recolored[:end_idx] + "</g>" + recolored[end_idx:]
        return recolored

    if 'data-crt-blue="2"' in recolored:
        return recolored

    open_end = recolored.find(">")
    close_start = recolored.rfind("</svg>")
    if open_end == -1 or close_start == -1:
        return recolored

    open_tag = recolored[: open_end + 1]
    w_match = re.search(r'width="(\d+(?:\.\d+)?)"', open_tag)
    h_match = re.search(r'height="(\d+(?:\.\d+)?)"', open_tag)
    inner_w = float(w_match.group(1)) if w_match else 1166.0
    inner_h = float(h_match.group(1)) if h_match else 184.0

    inner_body = _clean_inner_body(recolored[open_end + 1 : close_start])

    # Match exact 860px coordinate system of crt_bios.svg & btop_telemetry.svg
    w, h = 860, 196
    inner_scr_w, inner_scr_h = w - 24, h - 24
    target_w = 804.0
    scale = target_w / max(1.0, inner_w)
    scaled_h = inner_h * scale
    tx = (w - target_w) / 2.0
    ty = 42.0 + (142.0 - scaled_h) / 2.0

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" data-crt-blue="2">
<style>
.pac-bar-t{{font-family:{FONT_STACK};font-size:11.5px;font-weight:700;fill:#58a6ff;letter-spacing:0.4px}}
.pac-bar-r{{font-family:{FONT_STACK};font-size:10.5px;fill:#7da5d8;letter-spacing:0.4px}}
.pac-led{{animation:pacLed 2.2s ease-in-out infinite}}
.pac-in{{opacity:0;transform:translateY(6px);animation:pacIn .55s cubic-bezier(.16,1,.3,1) .12s forwards}}
@keyframes pacLed{{0%,100%{{opacity:1}}50%{{opacity:0.42}}}}
@keyframes pacIn{{to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.pac-led,.pac-in{{animation:none;opacity:1;transform:none}}}}
</style>
<defs>
  <pattern id="pac-scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000000" fill-opacity="0.20"/></pattern>
  <radialGradient id="pac-vig" cx="50%" cy="48%" r="65%">
    <stop offset="0%" stop-color="#58a6ff" stop-opacity="0.06"/>
    <stop offset="72%" stop-color="#0d1117" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000000" stop-opacity="0.38"/>
  </radialGradient>
  <filter id="pac-glow" x="-15%" y="-15%" width="130%" height="130%">
    <feGaussianBlur stdDeviation="1.4" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="pac-scr"><rect x="12" y="12" width="{inner_scr_w}" height="{inner_scr_h}" rx="9"/></clipPath>
</defs>
<rect width="{w}" height="{h}" rx="14" fill="#090d13" stroke="#21262d" stroke-width="1.5"/>
<rect x="12" y="12" width="{inner_scr_w}" height="{inner_scr_h}" rx="9" fill="#0d1117" stroke="#30363d" stroke-width="1.2"/>
<rect x="12" y="12" width="{inner_scr_w}" height="30" rx="9" fill="#161b22"/>
<rect x="12" y="30" width="{inner_scr_w}" height="12" fill="#161b22"/>
<line x1="12" y1="42" x2="{w - 12}" y2="42" stroke="#30363d" stroke-width="1"/>
<circle cx="28" cy="27" r="4" fill="#58a6ff" class="pac-led" filter="url(#pac-glow)"/>
<text x="40" y="31" class="pac-bar-t">CMD // GitHub Contributions (Pac-Man)</text>
<text x="{w - 26}" y="31" text-anchor="end" class="pac-bar-r">LIVE GRAPH</text>
<g clip-path="url(#pac-scr)">
  <g transform="translate({tx:.2f},{ty:.2f}) scale({scale:.5f})">
    <g class="pac-in">{inner_body}</g>
  </g>
  <rect x="12" y="42" width="{inner_scr_w}" height="{inner_scr_h - 30}" fill="url(#pac-vig)" pointer-events="none"/>
  <rect x="12" y="42" width="{inner_scr_w}" height="{inner_scr_h - 30}" fill="url(#pac-scan)" pointer-events="none"/>
</g>
</svg>'''


def process_directory(dist_dir: str | Path = "dist") -> list[Path]:
    updated: list[Path] = []
    for path in sorted(Path(dist_dir).glob("*.svg")):
        is_dark = "dark" in path.name.lower()
        themed = theme_pacman_svg(path.read_text(encoding="utf-8"), dark=is_dark)
        path.write_text(themed, encoding="utf-8")
        updated.append(path)
    return updated


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "dist"
    files = process_directory(target)
    print(f"Themed {len(files)} Pac-Man SVGs in {target}: {[f.name for f in files]}")
