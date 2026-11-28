"""Applies the GitHub Dark Blue CRT theme to Pac-Man contribution graph SVGs."""
from __future__ import annotations

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

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
_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE | re.DOTALL)
_G_TAG_RE = re.compile(r"<(/?)g\b([^>]*)>", re.IGNORECASE)
_BG_RECT_RE = re.compile(r"<rect\b[^>]*>", re.IGNORECASE)


def _remap_colors(svg: str, color_map: dict[str, str]) -> str:
    keys = "|".join(re.escape(k) for k in color_map)
    pattern = re.compile(rf"(?:{keys})(?![0-9a-fA-F])", re.IGNORECASE)
    return pattern.sub(lambda m: color_map[m.group(0).lower()], svg)


def _unwrap_single_pac_in(inner: str) -> str:
    """Unwrap an outer <g class="pac-in">...</g> only if it spans the whole body."""
    stripped = inner.strip()
    open_prefix = '<g class="pac-in">'
    if not stripped.startswith(open_prefix) or not stripped.endswith("</g>"):
        return inner

    depth = 0
    for idx, match in enumerate(_G_TAG_RE.finditer(stripped)):
        is_close = bool(match.group(1))
        attrs = match.group(2)
        if not is_close:
            if attrs.rstrip().endswith("/"):
                continue
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                if match.end() == len(stripped):
                    return stripped[len(open_prefix) : match.start()]
                return inner
        if idx > 10000:
            break
    return inner


def _strip_dark_bg_rect(inner: str) -> str:
    """Remove the first full-bleed #0d1117 background <rect> regardless of attribute order."""
    for match in _BG_RECT_RE.finditer(inner):
        tag = match.group(0)
        if (
            re.search(r'\bwidth=["\']100%["\']', tag, re.IGNORECASE)
            and re.search(r'\bheight=["\']100%["\']', tag, re.IGNORECASE)
            and re.search(r'\bfill=["\']#0d1117["\']', tag, re.IGNORECASE)
        ):
            end = match.end()
            if not tag.rstrip().endswith("/>"):
                close_m = re.match(r"\s*</rect>", inner[end:], re.IGNORECASE)
                if close_m:
                    end += close_m.end()
            return inner[: match.start()] + inner[end:]
    return inner


def _clean_inner_body(inner: str) -> str:
    """Strip legacy wrappers and redundant 100% background rect before framing."""
    inner = re.sub(r"<style[^>]*>\.pac-in\{.*?</style>", "", inner, count=1, flags=re.DOTALL | re.IGNORECASE)
    inner = _unwrap_single_pac_in(inner)
    inner = _strip_dark_bg_rect(inner)
    return inner


def _extract_svg_dimensions(open_tag: str) -> tuple[float, float]:
    w_match = re.search(r'\bwidth=["\'](\d+(?:\.\d+)?)(?:px)?["\']', open_tag, re.IGNORECASE)
    h_match = re.search(r'\bheight=["\'](\d+(?:\.\d+)?)(?:px)?["\']', open_tag, re.IGNORECASE)
    if w_match and h_match:
        w_val, h_val = float(w_match.group(1)), float(h_match.group(1))
        if w_val > 0 and h_val > 0:
            return w_val, h_val

    vb_match = re.search(
        r'\bviewBox=["\']\s*[-\d.]+\s+[-\d.]+\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*["\']',
        open_tag,
        re.IGNORECASE,
    )
    if vb_match:
        vb_w, vb_h = float(vb_match.group(1)), float(vb_match.group(2))
        if vb_w > 0 and vb_h > 0:
            return vb_w, vb_h

    return 1166.0, 184.0


def theme_pacman_svg(svg_text: str, dark: bool = True) -> str:
    """Recolor contribution tiles & walls to GitHub Blue inside a unified 860px CRT card."""
    if dark and 'data-crt-blue="2"' in svg_text:
        return svg_text

    color_map = DARK_BLUE_MAP if dark else LIGHT_BLUE_MAP
    recolored = _remap_colors(svg_text, color_map)

    open_match = _SVG_OPEN_RE.search(recolored)
    close_start = recolored.rfind("</svg>")
    if open_match is None or close_start == -1 or close_start <= open_match.end():
        return recolored

    if not dark:
        if "pac-in" not in recolored:
            css = (
                "<style>.pac-in{opacity:0;transform:translateY(8px);"
                "animation:pacIn .6s cubic-bezier(.16,1,.3,1) .15s forwards}"
                "@keyframes pacIn{to{opacity:1;transform:none}}"
                "@media(prefers-reduced-motion:reduce){.pac-in{animation:none;opacity:1;transform:none}}</style>"
                '<g class="pac-in">'
            )
            recolored = (
                recolored[: open_match.end()]
                + css
                + recolored[open_match.end() : close_start]
                + "</g>"
                + recolored[close_start:]
            )
        return recolored

    open_tag = open_match.group(0)
    inner_w, inner_h = _extract_svg_dimensions(open_tag)
    inner_body = _clean_inner_body(recolored[open_match.end() : close_start])

    # Match exact 860px coordinate system of crt_bios.svg & btop_telemetry.svg
    w, h = 860, 196
    inner_scr_w, inner_scr_h = w - 24, h - 24
    max_content_w = 804.0
    max_content_h = 132.0
    scale = min(max_content_w / max(1.0, inner_w), max_content_h / max(1.0, inner_h))
    scaled_w = inner_w * scale
    scaled_h = inner_h * scale
    tx = (w - scaled_w) / 2.0
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
<rect x="12" y="12" width="{inner_scr_w}" height="{inner_scr_h}" rx="9" fill="#0d1117"/>
<g clip-path="url(#pac-scr)">
  <rect x="12" y="12" width="{inner_scr_w}" height="30" fill="#161b22"/>
  <line x1="12" y1="42" x2="{w - 12}" y2="42" stroke="#30363d" stroke-width="1"/>
</g>
<rect x="12" y="12" width="{inner_scr_w}" height="{inner_scr_h}" rx="9" fill="none" stroke="#30363d" stroke-width="1.2"/>
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
    target_dir = Path(dist_dir)
    if not target_dir.is_dir():
        raise FileNotFoundError(f"Pac-Man output directory not found: {target_dir}")

    svg_files = sorted(target_dir.glob("*.svg"))
    if not svg_files:
        raise RuntimeError(f"No SVG files found in {target_dir}")

    updated: list[Path] = []
    for path in svg_files:
        is_dark = "dark" in path.name.lower()
        themed = theme_pacman_svg(path.read_text(encoding="utf-8"), dark=is_dark)
        root = ET.fromstring(themed)
        if not root.tag.endswith("svg"):
            raise ValueError(f"Themed output for {path.name} is not an SVG root element")
        path.write_text(themed, encoding="utf-8")
        updated.append(path)
    return updated


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "dist"
    files = process_directory(target)
    print(f"Themed {len(files)} Pac-Man SVGs in {target}: {[f.name for f in files]}")
