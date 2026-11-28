"""GitHub Blue CRT SVG rendering engine for BIOS/CMD and GitHub stats."""
from __future__ import annotations

from datetime import datetime, timezone
import html
import math
import re

from github_stats import ProfileTelemetry

# GitHub Dark UI Blue Palette (#0d1117 canvas + #58a6ff / #79c0ff GitHub blue)
CHASSIS_BG = "#090d13"
CHASSIS_STROKE = "#21262d"
SCREEN_BG = "#0d1117"
SCREEN_BAR = "#161b22"
SCREEN_STROKE = "#30363d"
PANEL_BORDER = "#26364d"
PANEL_DIVIDER = "#21262d"

ACCENT_BRIGHT = "#79c0ff"
ACCENT_CORE = "#58a6ff"
ACCENT_SOFT = "#e6edf3"
ACCENT_MID = "#7da5d8"
ACCENT_DIM = "#388bfd"
ACCENT_DARK = "#162438"

FONT_STACK = "'Cascadia Mono','JetBrains Mono','Fira Code',Consolas,'SFMono-Regular',ui-monospace,monospace"
_XML_ILLEGAL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffe\uffff]")


def _strip_xml_illegal(text: str) -> str:
    return _XML_ILLEGAL_RE.sub("", str(text))


def esc(text: str) -> str:
    return html.escape(_strip_xml_illegal(text), quote=True)


def clamp_text(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    clean = " ".join(_strip_xml_illegal(text).split())
    if len(clean) <= max_len:
        return clean
    if max_len <= 3:
        return clean[:max_len]
    return clean[: max_len - 3].rstrip() + "..."


def _safe_nonneg_int(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value)) if math.isfinite(value) else 0
    try:
        return max(0, int(str(value).strip()))
    except ValueError:
        return 0


def fmt_bytes(byte_count: int) -> str:
    val = _safe_nonneg_int(byte_count)
    if val == 0:
        return "0.0 KB"
    if val >= 1_073_741_824:
        return f"{val / 1_073_741_824:.1f} GB"
    if val >= 1_048_576:
        return f"{val / 1_048_576:.1f} MB"
    return f"{max(0.1, val / 1024):.1f} KB"


def fmt_repo_kb(size_kb: int) -> str:
    val = _safe_nonneg_int(size_kb)
    if val >= 1_048_576:
        return f"{val / 1_048_576:.1f} GB"
    if val >= 1024:
        return f"{val / 1024:.1f} MB"
    return f"{val} KB"


def fmt_uptime(days: int) -> str:
    val = _safe_nonneg_int(days)
    if val >= 365:
        years, rem = divmod(val, 365)
        return f"{years}y {rem}d"
    return f"{val}d"


def _crt_defs(prefix: str, width: int, height: int, extra: str = "") -> str:
    return (
        "<defs>"
        f'<pattern id="{prefix}-scan" width="4" height="3" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="1" fill="#000000" fill-opacity="0.20"/>'
        "</pattern>"
        f'<radialGradient id="{prefix}-vig" cx="50%" cy="48%" r="65%">'
        f'<stop offset="0%" stop-color="{ACCENT_CORE}" stop-opacity="0.06"/>'
        '<stop offset="72%" stop-color="#0d1117" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#000000" stop-opacity="0.40"/>'
        "</radialGradient>"
        f'<filter id="{prefix}-glow" x="-15%" y="-15%" width="130%" height="130%">'
        '<feGaussianBlur stdDeviation="1.4" result="blur"/>'
        "<feMerge>"
        '<feMergeNode in="blur"/>'
        '<feMergeNode in="SourceGraphic"/>'
        "</feMerge>"
        "</filter>"
        f'<clipPath id="{prefix}-scr">'
        f'<rect x="12" y="12" width="{width - 24}" height="{height - 24}" rx="9"/>'
        "</clipPath>"
        f"{extra}"
        "</defs>"
    )


