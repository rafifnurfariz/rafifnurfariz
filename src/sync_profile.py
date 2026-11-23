"""Syncs neofetch.svg and stack.svg with GitHub repositories."""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

USER = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REPOSITORY_OWNER", "rafifnurfariz")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

LANG_SHORT = {
    "JavaScript": "JS",
    "TypeScript": "TS",
    "Python": "Py",
    "C++": "C++",
    "C#": "C#",
    "HTML": "HTML",
    "CSS": "CSS",
    "SCSS": "SCSS",
    "Shell": "Shell",
    "PowerShell": "PS",
    "Kotlin": "Kotlin",
    "Java": "Java",
    "Go": "Go",
    "Rust": "Rust",
    "PHP": "PHP",
    "Ruby": "Ruby",
    "Swift": "Swift",
    "Dart": "Dart",
}

BADGE_MAP = {
    "Next.js": ("Next.js", "nextdotjs", "white"),
    "React": ("React", "react", "61DAFB"),
    "TypeScript": ("TypeScript", "typescript", "3178C6"),
    "JavaScript": ("JavaScript", "javascript", "F7DF1E"),
    "HTML": ("HTML5", "html5", "E34F26"),
    "CSS": ("CSS3", "css3", "1572B6"),
    "C++": ("C%2B%2B", "cplusplus", "00599C"),
    "C#": ("C%23", "csharp", "239120"),
    "C": ("C", "c", "A8B9CC"),
    "Python": ("Python", "python", "3776AB"),
    "Go": ("Go", "go", "00ADD8"),
    "Rust": ("Rust", "rust", "DEA584"),
    "Java": ("Java", "openjdk", "ED8B00"),
    "PHP": ("PHP", "php", "777BB4"),
    "Dart": ("Dart", "dart", "0175C2"),
    "Tailwind": ("Tailwind%20CSS", "tailwindcss", "06B6D4"),
    "Vite": ("Vite", "vite", "646CFF"),
    "Vue": ("Vue.js", "vuedotjs", "4FC08D"),
    "Node.js": ("Node.js", "nodedotjs", "339933"),
    "Express": ("Express", "express", "white"),
    "Astro": ("Astro", "astro", "FF5D01"),
    "Svelte": ("Svelte", "svelte", "FF3E00"),
    "Flutter": ("Flutter", "flutter", "02569B"),
    "Docker": ("Docker", "docker", "2496ED"),
    "Django": ("Django", "django", "092E20"),
    "FastAPI": ("FastAPI", "fastapi", "009688"),
    "Flask": ("Flask", "flask", "white"),
}

PKG_DETECT = [
    ("next", "Next.js"),
    ("react", "React"),
    ("vue", "Vue"),
    ("svelte", "Svelte"),
    ("astro", "Astro"),
    ("tailwindcss", "Tailwind"),
    ("vite", "Vite"),
    ("express", "Express"),
]

TOPIC_DETECT = {
    "nextjs": "Next.js",
    "next-js": "Next.js",
    "react": "React",
    "reactjs": "React",
    "tailwindcss": "Tailwind",
    "tailwind": "Tailwind",
    "vite": "Vite",
    "vue": "Vue",
    "nodejs": "Node.js",
    "express": "Express",
    "flutter": "Flutter",
    "docker": "Docker",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "astro": "Astro",
    "svelte": "Svelte",
}


def api_get(url: str):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-sync"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return None


def get_file_text(owner: str, repo: str, path: str) -> str:
    data = api_get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}")
    if isinstance(data, dict) and data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


