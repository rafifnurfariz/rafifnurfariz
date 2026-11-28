"""Collects public GitHub profile, repository, stack, and activity telemetry."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
import re
import urllib.error
import urllib.request

PKG_DETECT: list[tuple[str, str]] = [
    ("next", "Next.js"),
    ("react", "React"),
    ("vue", "Vue"),
    ("svelte", "Svelte"),
    ("astro", "Astro"),
    ("tailwindcss", "Tailwind"),
    ("vite", "Vite"),
    ("express", "Express"),
    ("fabric", "Fabric.js"),
    ("sharp", "Sharp"),
    ("vitest", "Vitest"),
    ("eslint", "ESLint"),
    ("prisma", "Prisma"),
    ("@supabase/supabase-js", "Supabase"),
]

PY_DETECT: list[tuple[str, str]] = [
    ("django", "Django"),
    ("fastapi", "FastAPI"),
    ("flask", "Flask"),
    ("pillow", "Pillow"),
    ("numpy", "NumPy"),
    ("requests", "Requests"),
]

TOPIC_DETECT: dict[str, str] = {
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
    "typescript": "TypeScript",
    "python": "Python",
}


@dataclass
class RepoSummary:
    name: str
    description: str
    language: str
    size_kb: int
    stars: int
    forks: int
    pushed_at: str
    homepage: str
    is_profile_repo: bool = False


@dataclass
class CommitEntry:
    sha: str
    repo: str
    message: str
    date: str


@dataclass
class ProfileTelemetry:
    username: str
    display_name: str
    bio: str
    location: str
    homepage: str
    created_at: str
    uptime_days: int
    public_repos: int
    followers: int
    following: int
    total_stars: int
    total_forks: int
    total_bytes: int
    languages: list[tuple[str, int]] = field(default_factory=list)
    stacks: list[str] = field(default_factory=list)
    repos: list[RepoSummary] = field(default_factory=list)
    recent_commits: list[CommitEntry] = field(default_factory=list)
    push_series: list[int] = field(default_factory=list)
    recent_push_count: int = 0
    synced_at: str = ""


def api_get(url: str, token: str = "") -> dict | list | None:
    """Fetch JSON from GitHub REST API, returning None on HTTP errors."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rafifnurfariz-crt-profile",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


def get_file_text(owner: str, repo: str, path: str, token: str = "") -> str:
    """Read a repository file via GitHub Contents API."""
    data = api_get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}", token)
    if isinstance(data, dict) and data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_push_series(events: list[dict], now: datetime, days: int = 14) -> tuple[list[int], int]:
    buckets = [0] * days
    push_total = 0
    today = now.date()
    for ev in events:
        if ev.get("type") != "PushEvent":
            continue
        push_total += 1
        dt = _parse_iso(ev.get("created_at"))
        if not dt:
            continue
        delta = (today - dt.astimezone(timezone.utc).date()).days
        if 0 <= delta < days:
            buckets[days - 1 - delta] += 1
    return buckets, push_total