def _crt_chrome(prefix: str, width: int, height: int, left_title: str, right_status: str) -> tuple[str, str]:
    inner_w = width - 24
    inner_h = height - 24
    base = (
        f'<rect width="{width}" height="{height}" rx="14" fill="{CHASSIS_BG}" stroke="{CHASSIS_STROKE}" stroke-width="1.5"/>'
        f'<rect x="12" y="12" width="{inner_w}" height="{inner_h}" rx="9" fill="{SCREEN_BG}"/>'
        f'<g clip-path="url(#{prefix}-scr)">'
        f'<rect x="12" y="12" width="{inner_w}" height="30" fill="{SCREEN_BAR}"/>'
        f'<line x1="12" y1="42" x2="{width - 12}" y2="42" stroke="{SCREEN_STROKE}" stroke-width="1"/>'
        "</g>"
        f'<rect x="12" y="12" width="{inner_w}" height="{inner_h}" rx="9" fill="none" stroke="{SCREEN_STROKE}" stroke-width="1.2"/>'
        f'<circle cx="28" cy="27" r="4" fill="{ACCENT_CORE}" class="led" filter="url(#{prefix}-glow)"/>'
        f'<text x="40" y="31" class="bar-t">{esc(left_title)}</text>'
        f'<text x="{width - 26}" y="31" text-anchor="end" class="bar-r">{esc(right_status)}</text>'
    )
    overlay = (
        f'<g clip-path="url(#{prefix}-scr)">'
        f'<rect x="12" y="42" width="{inner_w}" height="{inner_h - 30}" fill="url(#{prefix}-vig)"/>'
        f'<rect x="12" y="42" width="{inner_w}" height="{inner_h - 30}" fill="url(#{prefix}-scan)"/>'
        "</g>"
    )
    return base, overlay


def _crt_ascii_art(x: int, y: int) -> str:
    """Retro CRT Monitor + coding mascot ASCII art in GitHub Blue."""
    lines: list[tuple[str, str]] = [
        ("     _______________________     ", ACCENT_MID),
        ("    /                       \\    ", ACCENT_MID),
        ("   /  +-------------------+  \\   ", ACCENT_MID),
        ("  |   | C:\\> code_        |   |  ", ACCENT_BRIGHT),
        ("  |   |                   |   |  ", ACCENT_CORE),
        ("  |   |     {  /\\_/\\  }   |   |  ", ACCENT_BRIGHT),
        ("  |   |     (  >_<  )     |   |  ", ACCENT_BRIGHT),
        ("  |   |     /> </> <\\     |   |  ", ACCENT_CORE),
        ("  |   +-------------------+   |  ", ACCENT_MID),
        ("  |   [===]         (*) PWR   |  ", ACCENT_DIM),
        ("   \\_________________________/   ", ACCENT_MID),
        ("      ___|_____________|___      ", ACCENT_DIM),
        ("   __/_____________________\\__   ", ACCENT_DIM),
        ("  /  [][][][][][][][][][][]   \\  ", ACCENT_MID),
        (" /_____________________________\\ ", ACCENT_DIM),
    ]
    out = ['<g xml:space="preserve">']
    for idx, (line, color) in enumerate(lines):
        out.append(
            f'<text x="{x}" y="{y + idx * 16}" class="asc" fill="{color}">{esc(line)}</text>'
        )
    out.append("</g>")
    return "".join(out)


def _resolve_year(synced_at: str) -> str:
    match = re.match(r"^(\d{4})\b", str(synced_at).strip())
    return match.group(1) if match else str(datetime.now(timezone.utc).year)


