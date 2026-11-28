"""Syncs GitHub Blue CRT BIOS and GitHub stats SVGs from GitHub API."""
from __future__ import annotations

import argparse
from pathlib import Path

from crt_svg import render_bios_terminal, render_btop_telemetry, render_cli_button
from github_stats import build_sample_telemetry, collect_telemetry

REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_DIR = REPO_ROOT / "media" / "svg"

CLI_ENDPOINTS = [
    ("btn_repos.svg", "GitHub Repos", "github"),
    ("btn_ig.svg", "Instagram @rapip1241", "instagram"),
    ("btn_tt.svg", "TikTok @rapip1241", "tiktok"),
]


def generate_all(username: str, offline: bool = False, out_dir: Path = SVG_DIR) -> None:
    telemetry = build_sample_telemetry(username) if offline else collect_telemetry(username)

    rendered: list[tuple[str, str]] = [
        ("crt_bios.svg", render_bios_terminal(telemetry)),
        ("btop_telemetry.svg", render_btop_telemetry(telemetry)),
    ]
    for idx, (filename, label, icon) in enumerate(CLI_ENDPOINTS):
        rendered.append((filename, render_cli_button(label, icon, delay_s=idx * 0.06)))

    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, svg_content in rendered:
        (out_dir / filename).write_text(svg_content, encoding="utf-8")

    print(
        f"Synced GitHub Blue CRT profile for {telemetry.username}: "
        f"repos={telemetry.public_repos}, langs={[l for l, _ in telemetry.languages]}, "
        f"stacks={telemetry.stacks}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GitHub Blue CRT profile SVGs.")
    parser.add_argument("username", nargs="?", default="rafifnurfariz", help="GitHub username")
    parser.add_argument("--offline", action="store_true", help="Use offline sample fixture instead of API")
    args = parser.parse_args()
    generate_all(args.username, offline=args.offline)


if __name__ == "__main__":
    main()