def collect_telemetry(username: str, token: str = "") -> ProfileTelemetry:
    """Gather GitHub user, repo, language, stack, commit, and event telemetry."""
    token = token or os.environ.get("GITHUB_TOKEN", "")
    now = datetime.now(timezone.utc)

    user_data = api_get(f"https://api.github.com/users/{username}", token)
    repos_data = api_get(
        f"https://api.github.com/users/{username}/repos?per_page=100&type=owner&sort=updated",
        token,
    )
    if not isinstance(user_data, dict) or not isinstance(repos_data, list):
        raise RuntimeError(f"Failed to fetch GitHub profile or repositories for {username}")

    created_dt = _parse_iso(user_data.get("created_at")) or now
    uptime_days = max(1, (now - created_dt).days)

    lang_bytes: dict[str, int] = {}
    stacks: list[str] = []
    repo_summaries: list[RepoSummary] = []
    total_stars = 0
    total_forks = 0
    homepage = (user_data.get("blog") or "").strip()

    def add_stack(label: str) -> None:
        if label not in stacks:
            stacks.append(label)

    for repo in repos_data:
        if repo.get("fork"):
            continue
        name = repo.get("name", "")
        is_profile = name.lower() == username.lower()
        stars = int(repo.get("stargazers_count") or 0)
        forks = int(repo.get("forks_count") or 0)
        total_stars += stars
        total_forks += forks

        repo_home = (repo.get("homepage") or "").strip()
        if repo_home and not homepage:
            homepage = repo_home

        langs = api_get(repo["languages_url"], token)
        if isinstance(langs, dict):
            for lang, b_count in langs.items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + int(b_count)

        for topic in repo.get("topics") or []:
            mapped = TOPIC_DETECT.get(topic.lower())
            if mapped:
                add_stack(mapped)

        if not is_profile:
            pkg_raw = get_file_text(username, name, "package.json", token)
            if pkg_raw:
                try:
                    pkg = json.loads(pkg_raw)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    for key, label in PKG_DETECT:
                        if key in deps:
                            add_stack(label)
                except Exception:
                    pass

            req_raw = get_file_text(username, name, "requirements.txt", token).lower()
            if req_raw:
                for key, label in PY_DETECT:
                    if re.search(rf"\b{re.escape(key)}\b", req_raw):
                        add_stack(label)

        pushed_dt = _parse_iso(repo.get("pushed_at"))
        pushed_str = pushed_dt.strftime("%Y-%m-%d") if pushed_dt else "-"
        repo_summaries.append(
            RepoSummary(
                name=name,
                description=(repo.get("description") or "").strip(),
                language=repo.get("language") or "Mixed",
                size_kb=int(repo.get("size") or 0),
                stars=stars,
                forks=forks,
                pushed_at=pushed_str,
                homepage=repo_home,
                is_profile_repo=is_profile,
            )
        )

    # Prefer project repositories ahead of the profile repo, then most recently pushed
    repo_summaries.sort(key=lambda r: (not r.is_profile_repo, r.stars, r.pushed_at), reverse=True)

    sorted_langs = sorted(lang_bytes.items(), key=lambda item: item[1], reverse=True)
    for lang_name, _ in sorted_langs[:3]:
        if lang_name in ("TypeScript", "Python", "JavaScript", "Go", "Rust"):
            add_stack(lang_name)

    recent_commits: list[CommitEntry] = []
    commit_targets = [r.name for r in repo_summaries[:2]]
    for target in commit_targets:
        commits = api_get(f"https://api.github.com/repos/{username}/{target}/commits?per_page=3", token)
        if not isinstance(commits, list):
            continue
        for c in commits:
            msg = ((c.get("commit") or {}).get("message") or "").splitlines()[0].strip()
            if "[skip ci]" in msg.lower():
                continue
            c_dt = _parse_iso(((c.get("commit") or {}).get("author") or {}).get("date"))
            recent_commits.append(
                CommitEntry(
                    sha=(c.get("sha") or "")[:7],
                    repo=target,
                    message=msg,
                    date=c_dt.strftime("%Y-%m-%d") if c_dt else "-",
                )
            )
    recent_commits.sort(key=lambda c: c.date, reverse=True)

    events = api_get(f"https://api.github.com/users/{username}/events/public?per_page=30", token)
    push_series, recent_push_count = _build_push_series(
        events if isinstance(events, list) else [],
        now,
    )

    return ProfileTelemetry(
        username=user_data.get("login") or username,
        display_name=(user_data.get("name") or username).strip(),
        bio=(user_data.get("bio") or "").strip(),
        location=(user_data.get("location") or "Indonesia").strip(),
        homepage=homepage,
        created_at=created_dt.strftime("%Y-%m-%d"),
        uptime_days=uptime_days,
        public_repos=int(user_data.get("public_repos") or len(repo_summaries)),
        followers=int(user_data.get("followers") or 0),
        following=int(user_data.get("following") or 0),
        total_stars=total_stars,
        total_forks=total_forks,
        total_bytes=sum(lang_bytes.values()),
        languages=sorted_langs,
        stacks=stacks,
        repos=repo_summaries,
        recent_commits=recent_commits[:3],
        push_series=push_series,
        recent_push_count=recent_push_count,
        synced_at=now.strftime("%Y-%m-%d %H:%M UTC"),
    )


def build_sample_telemetry(username: str = "rafifnurfariz") -> ProfileTelemetry:
    """Offline fallback fixture for local tests without network access."""
    return ProfileTelemetry(
        username=username,
        display_name="Rapiiipp",
        bio="Learning, experimenting & shipping code",
        location="Indonesia",
        homepage="https://photopip.vercel.app",
        created_at="2026-09-15",
        uptime_days=74,
        public_repos=2,
        followers=0,
        following=0,
        total_stars=0,
        total_forks=0,
        total_bytes=388124,
        languages=[
            ("TypeScript", 295884),
            ("CSS", 67770),
            ("Python", 16254),
            ("JavaScript", 8216),
        ],
        stacks=["Next.js", "React", "Fabric.js", "Sharp", "Vitest", "TypeScript", "Python"],
        repos=[
            RepoSummary("Photopip", "Photo editor web app", "TypeScript", 10285, 0, 0, "2026-11-24", "https://photopip.vercel.app", False),
            RepoSummary(username, "Personal GitHub profile", "Python", 217, 0, 0, "2026-11-28", "", True),
        ],
        recent_commits=[
            CommitEntry("f2c8ccc", "Photopip", "fix: sinkronisasi teks kosong, font kustom, handle resize", "2026-11-24"),
            CommitEntry("6d4f215", "Photopip", "fix: pertahankan warna dan font teks saat mengganti bingkai", "2026-11-24"),
        ],
        push_series=[0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 5, 6, 0, 0],
        recent_push_count=15,
        synced_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M UTC"),
    )