def render_bios_terminal(t: ProfileTelemetry) -> str:
    """Render GitHub Blue CRT CMD profile terminal SVG directly with no loading gimmick."""
    w, h = 860, 420
    prefix = "bios"
    top_project = next((r for r in t.repos if not r.is_profile_repo), t.repos[0] if t.repos else None)
    safe_user = clamp_text(t.username, 28)
    safe_name = clamp_text(t.display_name, 26)
    year = _resolve_year(t.synced_at)

    lang_list = " · ".join(name for name, _ in t.languages[:4]) or "Learning Code"
    stack_list = " · ".join(t.stacks[:4]) or lang_list
    safe_public_repos = _safe_nonneg_int(t.public_repos)
    projects_summary = (
        f"{safe_public_repos:02d} public repositories (e.g. {clamp_text(top_project.name, 16)})"
        if top_project is not None
        else f"{safe_public_repos:02d} public repositories"
    )

    info_rows = [
        ("NAME", clamp_text(f"{t.display_name} (@{t.username})", 44)),
        ("ROLE", "Beginner Programmer · Coding & Learning"),
        ("SKILLS", clamp_text(stack_list, 44)),
        ("LANGUAGES", clamp_text(lang_list, 44)),
        ("TOOLS", "Windows · VS Code · GitHub"),
        ("PROJECTS", projects_summary),
        ("SINCE", f"{t.created_at} ({fmt_uptime(t.uptime_days)} on GitHub)"),
    ]

    info_rows_svg = []
    info_css = []
    for idx, (key, val) in enumerate(info_rows):
        y_pos = 186 + idx * 23
        delay = 0.25 + idx * 0.09
        info_css.append(
            f".nl{idx}{{opacity:0;transform:translateX(-10px);"
            f"animation:row-in 0.50s cubic-bezier(.16,1,.3,1) {delay:.2f}s forwards}}"
        )
        info_rows_svg.append(
            f'<g class="nl{idx}">'
            f'<text x="382" y="{y_pos}" class="nk">{esc(key)}</text>'
            f'<text x="468" y="{y_pos}" class="nd">:</text>'
            f'<text x="482" y="{y_pos}" class="nv">{esc(val)}</text>'
            "</g>"
        )

    prompt_text = f"C:\\Users\\{safe_user}>"
    prompt_w = round(len(prompt_text) * 7.8)
    cmd_x = 32 + prompt_w + 8
    cmd_text = "whoami"
    cmd_w = round(len(cmd_text) * 7.8)

    chrome_base, chrome_overlay = _crt_chrome(
        prefix,
        w,
        h,
        f"CMD.EXE // {safe_user}",
        "GITHUB CONSOLE",
    )

    reduced_rows = ",".join(f".nl{i}" for i in range(len(info_rows)))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
