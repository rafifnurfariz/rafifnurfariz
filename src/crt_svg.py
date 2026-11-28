"""Retro CRT Amber SVG rendering engine for BIOS/Terminal and btop telemetry."""
from __future__ import annotations

import html

from github_stats import ProfileTelemetry

# Retro CRT Amber Phosphor Palette (#121212 charcoal + #ffb000 classic amber)
CHASSIS_BG = "#0c0a08"
CHASSIS_STROKE = "#332308"
SCREEN_BG = "#121212"
SCREEN_BAR = "#1a150c"
SCREEN_STROKE = "#4d3408"
PANEL_BORDER = "#3d2a09"
PANEL_DIVIDER = "#291c06"

AMBER_BRIGHT = "#ffd54f"
AMBER_CORE = "#ffb000"
AMBER_SOFT = "#ffe8a3"
AMBER_MID = "#cc8800"
AMBER_DIM = "#7a5200"
AMBER_DARK = "#2d1f05"

FONT_STACK = "'Cascadia Mono','JetBrains Mono','Fira Code',Consolas,'SFMono-Regular',ui-monospace,monospace"


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def clamp_text(text: str, max_len: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= max_len:
        return clean
    return clean[: max(1, max_len - 3)].rstrip() + "..."


def fmt_bytes(byte_count: int) -> str:
    if byte_count >= 1_048_576:
        return f"{byte_count / 1_048_576:.1f} MB"
    return f"{max(0.1, byte_count / 1024):.1f} KB"


def fmt_repo_kb(size_kb: int) -> str:
    if size_kb >= 1024:
        return f"{size_kb / 1024:.1f} MB"
    return f"{size_kb} KB"


def fmt_uptime(days: int) -> str:
    if days >= 365:
        years, rem = divmod(days, 365)
        return f"{years}y {rem}d"
    return f"{days}d"


def strip_scheme(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")


def _crt_defs(prefix: str, width: int, height: int, extra: str = "") -> str:
    return (
        "<defs>"
        f'<pattern id="{prefix}-scan" width="4" height="3" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="1" fill="#000000" fill-opacity="0.24"/>'
        "</pattern>"
        f'<radialGradient id="{prefix}-vig" cx="50%" cy="48%" r="65%">'
        f'<stop offset="0%" stop-color="{AMBER_CORE}" stop-opacity="0.06"/>'
        '<stop offset="72%" stop-color="#121212" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#000000" stop-opacity="0.45"/>'
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
        f'<rect x="12" y="12" width="{inner_w}" height="{inner_h}" rx="9" fill="{SCREEN_BG}" stroke="{SCREEN_STROKE}" stroke-width="1.2"/>'
        f'<rect x="12" y="12" width="{inner_w}" height="30" rx="9" fill="{SCREEN_BAR}"/>'
        f'<rect x="12" y="30" width="{inner_w}" height="12" fill="{SCREEN_BAR}"/>'
        f'<line x1="12" y1="42" x2="{width - 12}" y2="42" stroke="{SCREEN_STROKE}" stroke-width="1"/>'
        f'<circle cx="28" cy="27" r="4" fill="{AMBER_CORE}" class="led" filter="url(#{prefix}-glow)"/>'
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


def _bios_chip_badge(x: int, y: int) -> str:
    """Pixel-art retro amber BIOS emblem inspired by classic Award POST badges."""
    rows = [
        "001111111100",
        "010000000010",
        "101101101101",
        "101001100101",
        "101111111101",
        "100011110001",
        "010000000010",
        "001111111100",
    ]
    rects = []
    px = 5
    for r_idx, row in enumerate(rows):
        for c_idx, ch in enumerate(row):
            if ch == "1":
                color = AMBER_BRIGHT if r_idx in (2, 4) else AMBER_CORE
                rects.append(
                    f'<rect x="{x + c_idx * px}" y="{y + r_idx * px}" '
                    f'width="{px - 0.6}" height="{px - 0.6}" rx="0.6" fill="{color}"/>'
                )
    return (
        f'<g opacity="0.92">'
        f'<rect x="{x - 6}" y="{y - 6}" width="{12 * px + 12}" height="{8 * px + 24}" '
        f'rx="4" fill="#171208" stroke="{AMBER_DIM}" stroke-width="1"/>'
        f'{"".join(rects)}'
        f'<text x="{x + 6 * px}" y="{y + 8 * px + 13}" text-anchor="middle" '
        f'font-size="8.5" font-weight="700" fill="{AMBER_CORE}">AMBER-P3</text>'
        "</g>"
    )


def _crt_ascii_art(x: int, y: int) -> str:
    """Crisp Retro CRT Monitor + terminal </> ASCII art in glowing phosphor amber."""
    lines: list[tuple[str, str]] = [
        ("     _______________________     ", AMBER_MID),
        ("    /                       \\    ", AMBER_MID),
        ("   /  +-------------------+  \\   ", AMBER_MID),
        ("  |   | C:\\> code_        |   |  ", AMBER_BRIGHT),
        ("  |   |                   |   |  ", AMBER_CORE),
        ("  |   |     {  /\\_/\\  }   |   |  ", AMBER_BRIGHT),
        ("  |   |     (  >_<  )     |   |  ", AMBER_BRIGHT),
        ("  |   |     /> </> <\\     |   |  ", AMBER_CORE),
        ("  |   +-------------------+   |  ", AMBER_MID),
        ("  |   [===]         (*) PWR   |  ", AMBER_DIM),
        ("   \\_________________________/   ", AMBER_MID),
        ("      ___|_____________|___      ", AMBER_DIM),
        ("   __/_____________________\\__   ", AMBER_DIM),
        ("  /  [][][][][][][][][][][]   \\  ", AMBER_MID),
        (" /_____________________________\\ ", AMBER_DIM),
    ]
    out = ['<g xml:space="preserve">']
    for idx, (line, color) in enumerate(lines):
        out.append(
            f'<text x="{x}" y="{y + idx * 16}" class="asc" fill="{color}">{esc(line)}</text>'
        )
    out.append("</g>")
    return "".join(out)


def _step_kf(name: str, show_pct: float, hide_pct: float) -> str:
    pre = max(0.0, show_pct - 0.25)
    post = min(100.0, hide_pct + 0.35)
    return (
        f"@keyframes {name}{{"
        f"0%,{pre:.2f}%{{opacity:0}}"
        f"{show_pct:.2f}%,{hide_pct:.2f}%{{opacity:1}}"
        f"{post:.2f}%,100%{{opacity:0}}}}"
    )


def render_bios_terminal(t: ProfileTelemetry) -> str:
    """Render two-phase Retro CRT Amber BIOS POST -> CMD neofetch terminal SVG."""
    w, h = 860, 430
    prefix = "bios"
    top_repo = t.repos[0] if t.repos else None
    top_repo_name = top_repo.name if top_repo else t.username
    top_repo_lang = top_repo.language if top_repo else "Code"
    net_target = strip_scheme(t.homepage) if t.homepage else f"github.com/{t.username}"

    lang_list = " · ".join(name for name, _ in t.languages[:4]) or "Exploring"
    stack_list = " · ".join(t.stacks[:4]) or lang_list
    uptime_label = f"{fmt_uptime(t.uptime_days)} (since {t.created_at})"

    bios_lines = [
        ("MAIN PROCESSOR : X86_64 DEVELOPER CORE @ 4.20GHz", "[VERIFIED]", 2.0),
        ("MEMORY TESTING : 65536K OK", "[PASS]", 4.2),
        (f"IDE0 PRIMARY   : /dev/github/{t.username}", "[ONLINE]", 7.8),
        (f"IDE1 PROJECT   : /dev/repo/{clamp_text(top_repo_name, 20)} ({top_repo_lang})", "[MOUNTED]", 9.8),
        (f"NETWORK IFACE  : {clamp_text(net_target, 32)}", "[LINK UP]", 11.8),
        (f"VOLUME SCAN    : {t.public_repos} REPOS · {fmt_bytes(t.total_bytes)} CODEBASE", "[READY]", 13.8),
        (f"ACTIVE STACK   : {clamp_text(stack_list, 40)}", "[LOADED]", 15.8),
        ("POST DIAGNOSTIC: 0 ERRORS · DEL:SETUP · F12:BOOT_MENU", "[OK]", 17.8),
        ("BOOTING RAFIF-OS KERNEL -> cmd.exe / neofetch ...", "", 19.6),
    ]

    bios_kf_css = []
    bios_rows_svg = []
    bios_classes = []
    for idx, (label, tag, pct) in enumerate(bios_lines):
        cls = f"bl{idx}"
        bios_classes.append(f".{cls}")
        bios_kf_css.append(_step_kf(f"kf-{cls}", pct, 24.4))
        bios_kf_css.append(f".{cls}{{animation:kf-{cls} 24s linear infinite}}")
        y_pos = 138 + idx * 24
        tag_svg = (
            f'<text x="816" y="{y_pos}" text-anchor="end" class="ok">{esc(tag)}</text>'
            if tag
            else ""
        )
        bios_rows_svg.append(
            f'<g class="{cls}">'
            f'<text x="32" y="{y_pos}" class="b-txt">{esc(label)}</text>'
            f"{tag_svg}"
            "</g>"
        )

    neo_rows = [
        ("USER", f"{t.username} ({t.display_name})"),
        ("OS", f"Windows 11 x86_64 // {clamp_text(t.location, 20)}"),
        ("SHELL", "cmd.exe // PowerShell 7"),
        ("STACK", clamp_text(stack_list, 44)),
        ("LANGS", clamp_text(lang_list, 44)),
        ("UPTIME", uptime_label),
        ("REPOS", f"{t.public_repos:02d} public · {fmt_bytes(t.total_bytes)} code"),
        ("DEPLOY", clamp_text(net_target, 44)),
    ]

    neo_kf_css = []
    neo_rows_svg = []
    neo_classes = []
    for idx, (key, val) in enumerate(neo_rows):
        cls = f"nl{idx}"
        neo_classes.append(f".{cls}")
        pct = 35.8 + idx * 1.1
        neo_kf_css.append(_step_kf(f"kf-{cls}", pct, 96.4))
        neo_kf_css.append(f".{cls}{{animation:kf-{cls} 24s linear infinite}}")
        y_pos = 180 + idx * 21
        neo_rows_svg.append(
            f'<g class="{cls}">'
            f'<text x="382" y="{y_pos}" class="nk">{esc(key)}</text>'
            f'<text x="448" y="{y_pos}" class="nd">:</text>'
            f'<text x="462" y="{y_pos}" class="nv">{esc(val)}</text>'
            "</g>"
        )

    swatches = ["#1f1503", "#3d2806", "#664308", "#996408", "#cc8600", AMBER_CORE, AMBER_BRIGHT, "#fff2bf"]
    swatch_svg = "".join(
        f'<rect x="{382 + i * 28}" y="356" width="22" height="12" rx="2.5" '
        f'fill="{c}" stroke="{PANEL_BORDER}" stroke-width="0.8"/>'
        for i, c in enumerate(swatches)
    )

    prompt_text = f"C:\\Users\\{t.username}>"
    prompt_w = round(len(prompt_text) * 7.8)
    cmd_x = 32 + prompt_w + 8
    cmd_text = "neofetch --crt amber"
    cmd_w = round(len(cmd_text) * 7.8) + 2

    extra_defs = (
        f'<clipPath id="{prefix}-cmd-clip">'
        f'<g transform="translate({cmd_x},101)">'
        f'<rect x="0" y="0" width="{cmd_w}" height="24" class="cmd-clip-rect"/>'
        "</g>"
        "</clipPath>"
    )

    chrome_base, chrome_overlay = _crt_chrome(
        prefix,
        w,
        h,
        f"CRT-01 // {t.username}@amber-console",
        "PHOSPHOR P3 · 60Hz · TTY1",
    )

    reduced_selectors = ",".join([".tty-phase"] + bios_classes + neo_classes)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
text{{font-family:{FONT_STACK}}}
.bar-t{{font-size:11.5px;font-weight:700;fill:{AMBER_CORE};letter-spacing:0.4px}}
.bar-r{{font-size:10.5px;fill:{AMBER_MID};letter-spacing:0.4px}}
.b-head{{font-size:13.5px;font-weight:700;fill:{AMBER_BRIGHT}}}
.b-sub{{font-size:12px;fill:{AMBER_MID}}}
.b-txt{{font-size:12.5px;fill:{AMBER_SOFT}}}
.ok{{font-size:12px;font-weight:700;fill:{AMBER_BRIGHT}}}
.tty-h{{font-size:12px;fill:{AMBER_MID}}}
.prm{{font-size:13px;font-weight:700;fill:{AMBER_CORE}}}
.cmd{{font-size:13px;fill:{AMBER_BRIGHT}}}
.asc{{font-size:11.5px;white-space:pre}}
.nh{{font-size:13.5px;font-weight:700;fill:{AMBER_BRIGHT}}}
.nk{{font-size:12.5px;font-weight:700;fill:{AMBER_CORE}}}
.nd{{font-size:12.5px;fill:{AMBER_DIM}}}
.nv{{font-size:12.5px;fill:{AMBER_SOFT}}}
.pal-lbl{{font-size:10.5px;fill:{AMBER_DIM};letter-spacing:0.6px}}
.led{{animation:led-pulse 2.2s ease-in-out infinite}}
.cur-blink{{animation:cur-flash 1.05s steps(1,end) infinite}}
.bios-phase{{animation:kf-bios-phase 24s linear infinite}}
.tty-phase{{animation:kf-tty-phase 24s linear infinite}}
.mem-fill{{transform-origin:274px 157px;animation:kf-mem 24s linear infinite}}
.cmd-clip-rect{{transform-origin:0 0;animation:kf-cmd-type 24s steps({len(cmd_text)},end) infinite}}
.type-cur{{animation:kf-type-cur 24s steps({len(cmd_text)},end) infinite}}
{"".join(bios_kf_css)}
{"".join(neo_kf_css)}
@keyframes led-pulse{{0%,100%{{opacity:1}}50%{{opacity:0.42}}}}
@keyframes cur-flash{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
@keyframes kf-bios-phase{{0%,24.4%{{opacity:1}}25%,99.2%{{opacity:0}}100%{{opacity:1}}}}
@keyframes kf-tty-phase{{0%,25.2%{{opacity:0}}25.8%,96.8%{{opacity:1}}97.4%,100%{{opacity:0}}}}
@keyframes kf-mem{{0%,4.2%{{transform:scaleX(0.05)}}8.5%,24.4%{{transform:scaleX(1)}}25%,100%{{transform:scaleX(0.05)}}}}
@keyframes kf-cmd-type{{0%,27.5%{{transform:scaleX(0)}}34.5%,96.8%{{transform:scaleX(1)}}97.4%,100%{{transform:scaleX(0)}}}}
@keyframes kf-type-cur{{0%,27.4%{{opacity:0;transform:translateX(0)}}27.5%{{opacity:1;transform:translateX(0)}}34.5%{{opacity:1;transform:translateX({cmd_w}px)}}35%,100%{{opacity:0;transform:translateX({cmd_w}px)}}}}
@media (prefers-reduced-motion:reduce){{
  .bios-phase{{display:none}}
  {reduced_selectors}{{animation:none;opacity:1}}
  .cmd-clip-rect{{animation:none;transform:scaleX(1)}}
  .type-cur{{display:none}}
  .led,.cur-blink{{animation:none;opacity:1}}
}}
</style>
{_crt_defs(prefix, w, h, extra=extra_defs)}
{chrome_base}
<g clip-path="url(#{prefix}-scr)">
  <!-- PHASE 1: RETRO BIOS POST -->
  <g class="bios-phase">
    <text x="32" y="76" class="b-head" filter="url(#{prefix}-glow)">RAFIF-BIOS v2.60-P3 // AMBER PHOSPHOR ALLY</text>
    <text x="32" y="96" class="b-sub">Copyright (C) 2026, Rafif Nurfariz Systems Inc.</text>
    <line x1="32" y1="112" x2="730" y2="112" stroke="{PANEL_BORDER}" stroke-width="1"/>
    {_bios_chip_badge(756, 62)}
    {"".join(bios_rows_svg)}
    <g class="bl1">
      <rect x="272" y="151" width="180" height="12" rx="2" fill="none" stroke="{AMBER_DIM}" stroke-width="1"/>
      <rect x="274" y="153" width="176" height="8" rx="1" fill="{AMBER_CORE}" class="mem-fill" opacity="0.9"/>
    </g>
  </g>

  <!-- PHASE 2: CMD PROMPT TYPING + NEOFETCH -->
  <g class="tty-phase">
    <text x="32" y="74" class="tty-h">RAFIF-OS [Version 10.0.26100] // Amber CRT Console</text>
    <text x="32" y="92" class="tty-h">(c) 2026 {esc(t.username)}@github. Session tty1 active.</text>
    <text x="32" y="118" textLength="{prompt_w}" class="prm">{esc(prompt_text)}</text>
    <text x="{cmd_x}" y="118" textLength="{cmd_w - 2}" class="cmd" clip-path="url(#{prefix}-cmd-clip)" filter="url(#{prefix}-glow)">{esc(cmd_text)}</text>
    <rect x="{cmd_x}" y="106" width="8" height="14" rx="1" fill="{AMBER_BRIGHT}" class="type-cur"/>
    <line x1="32" y1="132" x2="828" y2="132" stroke="{PANEL_DIVIDER}" stroke-width="1"/>

    {_crt_ascii_art(28, 160)}

    <text x="382" y="156" class="nh" filter="url(#{prefix}-glow)">{esc(t.username)}@github <tspan class="bar-r">[{esc(t.display_name)}]</tspan></text>
    <line x1="382" y1="164" x2="820" y2="164" stroke="{PANEL_BORDER}" stroke-width="1"/>
    {"".join(neo_rows_svg)}
    {swatch_svg}
    <text x="614" y="366" class="pal-lbl">P3-AMBER // 8-SHADE</text>

    <text x="32" y="398" textLength="{prompt_w}" class="prm">{esc(prompt_text)}</text>
    <rect x="{cmd_x}" y="386" width="8" height="14" rx="1" fill="{AMBER_BRIGHT}" class="cur-blink"/>
  </g>
</g>
{chrome_overlay}
</svg>'''


def _panel_box(x: int, y: int, w: int, h: int, title: str, right_hint: str = "") -> str:
    title_w = len(title) * 7.2 + 16
    right_svg = (
        f'<rect x="{x + w - len(right_hint) * 7 - 24}" y="{y - 8}" width="{len(right_hint) * 7 + 14}" height="16" fill="{SCREEN_BG}"/>'
        f'<text x="{x + w - 16}" y="{y + 3}" text-anchor="end" class="p-hint">{esc(right_hint)}</text>'
        if right_hint
        else ""
    )
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#14110c" stroke="{PANEL_BORDER}" stroke-width="1.2"/>'
        f'<rect x="{x + 12}" y="{y - 8}" width="{title_w:.1f}" height="16" fill="{SCREEN_BG}"/>'
        f'<text x="{x + 19}" y="{y + 3}" class="p-title">{esc(title)}</text>'
        f"{right_svg}"
    )


def _segmented_bar(x: int, y: int, pct: float, segments: int = 18) -> str:
    filled = max(1 if pct > 0 else 0, round((pct / 100.0) * segments))
    seg_w, gap = 7, 2
    rects = []
    for idx in range(segments):
        sx = x + idx * (seg_w + gap)
        if idx < filled:
            fill = AMBER_BRIGHT if idx >= segments - 4 else AMBER_CORE
            opacity = "0.95"
        else:
            fill = AMBER_DARK
            opacity = "0.8"
        rects.append(f'<rect x="{sx}" y="{y}" width="{seg_w}" height="10" rx="1.2" fill="{fill}" opacity="{opacity}"/>')
    return "".join(rects)


def render_btop_telemetry(t: ProfileTelemetry) -> str:
    """Render Retro CRT Amber btop/htop live GitHub telemetry SVG."""
    w, h = 860, 466
    prefix = "btop"
    chrome_base, chrome_overlay = _crt_chrome(
        prefix,
        w,
        h,
        f"TTY2 // btop++ --user {t.username} --theme amber-crt",
        f"SYNC {t.synced_at}",
    )

    p1 = _panel_box(22, 58, 424, 190, "[1] cpu // lang_allocation", fmt_bytes(t.total_bytes))
    total_b = max(1, t.total_bytes)
    top_langs = t.languages[:4] if t.languages else [("Exploring", 1)]
    lang_rows = []
    for idx, (lang, b_val) in enumerate(top_langs):
        pct = (b_val / total_b) * 100.0 if t.total_bytes else 0.0
        ry = 86 + idx * 28
        lang_rows.append(
            f'<text x="36" y="{ry}" class="lbl">{esc(clamp_text(lang, 11))}</text>'
            f'{_segmented_bar(134, ry - 9, pct, segments=18)}'
            f'<text x="352" y="{ry}" text-anchor="end" class="val">{pct:5.1f}%</text>'
            f'<text x="430" y="{ry}" text-anchor="end" class="dim">{esc(fmt_bytes(b_val))}</text>'
        )

    tag_x = 36
    tag_y = 210
    module_tags = []
    for mod in t.stacks[:6]:
        tw = len(mod) * 6.8 + 14
        if tag_x + tw > 432:
            break
        module_tags.append(
            f'<rect x="{tag_x}" y="{tag_y}" width="{tw:.1f}" height="20" rx="3" fill="#1d1609" stroke="{AMBER_DIM}" stroke-width="0.9"/>'
            f'<text x="{tag_x + tw / 2:.1f}" y="{tag_y + 13.5}" text-anchor="middle" class="tag">{esc(mod)}</text>'
        )
        tag_x += tw + 6

    p2 = _panel_box(458, 58, 380, 190, "[2] mem // git_telemetry", "LIVE")
    kv_pairs = [
        ("REPOS_PUB", f"{t.public_repos:02d}", "CODE_VOL", fmt_bytes(t.total_bytes)),
        ("STARS_TOT", f"{t.total_stars:02d}", "FORKS_TOT", f"{t.total_forks:02d}"),
        ("FOLLOWERS", f"{t.followers:02d}", "UPTIME", fmt_uptime(t.uptime_days)),
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

    series = t.push_series or [0] * 14
    peak = max(1, max(series))
    spark_bars = []
    base_x = 476
    bar_w = 19
    gap = 6
    max_bar_h = 44
    for i, val in enumerate(series[:14]):
        bh = max(4, round((val / peak) * max_bar_h)) if val > 0 else 3
        bx = base_x + i * (bar_w + gap)
        by = 228 - bh
        fill = AMBER_BRIGHT if val == max(series) and val > 0 else (AMBER_CORE if val > 0 else AMBER_DARK)
        spark_bars.append(f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" rx="1.5" fill="{fill}"/>')

    spark_svg = (
        f'<line x1="474" y1="150" x2="822" y2="150" stroke="{PANEL_DIVIDER}" stroke-width="1"/>'
        f'<text x="474" y="168" class="dim">PUSH_PULSE (14D)</text>'
        f'<text x="822" y="168" text-anchor="end" class="val">{t.recent_push_count} events · peak {max(series)}/d</text>'
        f'<line x1="474" y1="196" x2="822" y2="196" stroke="{PANEL_DIVIDER}" stroke-dasharray="3 3" stroke-width="1"/>'
        f'{"".join(spark_bars)}'
    )

    p3 = _panel_box(22, 266, 816, 162, "[3] proc // active_repos & git_log", f"{len(t.repos)} PROC")
    proc_head = (
        '<text x="38" y="292" class="tbl-h">PID</text>'
        '<text x="92" y="292" class="tbl-h">PROCESS / REPO</text>'
        '<text x="282" y="292" class="tbl-h">LANG</text>'
        '<text x="398" y="292" class="tbl-h">SIZE</text>'
        '<text x="492" y="292" class="tbl-h">PUSHED</text>'
        '<text x="590" y="292" class="tbl-h">STATE / TARGET</text>'
        f'<line x1="38" y1="299" x2="822" y2="299" stroke="{PANEL_DIVIDER}" stroke-width="1"/>'
    )
    proc_rows = []
    for idx, repo in enumerate(t.repos[:2]):
        ry = 318 + idx * 21
        pid = 1001 + idx
        state = "[DAEMON]" if repo.is_profile_repo else "[RUNNING]"
        target = strip_scheme(repo.homepage) if repo.homepage else ("profile-sync" if repo.is_profile_repo else clamp_text(repo.description or "active", 20))
        proc_rows.append(
            f'<text x="38" y="{ry}" class="dim">{pid}</text>'
            f'<text x="92" y="{ry}" class="val-hi">{esc(clamp_text(repo.name, 22))}</text>'
            f'<text x="282" y="{ry}" class="lbl">{esc(clamp_text(repo.language, 12))}</text>'
            f'<text x="398" y="{ry}" class="val">{esc(fmt_repo_kb(repo.size_kb))}</text>'
            f'<text x="492" y="{ry}" class="dim">{esc(repo.pushed_at)}</text>'
            f'<text x="590" y="{ry}" class="ok">{esc(state)} {esc(clamp_text(target, 20))}</text>'
        )

    git_log_rows = [f'<line x1="38" y1="354" x2="822" y2="354" stroke="{PANEL_DIVIDER}" stroke-width="1"/>']
    commits = t.recent_commits[:2]
    if not commits:
        git_log_rows.append('<text x="38" y="376" class="dim">* [git log] Waiting for recent public commits...</text>')
    else:
        for idx, c in enumerate(commits):
            cy = 376 + idx * 21
            git_log_rows.append(
                f'<text x="38" y="{cy}" class="ok">*</text>'
                f'<text x="54" y="{cy}" class="val-hi">{esc(c.sha)}</text>'
                f'<text x="122" y="{cy}" class="dim">{esc(c.date)}</text>'
                f'<text x="214" y="{cy}" class="lbl">[{esc(clamp_text(c.repo, 12))}]</text>'
                f'<text x="326" y="{cy}" class="val">{esc(clamp_text(c.message, 64))}</text>'
            )

    footer = (
        '<text x="26" y="446" class="fkey">[F1]Help  [F2]Theme:AMBER-CRT  [1-3]Focus  [q]Quit</text>'
        '<text x="834" y="446" text-anchor="end" class="dim">AUTO-SYNC // GITHUB ACTIONS</text>'
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
text{{font-family:{FONT_STACK}}}
.bar-t{{font-size:11.5px;font-weight:700;fill:{AMBER_CORE};letter-spacing:0.4px}}
.bar-r{{font-size:10.5px;fill:{AMBER_MID};letter-spacing:0.4px}}
.p-title{{font-size:11.5px;font-weight:700;fill:{AMBER_BRIGHT}}}
.p-hint{{font-size:10.5px;font-weight:700;fill:{AMBER_CORE}}}
.lbl{{font-size:12px;fill:{AMBER_CORE};font-weight:600}}
.val{{font-size:12px;fill:{AMBER_SOFT}}}
.val-hi{{font-size:12px;fill:{AMBER_BRIGHT};font-weight:700}}
.dim{{font-size:11.5px;fill:{AMBER_MID}}}
.ok{{font-size:11.5px;font-weight:700;fill:{AMBER_BRIGHT}}}
.tag{{font-size:10.5px;fill:{AMBER_BRIGHT};font-weight:600}}
.tbl-h{{font-size:10.5px;fill:{AMBER_DIM};font-weight:700;letter-spacing:0.5px}}
.fkey{{font-size:10.5px;fill:{AMBER_CORE}}}
.led{{animation:led-pulse 2.2s ease-in-out infinite}}
.in{{animation:panel-in 0.55s ease-out both}}
@keyframes led-pulse{{0%,100%{{opacity:1}}50%{{opacity:0.42}}}}
@keyframes panel-in{{from{{opacity:0.65}}to{{opacity:1}}}}
@media (prefers-reduced-motion:reduce){{.led,.in{{animation:none;opacity:1}}}}
</style>
{_crt_defs(prefix, w, h)}
{chrome_base}
<g clip-path="url(#{prefix}-scr)" class="in">
  {p1}
  {"".join(lang_rows)}
  {"".join(module_tags)}
  {p2}
  {"".join(kv_svg)}
  {spark_svg}
  {p3}
  {proc_head}
  {"".join(proc_rows)}
  {"".join(git_log_rows)}
  {footer}
</g>
{chrome_overlay}
</svg>'''


def render_cli_button(label: str, tag: str) -> str:
    """Render a compact Retro CRT Amber command-keycap SVG badge."""
    text = f">_ {tag}://{label}"
    w = max(144, round(len(text) * 7.2) + 26)
    h = 34
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
text{{font-family:{FONT_STACK};font-size:12px;font-weight:700;fill:{AMBER_BRIGHT}}}
.pre{{fill:{AMBER_CORE}}}
</style>
<rect width="{w}" height="{h}" rx="6" fill="#14110c" stroke="{AMBER_DIM}" stroke-width="1.2"/>
<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="4.5" fill="none" stroke="#291c06" stroke-width="1"/>
<text x="{w / 2:.1f}" y="21" text-anchor="middle"><tspan class="pre">&gt;_ </tspan>{esc(tag)}://{esc(label)}</text>
</svg>'''
