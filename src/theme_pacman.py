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


def _strip_existing_pac_in(inner: str) -> str:
    """Remove legacy inline .pac-in style/group wrapper if already present."""
    inner = re.sub(r"<style>\.pac-in\{.*?</style>", "", inner, count=1, flags=re.DOTALL)
    if inner.startswith('<g class="pac-in">') and inner.endswith("</g>"):
        inner = inner[len('<g class="pac-in">') : -len("</g>")]
    return inner


def theme_pacman_svg(svg_text: str, dark: bool = True) -> str:
    """Recolor contribution tiles to GitHub Blue and wrap dark graph in matching CRT frame."""
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

    if 'data-crt-blue="1"' in recolored:
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

    inner_body = _strip_existing_pac_in(recolored[open_end + 1 : close_start])

    pad_x = 20.0
    header_h = 42.0
    pad_top = 14.0
    pad_bottom = 18.0
    outer_w = int(round(inner_w + pad_x * 2))
    outer_h = int(round(inner_h + pad_top + header_h + pad_bottom + 8))
    scr_w = outer_w - 28
    scr_h = outer_h - 28

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{outer_w}" height="{outer_h}" viewBox="0 0 {outer_w} {outer_h}" data-crt-blue="1">
<style>
.pac-bar-t{{font-family:{FONT_STACK};font-size:16px;font-weight:700;fill:#58a6ff;letter-spacing:0.5px}}
.pac-bar-r{{font-family:{FONT_STACK};font-size:14.5px;fill:#7da5d8;letter-spacing:0.4px}}
.pac-led{{animation:pacLed 2.2s ease-in-out infinite}}
.pac-in{{opacity:0;transform:translateY(8px);animation:pacIn .6s cubic-bezier(.16,1,.3,1) .15s forwards}}
@keyframes pacLed{{0%,100%{{opacity:1}}50%{{opacity:0.42}}}}
@keyframes pacIn{{to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.pac-led,.pac-in{{animation:none;opacity:1;transform:none}}}}
</style>
<defs>
  <pattern id="pac-scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000000" fill-opacity="0.16"/></pattern>
  <clipPath id="pac-scr"><rect x="14" y="14" width="{scr_w}" height="{scr_h}" rx="12"/></clipPath>
</defs>
<rect width="{outer_w}" height="{outer_h}" rx="18" fill="#090d13" stroke="#21262d" stroke-width="2"/>
<rect x="14" y="14" width="{scr_w}" height="{scr_h}" rx="12" fill="#0d1117" stroke="#30363d" stroke-width="1.5"/>
<rect x="14" y="14" width="{scr_w}" height="{header_h:.0f}" rx="12" fill="#161b22"/>
<rect x="14" y="42" width="{scr_w}" height="14" fill="#161b22"/>
<line x1="14" y1="56" x2="{outer_w - 14}" y2="56" stroke="#30363d" stroke-width="1.4"/>
<circle cx="38" cy="35" r="5.5" fill="#58a6ff" class="pac-led"/>
<text x="56" y="40.5" class="pac-bar-t">CMD // GitHub Contributions (Pac-Man)</text>
<text x="{outer_w - 34}" y="40.5" text-anchor="end" class="pac-bar-r">GITHUB BLUE</text>
<g clip-path="url(#pac-scr)">
  <g class="pac-in" transform="translate({pad_x:.0f},{pad_top + header_h + 4:.0f})">{inner_body}</g>
  <rect x="14" y="56" width="{scr_w}" height="{scr_h - 42}" fill="url(#pac-scan)" pointer-events="none"/>
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