text{{font-family:{FONT_STACK}}}
.bar-t{{font-size:11.5px;font-weight:700;fill:{ACCENT_CORE};letter-spacing:0.4px}}
.bar-r{{font-size:10.5px;fill:{ACCENT_MID};letter-spacing:0.4px}}
.tty-h{{font-size:12px;fill:{ACCENT_MID}}}
.prm{{font-size:13px;font-weight:700;fill:{ACCENT_CORE}}}
.cmd{{font-size:13px;fill:{ACCENT_BRIGHT}}}
.asc{{font-size:11.5px;white-space:pre}}
.nh{{font-size:14px;font-weight:700;fill:{ACCENT_BRIGHT}}}
.nk{{font-size:12.5px;font-weight:700;fill:{ACCENT_CORE}}}
.nd{{font-size:12.5px;fill:{ACCENT_DIM}}}
.nv{{font-size:12.5px;fill:{ACCENT_SOFT}}}
.note{{font-size:12px;fill:{ACCENT_MID}}}
.hdr-in{{opacity:0;transform:translateY(6px);animation:card-in 0.50s cubic-bezier(.16,1,.3,1) 0.05s forwards}}
.asc-in{{opacity:0;transform:translateY(8px);animation:card-in 0.60s cubic-bezier(.16,1,.3,1) 0.15s forwards}}
.asc-glow{{animation:crt-breathe 3.4s ease-in-out 0.8s infinite}}
.note-in{{opacity:0;transform:translateX(-8px);animation:row-in 0.50s cubic-bezier(.16,1,.3,1) 0.92s forwards}}
.led{{animation:led-pulse 2.2s ease-in-out infinite}}
.cur-blink{{animation:cur-flash 1.05s steps(1,end) infinite}}
{"".join(info_css)}
@keyframes card-in{{to{{opacity:1;transform:none}}}}
@keyframes row-in{{to{{opacity:1;transform:none}}}}
@keyframes crt-breathe{{0%,100%{{opacity:1}}50%{{opacity:0.84}}}}
@keyframes led-pulse{{0%,100%{{opacity:1}}50%{{opacity:0.42}}}}
@keyframes cur-flash{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{.hdr-in,.asc-in,.asc-glow,.note-in,.led,.cur-blink,{reduced_rows}{{animation:none;opacity:1;transform:none}}}}
</style>
{_crt_defs(prefix, w, h)}
{chrome_base}
<g clip-path="url(#{prefix}-scr)">
  <g class="hdr-in">
    <text x="32" y="74" class="tty-h">Microsoft Windows [GitHub Console] // Developer Profile</text>
    <text x="32" y="92" class="tty-h">(c) {year} {esc(safe_name)}. Welcome to my GitHub workspace.</text>
    <text x="32" y="118" textLength="{prompt_w}" class="prm">{esc(prompt_text)}</text>
    <text x="{cmd_x}" y="118" textLength="{cmd_w}" class="cmd" filter="url(#{prefix}-glow)">{esc(cmd_text)}</text>
    <line x1="32" y1="132" x2="828" y2="132" stroke="{PANEL_DIVIDER}" stroke-width="1"/>
  </g>

  <g class="asc-in"><g class="asc-glow">{_crt_ascii_art(28, 158)}</g></g>

  <g class="hdr-in">
    <text x="382" y="158" class="nh" filter="url(#{prefix}-glow)">{esc(safe_name)} <tspan class="bar-r">(@{esc(safe_user)})</tspan></text>
    <line x1="382" y1="166" x2="820" y2="166" stroke="{PANEL_BORDER}" stroke-width="1"/>
  </g>
  {"".join(info_rows_svg)}
  <text x="382" y="362" class="note note-in">&gt; Exploring code, building web apps, and learning daily.</text>

  <text x="32" y="394" textLength="{prompt_w}" class="prm">{esc(prompt_text)}</text>
  <rect x="{cmd_x}" y="382" width="8" height="14" rx="1" fill="{ACCENT_BRIGHT}" class="cur-blink"/>