def collect_stats(user: str):
    repos = api_get(f"https://api.github.com/users/{user}/repos?per_page=100&type=owner&sort=updated")
    if not isinstance(repos, list):
        raise RuntimeError(f"Failed to fetch repos for {user}")

    lang_bytes: dict[str, int] = {}
    stacks: list[str] = []

    def add_stack(name: str):
        if name not in stacks:
            stacks.append(name)

    for repo in repos:
        if repo.get("fork") or repo.get("name", "").lower() == user.lower():
            continue
        name = repo["name"]

        # Aggregate languages
        langs = api_get(repo["languages_url"])
        if isinstance(langs, dict):
            for lang, b in langs.items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + int(b)

        # Detect stacks from topics
        for topic in repo.get("topics") or []:
            t = topic.lower()
            if t in TOPIC_DETECT:
                add_stack(TOPIC_DETECT[t])

        # Detect stacks from package.json
        pkg_raw = get_file_text(user, name, "package.json")
        if pkg_raw:
            try:
                pkg = json.loads(pkg_raw)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                for key, label in PKG_DETECT:
                    if key in deps:
                        add_stack(label)
            except Exception:
                pass

        # Detect Python frameworks from requirements.txt
        req_raw = get_file_text(user, name, "requirements.txt").lower()
        if req_raw:
            for key, label in [("django", "Django"), ("fastapi", "FastAPI"), ("flask", "Flask")]:
                if re.search(rf"\b{key}\b", req_raw):
                    add_stack(label)

    top_langs = [k for k, _ in sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)]
    return top_langs, stacks


