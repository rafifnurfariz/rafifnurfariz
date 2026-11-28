"""Collects public GitHub profile, repository, stack, and activity telemetry."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import http.client
import json
import os
import re
import urllib.error
import urllib.parse
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
    code_bytes: int
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
    timestamp: str = ""


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


GITHUB_API_HOST = "api.github.com"
_NEXT_LINK_RE = re.compile(r'<([^>]+)>;\s*rel="next"')
_REQ_PKG_RE = re.compile(r"^\s*([a-z0-9][a-z0-9._-]*)")


class _SafeGitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow redirects only within https://api.github.com to prevent SSRF/token leaks."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        resolved = urllib.parse.urljoin(req.full_url, newurl)
        if not _is_allowed_api_url(resolved):
            raise urllib.error.HTTPError(
                resolved, code, "Blocked redirect outside api.github.com", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, resolved)


_OPENER = urllib.request.build_opener(_SafeGitHubRedirectHandler)


def _is_allowed_api_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() == GITHUB_API_HOST


def _api_request(url: str, token: str = "") -> tuple[dict | list | None, str | None]:
    """Fetch JSON and optional next-page Link URL from GitHub REST API."""
    if not _is_allowed_api_url(url):
        return None, None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rafifnurfariz-crt-profile",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with _OPENER.open(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            link_header = resp.headers.get("Link") or ""
            match = _NEXT_LINK_RE.search(link_header)
            next_url = match.group(1) if match and _is_allowed_api_url(match.group(1)) else None
            return data, next_url
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        http.client.HTTPException,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None, None


def api_get(url: str, token: str = "") -> dict | list | None:
    """Fetch JSON from GitHub REST API, returning None on HTTP or decode errors."""
    data, _ = _api_request(url, token)
    return data


def _api_get_paginated_list(url: str, token: str = "", max_pages: int = 5) -> list | None:
    """Fetch a paginated JSON list from GitHub REST API."""
    items: list = []
    next_url: str | None = url
    pages = 0
    while next_url and pages < max_pages:
        data, next_url = _api_request(next_url, token)
        if not isinstance(data, list):
            return items if pages > 0 else None
        items.extend(data)
        pages += 1
    return items


def get_file_text(owner: str, repo: str, path: str, token: str = "") -> str:
    """Read a repository file via GitHub Contents API."""
    q_owner = urllib.parse.quote(owner, safe="")
    q_repo = urllib.parse.quote(repo, safe="")
    q_path = urllib.parse.quote(path, safe="/")
    data = api_get(f"https://api.github.com/repos/{q_owner}/{q_repo}/contents/{q_path}", token)
    if isinstance(data, dict) and data.get("encoding") == "base64":
        content = data.get("content")
        if isinstance(content, str) and content:
            try:
                return base64.b64decode(content).decode("utf-8", errors="ignore")
            except (ValueError, TypeError):
                return ""
    return ""


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_commit_series(commit_dts: list[datetime], now: datetime, days: int = 14) -> tuple[list[int], int]:
    if days <= 0:
        return [], 0
    buckets = [0] * days
    today = _to_utc(now).date()
    for dt in commit_dts:
        delta = (today - _to_utc(dt).date()).days
        if 0 <= delta < days:
            buckets[days - 1 - delta] += 1
    return buckets, sum(buckets)


def _parse_requirements_packages(req_raw: str) -> set[str]:
    """Extract normalized package names from requirements.txt, ignoring comments."""
    pkgs: set[str] = set()
    for raw_line in req_raw.splitlines():
        line = raw_line.split("#", 1)[0].strip().lower()
        if not line or line.startswith(("-", "git+", "http://", "https://")):
            continue
        match = _REQ_PKG_RE.match(line)
        if match:
            pkgs.add(match.group(1).replace("_", "-"))
    return pkgs


def _extract_commit_first_line(commit_obj: dict) -> str:
    raw_msg = commit_obj.get("message")
    if not isinstance(raw_msg, str):
        return ""
    for line in raw_msg.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return ""


def collect_telemetry(username: str, token: str = "") -> ProfileTelemetry:
    """Gather GitHub user, repo, language, stack, commit, and event telemetry."""
    clean_user = str(username).strip()
    if not clean_user or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", clean_user):
        raise ValueError(f"Invalid GitHub username: {username!r}")

    q_user = urllib.parse.quote(clean_user, safe="")
    token = token or os.environ.get("GITHUB_TOKEN", "")
    now = datetime.now(timezone.utc)

    user_data = api_get(f"https://api.github.com/users/{q_user}", token)
    repos_data = _api_get_paginated_list(
        f"https://api.github.com/users/{q_user}/repos?per_page=100&type=owner&sort=updated",
        token,
    )
    if not isinstance(user_data, dict) or not isinstance(repos_data, list):
        raise RuntimeError(f"Failed to fetch GitHub profile or repositories for {clean_user}")

    created_dt = _parse_iso(user_data.get("created_at")) or now
    uptime_days = max(1, (now - created_dt).days)

    lang_bytes: dict[str, int] = {}
    stacks: list[str] = []
    repo_rows: list[tuple[str, RepoSummary]] = []
    total_stars = 0
    total_forks = 0
    homepage = (user_data.get("blog") or "").strip()

    def add_stack(label: str) -> None:
        if label not in stacks:
            stacks.append(label)

    for repo in repos_data:
        if not isinstance(repo, dict) or repo.get("fork"):
            continue
        name = str(repo.get("name") or "").strip()
        if not name:
            continue
        q_repo = urllib.parse.quote(name, safe="")
        is_profile = name.lower() == clean_user.lower()
        stars = max(0, int(repo.get("stargazers_count") or 0))
        forks = max(0, int(repo.get("forks_count") or 0))
        total_stars += stars
        total_forks += forks

        repo_home = (repo.get("homepage") or "").strip()
        if repo_home and not homepage:
            homepage = repo_home

        lang_url = repo.get("languages_url")
        if not isinstance(lang_url, str) or not _is_allowed_api_url(lang_url):
            lang_url = f"https://api.github.com/repos/{q_user}/{q_repo}/languages"
        langs = api_get(lang_url, token)
        repo_code_bytes = 0
        if isinstance(langs, dict):
            for lang, b_count in langs.items():
                if isinstance(lang, str) and isinstance(b_count, (int, float)) and not isinstance(b_count, bool):
                    val = int(b_count)
                    if val > 0:
                        repo_code_bytes += val
                        lang_bytes[lang] = lang_bytes.get(lang, 0) + val

        for topic in repo.get("topics") or []:
            if not isinstance(topic, str):
                continue
            mapped = TOPIC_DETECT.get(topic.lower())
            if mapped:
                add_stack(mapped)

        if not is_profile:
            pkg_raw = get_file_text(clean_user, name, "package.json", token)
            if pkg_raw:
                try:
                    pkg = json.loads(pkg_raw)
                    if isinstance(pkg, dict):
                        deps: dict[str, object] = {}
                        for dep_key in ("dependencies", "devDependencies"):
                            section = pkg.get(dep_key)
                            if isinstance(section, dict):
                                deps.update(section)
                        for key, label in PKG_DETECT:
                            if key in deps:
                                add_stack(label)
                except (ValueError, TypeError):
                    pass

            req_raw = get_file_text(clean_user, name, "requirements.txt", token)
            if req_raw:
                req_pkgs = _parse_requirements_packages(req_raw)
                for key, label in PY_DETECT:
                    if key.replace("_", "-") in req_pkgs:
                        add_stack(label)

        pushed_dt = _parse_iso(repo.get("pushed_at"))
        pushed_str = pushed_dt.strftime("%Y-%m-%d") if pushed_dt else "-"
        pushed_sort = pushed_dt.isoformat() if pushed_dt else ""
        repo_rows.append(
            (
                pushed_sort,
                RepoSummary(
                    name=name,
                    description=(repo.get("description") or "").strip(),
                    language=repo.get("language") or "Mixed",
                    size_kb=max(0, int(repo.get("size") or 0)),
                    code_bytes=repo_code_bytes,
                    stars=stars,
                    forks=forks,
                    pushed_at=pushed_str,
                    homepage=repo_home,
                    is_profile_repo=is_profile,
                ),
            )
        )

    # Prefer project repositories ahead of the profile repo, then stars, then most recently pushed
    repo_rows.sort(key=lambda item: (not item[1].is_profile_repo, item[1].stars, item[0]), reverse=True)
    repo_summaries = [item[1] for item in repo_rows]

    sorted_langs = sorted(lang_bytes.items(), key=lambda item: item[1], reverse=True)
    for lang_name, _ in sorted_langs[:3]:
        if lang_name in ("TypeScript", "Python", "JavaScript", "Go", "Rust"):
            add_stack(lang_name)

    since_iso = (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_commits: list[CommitEntry] = []
    commit_dts: list[datetime] = []
    seen_commit_ids: set[tuple[str, str]] = set()

    def _ingest_commits(repo_name: str, commits_list: list) -> int:
        added = 0
        for c in commits_list:
            if not isinstance(c, dict):
                continue
            commit_obj = c.get("commit") if isinstance(c.get("commit"), dict) else {}
            msg = _extract_commit_first_line(commit_obj)
            if "[skip ci]" in msg.lower():
                continue
            full_sha = str(c.get("sha") or "")
            short_sha = full_sha[:7]
            dedup_key = (repo_name, full_sha or f"{msg}:{commit_obj}")
            if dedup_key in seen_commit_ids:
                continue
            seen_commit_ids.add(dedup_key)

            author_obj = commit_obj.get("author") if isinstance(commit_obj.get("author"), dict) else {}
            committer_obj = commit_obj.get("committer") if isinstance(commit_obj.get("committer"), dict) else {}
            raw_date = author_obj.get("date") or committer_obj.get("date") or ""
            c_dt = _parse_iso(raw_date)
            if c_dt:
                commit_dts.append(c_dt)
            all_commits.append(
                CommitEntry(
                    sha=short_sha,
                    repo=repo_name,
                    message=msg or "(no commit message)",
                    date=c_dt.strftime("%Y-%m-%d") if c_dt else "-",
                    timestamp=c_dt.isoformat() if c_dt else "",
                )
            )
            added += 1
        return added

    for repo_sum in repo_summaries:
        q_repo = urllib.parse.quote(repo_sum.name, safe="")
        commits = _api_get_paginated_list(
            f"https://api.github.com/repos/{q_user}/{q_repo}/commits?since={since_iso}&per_page=100",
            token,
        )
        added_recent = _ingest_commits(repo_sum.name, commits) if isinstance(commits, list) else 0
        if added_recent == 0:
            fallback = api_get(
                f"https://api.github.com/repos/{q_user}/{q_repo}/commits?per_page=20",
                token,
            )
            if isinstance(fallback, list):
                _ingest_commits(repo_sum.name, fallback)

    all_commits.sort(key=lambda c: c.timestamp or c.date, reverse=True)

    # Pick latest commit per repository first so one busy repo doesn't hide other projects
    recent_commits: list[CommitEntry] = []
    seen_repos: set[str] = set()
    chosen_keys: set[tuple[str, str]] = set()
    for c in all_commits:
        if c.repo not in seen_repos:
            seen_repos.add(c.repo)
            chosen_keys.add((c.repo, c.sha))
            recent_commits.append(c)
    for c in all_commits:
        if len(recent_commits) >= 3:
            break
        key = (c.repo, c.sha)
        if key not in chosen_keys:
            chosen_keys.add(key)
            recent_commits.append(c)
    recent_commits.sort(key=lambda c: c.timestamp or c.date, reverse=True)

    push_series, recent_push_count = _build_commit_series(commit_dts, now)

    resolved_login = (user_data.get("login") or "").strip() or clean_user
    display_name = (user_data.get("name") or "").strip() or resolved_login
    location = (user_data.get("location") or "").strip() or "Indonesia"
    raw_public_repos = user_data.get("public_repos")
    public_repos = (
        max(0, raw_public_repos)
        if isinstance(raw_public_repos, int) and not isinstance(raw_public_repos, bool)
        else len(repo_summaries)
    )

    return ProfileTelemetry(
        username=resolved_login,
        display_name=display_name,
        bio=(user_data.get("bio") or "").strip(),
        location=location,
        homepage=homepage,
        created_at=created_dt.strftime("%Y-%m-%d"),
        uptime_days=uptime_days,
        public_repos=public_repos,
        followers=max(0, int(user_data.get("followers") or 0)),
        following=max(0, int(user_data.get("following") or 0)),
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
            RepoSummary("Photopip", "Photo editor web app", "TypeScript", 10285, 371870, 0, 0, "2026-11-24", "https://photopip.vercel.app", False),
            RepoSummary(username, "Personal GitHub profile", "Python", 217, 16254, 0, 0, "2026-11-28", "", True),
        ],
        recent_commits=[
            CommitEntry("f05af98", username, "style: add smooth entrance animations across CRT SVGs", "2026-11-28", "2026-11-28T12:39:23+00:00"),
            CommitEntry("f2c8ccc", "Photopip", "fix: sinkronisasi teks kosong, font kustom, handle resize", "2026-11-24", "2026-11-24T04:42:44+00:00"),
        ],
        push_series=[0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 5, 6, 0, 0],
        recent_push_count=15,
        synced_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M UTC"),
    )