</g>
{chrome_overlay}
</svg>'''


def _panel_box(x: int, y: int, w: int, h: int, title: str, right_hint: str = "") -> str:
    clean_title = _strip_xml_illegal(title)
    clean_hint = _strip_xml_illegal(right_hint)
    title_w = min(w - 24.0, len(clean_title) * 7.2 + 16.0)
    if clean_hint:
        max_hint_w = max(24.0, w - title_w - 36.0)
        hint_w = min(max_hint_w, len(clean_hint) * 7.0 + 14.0)
        hint_x = x + w - hint_w - 10.0
        right_svg = (
            f'<rect x="{hint_x:.1f}" y="{y - 8}" width="{hint_w:.1f}" height="16" fill="{SCREEN_BG}"/>'
            f'<text x="{x + w - 16}" y="{y + 3}" text-anchor="end" class="p-hint">{esc(clean_hint)}</text>'
        )
    else:
        right_svg = ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#111722" stroke="{PANEL_BORDER}" stroke-width="1.2"/>'
        f'<rect x="{x + 12}" y="{y - 8}" width="{title_w:.1f}" height="16" fill="{SCREEN_BG}"/>'
        f'<text x="{x + 19}" y="{y + 3}" class="p-title">{esc(clean_title)}</text>'
        f"{right_svg}"
    )


def _segmented_bar(x: int, y: int, pct: float, segments: int = 18) -> str:
    safe_segments = max(1, int(segments))
    safe_pct = max(0.0, min(100.0, float(pct) if math.isfinite(pct) else 0.0))
    filled = min(safe_segments, max(1 if safe_pct > 0 else 0, round((safe_pct / 100.0) * safe_segments)))
    seg_w, gap = 7, 2
    rects = []
    for idx in range(safe_segments):
        sx = x + idx * (seg_w + gap)
        if idx < filled:
            fill = ACCENT_BRIGHT if idx >= safe_segments - 4 else ACCENT_CORE
            opacity = "0.95"
        else:
            fill = ACCENT_DARK
            opacity = "0.85"
        rects.append(f'<rect x="{sx}" y="{y}" width="{seg_w}" height="10" rx="1.2" fill="{fill}" opacity="{opacity}"/>')
    return "".join(rects)


def render_btop_telemetry(t: ProfileTelemetry) -> str:
    """Render simplified CMD-style GitHub Blue stats SVG."""
    w, h = 860, 284
    prefix = "btop"
    safe_user = clamp_text(t.username, 28)
    chrome_base, chrome_overlay = _crt_chrome(
        prefix,
        w,
        h,
        f"CMD // GitHub Stats ({safe_user})",
        f"Updated {t.synced_at}",
    )

    lang_sum = sum(_safe_nonneg_int(b_val) for _, b_val in t.languages)
    effective_total = _safe_nonneg_int(t.total_bytes) or lang_sum
    p1 = _panel_box(22, 58, 424, 190, "TOP LANGUAGES & TOOLS", fmt_bytes(effective_total))
    total_b = max(1, effective_total)
    top_langs = t.languages[:4] if t.languages else [("Exploring", 0)]
    lang_rows = []
    for idx, (lang, b_val) in enumerate(top_langs):
        safe_b = _safe_nonneg_int(b_val)
        pct = min(100.0, (safe_b / total_b) * 100.0) if effective_total > 0 else 0.0
        ry = 86 + idx * 28
        delay = 0.08 + idx * 0.07
        lang_rows.append(
            f'<text x="36" y="{ry}" class="lbl">{esc(clamp_text(lang, 11))}</text>'
            f'<g transform="translate(134,{ry - 9})"><g class="bar-grow" style="animation-delay:{delay:.2f}s">'
            f'{_segmented_bar(0, 0, pct, segments=18)}</g></g>'
            f'<text x="352" y="{ry}" text-anchor="end" class="val">{pct:5.1f}%</text>'
            f'<text x="430" y="{ry}" text-anchor="end" class="dim">{esc(fmt_bytes(safe_b))}</text>'
        )

    tag_x = 36.0
    tag_y = 210
    module_tags = []
    for t_idx, mod in enumerate(t.stacks[:6]):
        mod_label = clamp_text(mod, 16)
        if not mod_label:
            continue
        tw = len(mod_label) * 6.8 + 14.0
        if tag_x + tw > 432:
            break
        delay = 0.16 + t_idx * 0.04
        module_tags.append(
            f'<g class="tag-pop" style="animation-delay:{delay:.2f}s">'
            f'<rect x="{tag_x:.1f}" y="{tag_y}" width="{tw:.1f}" height="20" rx="3" fill="#132238" stroke="{ACCENT_DIM}" stroke-width="0.9"/>'
            f'<text x="{tag_x + tw / 2:.1f}" y="{tag_y + 13.5:.1f}" text-anchor="middle" class="tag">{esc(mod_label)}</text>'
            "</g>"
        )
        tag_x += tw + 6.0

    p2 = _panel_box(458, 58, 380, 190, "GITHUB OVERVIEW", "LIVE")
    kv_pairs = [
        ("REPOS", f"{_safe_nonneg_int(t.public_repos):02d}", "CODE SIZE", fmt_bytes(effective_total)),
        ("STARS", f"{_safe_nonneg_int(t.total_stars):02d}", "FORKS", f"{_safe_nonneg_int(t.total_forks):02d}"),
        ("FOLLOWERS", f"{_safe_nonneg_int(t.followers):02d}", "ACTIVE", fmt_uptime(t.uptime_days)),
    ]
    kv_svg = []
    for r_i, (k1, v1, k2, v2) in enumerate(kv_pairs):
        ry = 86 + r_i * 23
        kv_svg.append(
            f'<text x="474" y="{ry}" class="dim">{esc(k1)}</text>'
            f'<text x="562" y="{ry}" class="val-hi">{esc(v1)}</text>'
            f'<text x="646" y="{ry}" class="dim">{esc(k2)}</text>'
            f'<text x="822" y="{ry}" text-anchor="end" class="val-hi">{esc(v2)}</text>'
        )

    raw_series = [_safe_nonneg_int(v) for v in (t.push_series or [])]
    if len(raw_series) >= 14:
        series = raw_series[-14:]
    else:
        series = [0] * (14 - len(raw_series)) + raw_series
    series_max = max(series)
    peak = max(1, series_max)
    spark_bars = []
    base_x = 476
    bar_w = 19
    gap = 6
    max_bar_h = 44
    for i, val in enumerate(series):
        bh = max(4, round((val / peak) * max_bar_h)) if val > 0 else 3
        bx = base_x + i * (bar_w + gap)
        fill = ACCENT_BRIGHT if val == series_max and val > 0 else (ACCENT_CORE if val > 0 else ACCENT_DARK)
        delay = 0.08 + i * 0.025
        spark_bars.append(
            f'<g transform="translate({bx},228)">'
            f'<rect class="pulse-bar" style="animation-delay:{delay:.3f}s" x="0" y="{-bh}" width="{bar_w}" height="{bh}" rx="1.5" fill="{fill}"/>'
            "</g>"
        )

    spark_svg = (
        f'<line x1="474" y1="150" x2="822" y2="150" stroke="{PANEL_DIVIDER}" stroke-width="1"/>'
        f'<text x="474" y="168" class="dim">ACTIVITY (14 DAYS)</text>'
        f'<text x="822" y="168" text-anchor="end" class="val">{max(0, t.recent_push_count)} updates · peak {series_max}/d</text>'
        f'<line x1="474" y1="196" x2="822" y2="196" stroke="{PANEL_DIVIDER}" stroke-dasharray="3 3" stroke-width="1"/>'
        f'{"".join(spark_bars)}'
    )

    footer = (
        '<text x="26" y="264" class="fkey">Tip: Open the Repositories tab to inspect projects and live demos.</text>'
        '<text x="834" y="264" text-anchor="end" class="dim">AUTO-SYNC // GITHUB ACTIONS</text>'
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
text{{font-family:{FONT_STACK}}}
.bar-t{{font-size:11.5px;font-weight:700;fill:{ACCENT_CORE};letter-spacing:0.4px}}
.bar-r{{font-size:10.5px;fill:{ACCENT_MID};letter-spacing:0.4px}}
.p-title{{font-size:11.5px;font-weight:700;fill:{ACCENT_BRIGHT}}}
.p-hint{{font-size:10.5px;font-weight:700;fill:{ACCENT_CORE};animation:live-pulse 2.4s ease-in-out infinite}}
.lbl{{font-size:12px;fill:{ACCENT_CORE};font-weight:600}}
.val{{font-size:12px;fill:{ACCENT_SOFT}}}
.val-hi{{font-size:12px;fill:{ACCENT_BRIGHT};font-weight:700}}
.dim{{font-size:11.5px;fill:{ACCENT_MID}}}
.tag{{font-size:10.5px;fill:{ACCENT_BRIGHT};font-weight:600}}
.fkey{{font-size:10.5px;fill:{ACCENT_CORE}}}
.led{{animation:led-pulse 2.2s ease-in-out infinite}}
.in{{opacity:0;transform:translateY(8px);animation:panel-in 0.55s cubic-bezier(.16,1,.3,1) 0.12s forwards}}
.bar-grow{{transform-origin:0 0;transform:scaleX(0);animation:bar-fill 0.65s cubic-bezier(.16,1,.3,1) both}}
.pulse-bar{{transform-origin:0 0;transform:scaleY(0);animation:bar-rise 0.50s cubic-bezier(.16,1,.3,1) both}}
.tag-pop{{opacity:0;transform:translateY(4px);animation:fade-up 0.40s ease both}}
@keyframes led-pulse{{0%,100%{{opacity:1}}50%{{opacity:0.42}}}}
@keyframes live-pulse{{0%,100%{{opacity:1}}50%{{opacity:0.58}}}}
@keyframes panel-in{{to{{opacity:1;transform:none}}}}
@keyframes bar-fill{{to{{transform:scaleX(1)}}}}
@keyframes bar-rise{{to{{transform:scaleY(1)}}}}
@keyframes fade-up{{to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.led,.p-hint,.in,.bar-grow,.pulse-bar,.tag-pop{{animation:none;opacity:1;transform:none}}}}
</style>
{_crt_defs(prefix, w, h)}
{chrome_base}
<g clip-path="url(#{prefix}-scr)">
<g class="in">
  {p1}
  {"".join(lang_rows)}
  {"".join(module_tags)}
  {p2}
  {"".join(kv_svg)}
  {spark_svg}
  {footer}
</g>
</g>
{chrome_overlay}
</svg>'''


