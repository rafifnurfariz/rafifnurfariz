"""Syncs Retro CRT Amber BIOS and GitHub stats SVGs from GitHub API."""
from __future__ import annotations

import argparse
from pathlib import Path

from crt_svg import render_bios_terminal, render_btop_telemetry, render_cli_button
from github_stats import build_sample_telemetry, collect_telemetry

SVG_DIR = Path("media/svg")

CLI_ENDPOINTS = [
    ("btn_repos.svg", "GitHub Repos", "github"),
    ("btn_ig.svg", "Instagram @rapip1241", "instagram"),
    ("btn_tt.svg", "TikTok @rapip1241", "tiktok"),
]


def generate_all(username: str, offline: bool = False) -> None:
    telemetry = build_sample_telemetry(username) if offline else collect_telemetry(username)

    SVG_DIR.mkdir(parents=True, exist_ok=True)
    (SVG_DIR / "crt_bios.svg").write_text(render_bios_terminal(telemetry), encoding="utf-8")
    (SVG_DIR / "btop_telemetry.svg").write_text(render_btop_telemetry(telemetry), encoding="utf-8")

    for idx, (filename, label, icon) in enumerate(CLI_ENDPOINTS):
        (SVG_DIR / filename).write_text(render_cli_button(label, icon, delay_s=idx * 0.06), encoding="utf-8")

    print(
        f"Synced CRT Amber profile for {telemetry.username}: "
        f"repos={telemetry.public_repos}, langs={[l for l, _ in telemetry.languages]}, "
        f"stacks={telemetry.stacks}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GitHub Retro CRT Amber SVGs.")
    parser.add_argument("username", nargs="?", default="rafifnurfariz", help="GitHub username")
    parser.add_argument("--offline", action="store_true", help="Use offline sample fixture instead of API")
    args = parser.parse_args()
    generate_all(args.username, offline=args.offline)


if __name__ == "__main__":
    main()