def render_card(user: str, langs: list[str], stacks: list[str]):
    lang_str = " · ".join(LANG_SHORT.get(l, l) for l in langs[:5]) if langs else "Exploring"
    stack_str = " · ".join(stacks[:4]) if stacks else "Exploring"

    # Keep text inside the 400px card
    if len(lang_str) > 30:
        lang_str = " · ".join(LANG_SHORT.get(l, l) for l in langs[:4])
    if len(stack_str) > 30:
        stack_str = " · ".join(stacks[:3])

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="425" viewBox="0 0 400 425">
<style>
text{{font:13px ui-monospace,SFMono-Regular,Menlo,monospace}}
.h{{font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#8b949e}}
.k{{fill:#7ee787;font-weight:600}}.v{{fill:#e6edf3}}.d{{fill:#8b949e}}.m{{fill:#6e7681;font-size:11.5px}}
.b{{fill:#39d353;font-size:11px}}
.dot{{fill:#39d353}}
.cur{{fill:#39d353;animation:blink 1.4s ease-in-out infinite}}
.l{{opacity:0;transform:translateX(-6px);animation:f .5s cubic-bezier(.16,1,.3,1) forwards}}
.sw{{opacity:0;transform:scale(.75);transform-box:fill-box;transform-origin:center;animation:sw .45s cubic-bezier(.16,1,.3,1) forwards}}
@keyframes f{{to{{opacity:1;transform:none}}}}
@keyframes sw{{to{{opacity:1;transform:scale(1)}}}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.15}}}}
@media (prefers-reduced-motion:reduce){{.l,.sw{{animation:none;opacity:1;transform:none}}.cur{{animation:none}}}}
</style>
<rect width="400" height="425" rx="10" fill="#0d1117" stroke="#30363d"/>
<rect x="0" y="0" width="400" height="38" rx="10" fill="#161b22"/>
<rect x="0" y="28" width="400" height="10" fill="#161b22"/>
<line x1="0" y1="38" x2="400" y2="38" stroke="#30363d"/>
<circle cx="20" cy="19" r="5" fill="#ff5f56"/><circle cx="37" cy="19" r="5" fill="#ffbd2e"/><circle cx="54" cy="19" r="5" fill="#27c93f"/>
<text x="76" y="23" class="h">{user} ~ neofetch</text><rect x="234" y="13" width="6" height="12" rx="1" class="cur"/>
<circle cx="332" cy="19" r="3.5" class="dot"/><text x="341" y="22.5" class="b">online</text>

<text x="26" y="74" class="k">{user}</text><text x="130" y="74" class="d">@github</text>
<line x1="26" y1="88" x2="374" y2="88" stroke="#21262d"/>

<g class="l" style="animation-delay:0.30s"><text x="26" y="130" class="k">user</text><text x="104" y="130" class="v">{user}</text></g>
<g class="l" style="animation-delay:0.50s"><text x="26" y="174" class="k">lang</text><text x="104" y="174" class="v">{lang_str}</text></g>
<g class="l" style="animation-delay:0.70s"><text x="26" y="218" class="k">stack</text><text x="104" y="218" class="v">{stack_str}</text></g>
<g class="l" style="animation-delay:0.90s"><text x="26" y="262" class="k">tools</text><text x="104" y="262" class="v">Windows · VS Code · GitHub</text></g>

<line x1="26" y1="302" x2="374" y2="302" stroke="#21262d"/>

<g class="l" style="animation-delay:1.10s">
<text x="26" y="334" class="m">commit activity palette</text>
</g>
<rect class="sw" style="animation-delay:1.15s" x="26" y="352" width="34" height="16" rx="4" fill="#161b22" stroke="#30363d"/>
<rect class="sw" style="animation-delay:1.22s" x="68" y="352" width="34" height="16" rx="4" fill="#0e4429"/>
<rect class="sw" style="animation-delay:1.29s" x="110" y="352" width="34" height="16" rx="4" fill="#006d32"/>
<rect class="sw" style="animation-delay:1.36s" x="152" y="352" width="34" height="16" rx="4" fill="#26a641"/>
<rect class="sw" style="animation-delay:1.43s" x="194" y="352" width="34" height="16" rx="4" fill="#39d353"/>
</svg>'''
    with open("media/svg/neofetch.svg", "w", encoding="utf-8") as f:
        f.write(svg)


ICON_SVG = {
    "Next.js": '<circle cx="8" cy="8" r="7.5" fill="#fff"/><path d="M5.2 11.2V4.8h1.1l4.4 6.1V4.8h1v6.4h-1.1L6.2 5.2v6z" fill="#0d1117"/>',
    "React": '<circle cx="8" cy="8" r="1.5" fill="#61DAFB"/><ellipse cx="8" cy="8" rx="7" ry="2.7" fill="none" stroke="#61DAFB" stroke-width="1.1"/><ellipse cx="8" cy="8" rx="7" ry="2.7" fill="none" stroke="#61DAFB" stroke-width="1.1" transform="rotate(60 8 8)"/><ellipse cx="8" cy="8" rx="7" ry="2.7" fill="none" stroke="#61DAFB" stroke-width="1.1" transform="rotate(120 8 8)"/>',
    "TypeScript": '<rect x="1" y="1" width="14" height="14" rx="2.5" fill="#3178C6"/><text x="8" y="11.5" text-anchor="middle" font-family="ui-sans-serif,system-ui,sans-serif" font-size="7.5" font-weight="800" fill="#fff">TS</text>',
    "JavaScript": '<rect x="1" y="1" width="14" height="14" rx="2.5" fill="#F7DF1E"/><text x="8" y="11.5" text-anchor="middle" font-family="ui-sans-serif,system-ui,sans-serif" font-size="7.5" font-weight="800" fill="#0d1117">JS</text>',
    "CSS": '<path d="M2 1.5h12l-1.1 11L8 14.5l-4.9-2z" fill="#1572B6"/><path d="M5 4.8h6l-.3 2.2H6.5l.1 1.4h3.9l-.4 3-2.1.7-2.1-.7-.1-1.3h1.4l.1.5.7.2.7-.2.1-1H5.3z" fill="#fff"/>',
    "HTML": '<path d="M2 1.5h12l-1.1 11L8 14.5l-4.9-2z" fill="#E34F26"/><path d="M5 4.8h6l-.1 1.4H6.5l.1 1.4h4.1l-.4 3.5-2.3.7-2.3-.7-.2-1.7h1.4l.1.7 1 .3 1-.3.1-1.2H5.4z" fill="#fff"/>',
    "C++": '<polygon points="8,1 14.5,4.5 14.5,11.5 8,15 1.5,11.5 1.5,4.5" fill="#00599C"/><text x="8" y="10.5" text-anchor="middle" font-family="ui-sans-serif,system-ui,sans-serif" font-size="6.2" font-weight="800" fill="#fff">C++</text>',
    "Python": '<path d="M8 1.5c-2.8 0-2.6 1.2-2.6 1.2v1.3h2.7v.5H4.3S2.5 4.3 2.5 7.2c0 2.9 1.6 2.8 1.6 2.8h.9V8.6s-.1-1.6 1.5-1.6h2.7s1.5 0 1.5-1.4V3.1S11 1.5 8 1.5zm-1.4.9a.5.5 0 1 1 0 1 .5.5 0 0 1 0-1z" fill="#3776AB"/><path d="M8 14.5c2.8 0 2.6-1.2 2.6-1.2V12H7.9v-.5h3.8s1.8.2 1.8-2.7c0-2.9-1.6-2.8-1.6-2.8H11v1.4s.1 1.6-1.5 1.6H6.8s-1.5 0-1.5 1.4v2.5S5 14.5 8 14.5zm1.4-.9a.5.5 0 1 1 0-1 .5.5 0 0 1 0 1z" fill="#FFD43B"/>',
    "Tailwind": '<path d="M8 3.5c-2.2 0-3.6 1.1-4.2 3.3.8-1.1 1.8-1.5 3-1.2.6.2 1.1.6 1.6 1.1.8.8 1.8 1.8 3.8 1.8 2.2 0 3.6-1.1 4.2-3.3-.8 1.1-1.8 1.5-3 1.2-.6-.2-1.1-.6-1.6-1.1C11 4.5 10 3.5 8 3.5zm-4.2 5C1.6 8.5.2 9.6-.4 11.8c.8-1.1 1.8-1.5 3-1.2.6.2 1.1.6 1.6 1.1.8.8 1.8 1.8 3.8 1.8 2.2 0 3.6-1.1 4.2-3.3-.8 1.1-1.8 1.5-3 1.2-.6-.2-1.1-.6-1.6-1.1-.8-.8-1.8-1.8-3.8-1.8z" transform="translate(1.5,1) scale(.8)" fill="#06B6D4"/>',
    "Vite": '<polygon points="8,14.5 2.5,3 8,4.8 13.5,3" fill="#646CFF"/><polygon points="8.2,1.5 5.5,7.8 8.3,7.3 7.4,12.2 11.2,6 8.6,6.5" fill="#FFD62E"/>',
    "Node.js": '<polygon points="8,1 14.5,4.5 14.5,11.5 8,15 1.5,11.5 1.5,4.5" fill="#339933"/><text x="8" y="10.2" text-anchor="middle" font-family="ui-sans-serif,system-ui,sans-serif" font-size="6" font-weight="800" fill="#fff">JS</text>',
}


def render_stack_bar(langs: list[str], stacks: list[str]):
    items: list[str] = []
    for item in stacks + langs:
        if item not in items:
            items.append(item)
    if not items:
        items = ["Exploring"]

    pills = []
    gap = 10
    widths = [max(78, len(name) * 8 + 44) for name in items]
    total_w = sum(widths) + gap * (len(items) - 1)
    x = max(10, (835 - total_w) / 2)

    for idx, (item, w) in enumerate(zip(items, widths)):
        color = BADGE_MAP.get(item, (item, "", "#39d353"))[2]
        if color != "white" and not color.startswith("#"):
            color = f"#{color}"
        icon = ICON_SVG.get(item, f'<path d="M5 5l-3 3 3 3M11 5l3 3-3 3M9 4l-2 8" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>')
        safe = item.replace("&", "&amp;").replace("<", "&lt;")
        pills.append(
            f'<g>'
            f'<rect x="{x:.1f}" y="8" width="{w}" height="34" rx="8" fill="#161b22" stroke="#30363d"/>'
            f'<g transform="translate({x + 12:.1f},17)">{icon}</g>'
            f'<text x="{x + 34:.1f}" y="29.5" class="t">{safe}</text>'
            f'</g>'
        )
        x += w + gap

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="835" height="50" viewBox="0 0 835 50">
<style>
.in{{opacity:0;transform:translateY(8px);animation:in .7s cubic-bezier(.22,1,.36,1) .35s forwards}}
.t{{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#e6edf3}}
@keyframes in{{to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.in{{animation:none;opacity:1;transform:none}}}}
</style>
<g class="in">
{"".join(pills)}
</g>
</svg>'''
    with open("media/svg/stack.svg", "w", encoding="utf-8") as f:
        f.write(svg)


if __name__ == "__main__":
    langs, stacks = collect_stats(USER)
    render_card(USER, langs, stacks)
    render_stack_bar(langs, stacks)
    print(f"Synced for {USER}: langs={langs}, stacks={stacks}")