BRAND_LOGOS: dict[str, tuple[str, str]] = {
    "github": (
        "",
        '<path transform="scale(0.833)" fill="#f0f6fc" fill-rule="evenodd" d="M12 1.27a11 11 0 00-3.48 21.46c.55.09.73-.28.73-.55v-1.84c-3.03.64-3.67-1.45-3.67-1.45-.55-1.29-1.28-1.65-1.28-1.65-.92-.65.1-.65.1-.65 1.1 0 1.73 1.1 1.73 1.1.92 1.65 2.57 1.2 3.21.92a2 2 0 01.64-1.47c-2.47-.27-5.04-1.19-5.04-5.5 0-1.1.46-2.1 1.2-2.84a3.76 3.76 0 010-2.93s.91-.28 3.11 1.1c1.8-.49 3.7-.49 5.5 0 2.1-1.38 3.02-1.1 3.02-1.1a3.76 3.76 0 010 2.93c.83.74 1.2 1.74 1.2 2.94 0 4.21-2.57 5.13-5.04 5.4.45.37.82.92.82 2.02v3.03c0 .27.1.64.73.55A11 11 0 0012 1.27z"/>',
    ),
    "instagram": (
        '<defs><linearGradient id="ig-btn" x1="2" y1="22" x2="22" y2="2" gradientUnits="userSpaceOnUse">'
        '<stop offset="0%" stop-color="#feda75"/><stop offset="25%" stop-color="#fa7e1e"/>'
        '<stop offset="50%" stop-color="#d62976"/><stop offset="75%" stop-color="#962fbf"/>'
        '<stop offset="100%" stop-color="#4f5bd5"/></linearGradient></defs>',
        '<g transform="scale(0.833)" fill="none"><rect x="2" y="2" width="20" height="20" rx="5.5" stroke="url(#ig-btn)" stroke-width="2.2"/>'
        '<circle cx="12" cy="12" r="4.2" stroke="url(#ig-btn)" stroke-width="2.2"/>'
        '<circle cx="17.3" cy="6.7" r="1.35" fill="url(#ig-btn)"/></g>',
    ),
    "tiktok": (
        "",
        '<g transform="scale(0.833)">'
        '<path d="M16.6 5.82s.51.5 0 0A4.28 4.28 0 0 1 15.54 3h-3.09v12.4a2.59 2.59 0 0 1-2.59 2.5c-1.42 0-2.6-1.16-2.6-2.6 0-1.72 1.66-3.01 3.37-2.48V9.66c-3.45-.46-6.47 2.22-6.47 5.64 0 3.33 2.76 5.7 5.69 5.7 3.14 0 5.69-2.55 5.69-5.7V9.01a7.35 7.35 0 0 0 4.3 1.38V7.3s-1.88.09-3.24-1.48z" fill="#25F4EE" transform="translate(-0.8,-0.6)"/>'
        '<path d="M16.6 5.82s.51.5 0 0A4.28 4.28 0 0 1 15.54 3h-3.09v12.4a2.59 2.59 0 0 1-2.59 2.5c-1.42 0-2.6-1.16-2.6-2.6 0-1.72 1.66-3.01 3.37-2.48V9.66c-3.45-.46-6.47 2.22-6.47 5.64 0 3.33 2.76 5.7 5.69 5.7 3.14 0 5.69-2.55 5.69-5.7V9.01a7.35 7.35 0 0 0 4.3 1.38V7.3s-1.88.09-3.24-1.48z" fill="#FE2C55" transform="translate(0.8,0.6)"/>'
        '<path d="M16.6 5.82s.51.5 0 0A4.28 4.28 0 0 1 15.54 3h-3.09v12.4a2.59 2.59 0 0 1-2.59 2.5c-1.42 0-2.6-1.16-2.6-2.6 0-1.72 1.66-3.01 3.37-2.48V9.66c-3.45-.46-6.47 2.22-6.47 5.64 0 3.33 2.76 5.7 5.69 5.7 3.14 0 5.69-2.55 5.69-5.7V9.01a7.35 7.35 0 0 0 4.3 1.38V7.3s-1.88.09-3.24-1.48z" fill="#FFFFFF"/></g>',
    ),
}


def render_cli_button(label: str, icon: str = "", delay_s: float = 0.0) -> str:
    """Render a compact GitHub Blue CRT command-keycap SVG badge with subtle motion."""
    clean_label = " ".join(_strip_xml_illegal(label).split())
    safe_delay = max(0.0, float(delay_s)) if math.isfinite(delay_s) else 0.0
    logo_defs, logo_shape = BRAND_LOGOS.get(icon, ("", ""))
    text_w = round((len(clean_label) + 3) * 7.5)
    icon_pad = 28 if logo_shape else 0
    w = max(180, text_w + icon_pad + 32)
    h = 38
    text_x = 16 + icon_pad if logo_shape else w / 2
    anchor = "start" if logo_shape else "middle"
    float_delay = safe_delay + 0.35
    logo_svg = (
        f'<g transform="translate(14,9)"><g class="ico" style="animation-delay:{float_delay:.2f}s">{logo_shape}</g></g>'
        if logo_shape
        else ""
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
text{{font-family:{FONT_STACK};font-size:12px;font-weight:700;fill:{ACCENT_SOFT}}}
.pre{{fill:{ACCENT_CORE}}}
.btn{{opacity:0;transform:translateY(8px);animation:btn-in 0.55s cubic-bezier(.16,1,.3,1) {safe_delay + 0.20:.2f}s forwards}}
.ico{{animation:ico-float 3.4s ease-in-out infinite}}
@keyframes btn-in{{to{{opacity:1;transform:none}}}}
@keyframes ico-float{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-1.2px)}}}}
@media (prefers-reduced-motion:reduce){{.btn,.ico{{animation:none;opacity:1;transform:none}}}}
</style>
{logo_defs}
<g class="btn">
<rect width="{w}" height="{h}" rx="7" fill="{SCREEN_BAR}" stroke="{SCREEN_STROKE}" stroke-width="1.2"/>
<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="5" fill="none" stroke="#1e293b" stroke-width="1"/>
{logo_svg}
<text x="{text_x:.1f}" y="23" text-anchor="{anchor}"><tspan class="pre">&gt;_ </tspan>{esc(clean_label)}</text>
</g>
</svg>'''
