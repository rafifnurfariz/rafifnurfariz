"""Tests for GitHub Blue CRT profile generators, Pac-Man theming, and security."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crt_svg import (
    clamp_text,
    fmt_bytes,
    fmt_repo_kb,
    fmt_uptime,
    render_bios_terminal,
    render_btop_telemetry,
    render_cli_button,
)
from github_stats import (
    _api_get_paginated_list,
    _build_commit_series,
    _is_allowed_api_url,
    _parse_iso,
    _parse_requirements_packages,
    api_get,
    build_sample_telemetry,
    collect_telemetry,
    get_file_text,
)
from theme_pacman import process_directory, theme_pacman_svg

HAS_MEDIA_DEPS = all(importlib.util.find_spec(pkg) is not None for pkg in ("PIL", "numpy", "scipy"))


class CrtSvgTests(unittest.TestCase):
    def test_svgs_are_valid_xml_play_once_and_hide_external_deploy_url(self) -> None:
        t = build_sample_telemetry("rafifnurfariz")
        bios = render_bios_terminal(t)
        btop = render_btop_telemetry(t)
        btn_gh = render_cli_button("GitHub Repos", "github")
        btn_ig = render_cli_button("Instagram @rapip1241", "instagram")
        btn_tt = render_cli_button("TikTok @rapip1241", "tiktok")

        for svg in (bios, btop, btn_gh, btn_ig, btn_tt):
            root = ET.fromstring(svg)
            self.assertTrue(root.tag.endswith("svg"))
            self.assertNotIn("photopip.vercel.app", svg)

        self.assertIn("#f0f6fc", btn_gh)
        self.assertIn("ig-btn", btn_ig)
        self.assertIn("#FE2C55", btn_tt)

        for required in ("#0d1117", "#58a6ff", "prefers-reduced-motion:reduce"):
            self.assertIn(required, bios)
            self.assertIn(required, btop)

        self.assertIn("whoami", bios)
        self.assertNotIn("RAFIF-BIOS", bios)
        self.assertNotIn("bios-phase", bios)
        self.assertIn("crt-breathe", bios)
        self.assertIn("bar-grow", btop)
        self.assertIn("pulse-bar", btop)
        self.assertIn("ico-float", btn_ig)
        self.assertIn("TOP LANGUAGES &amp; TOOLS", btop)
        self.assertNotIn("PROJECTS &amp; RECENT UPDATES", btop)
        self.assertEqual(ET.fromstring(btop).attrib["height"], "284")
        self.assertNotIn('<g clip-path="url(#btop-scr)" class="in">', btop)
        self.assertIn('<g clip-path="url(#btop-scr)">\n<g class="in">', btop)

    def test_readme_order_and_no_website_links(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("photopip.vercel.app", readme)
        self.assertNotIn("btn_web.svg", readme)

        pos_bios = readme.index("media/svg/crt_bios.svg")
        pos_cur = readme.index("media/svg/currents_crt.svg")
        pos_cow = readme.index("media/images/polish-cow-crt.gif")
        pos_ig = readme.index("media/svg/btn_ig.svg")
        pos_stats = readme.index("media/svg/btop_telemetry.svg")
        pos_pacman = readme.index("pacman-contribution-graph-dark.svg")
        self.assertTrue(pos_bios < pos_cur < pos_cow < pos_ig < pos_stats < pos_pacman)

    def test_escapes_xml_special_characters_strips_control_chars_and_clamps(self) -> None:
        t = build_sample_telemetry("rafifnurfariz")
        t.display_name = 'Rafif\x00 <Dev>\x1b[31m & "Code"'
        t.stacks = ["Next.js", "C&C++\x0c", "<Tag>"]
        bios = render_bios_terminal(t)
        btop = render_btop_telemetry(t)
        btn = render_cli_button("Click\x00\x1bMe", "github", delay_s=-1.0)
        for svg in (bios, btop, btn):
            ET.fromstring(svg)

        self.assertIn("Rafif &lt;Dev&gt;[31m &amp; &quot;Code&quot;", bios)
        self.assertIn("C&amp;C++", btop)
        self.assertLessEqual(len(clamp_text("a" * 80, 58)), 58)
        self.assertEqual(clamp_text("abcdef", 3), "abc")
        self.assertEqual(clamp_text("abcdef", 2), "ab")
        self.assertEqual(clamp_text("abcdef", 0), "")

    def test_formatting_and_zero_or_invalid_numeric_edge_cases(self) -> None:
        self.assertEqual(fmt_bytes(0), "0.0 KB")
        self.assertEqual(fmt_bytes(-50), "0.0 KB")
        self.assertEqual(fmt_bytes(float("nan")), "0.0 KB")  # type: ignore[arg-type]
        self.assertEqual(fmt_bytes(50), "0.1 KB")
        self.assertEqual(fmt_bytes(2_097_152), "2.0 MB")
        self.assertEqual(fmt_bytes(2_147_483_648), "2.0 GB")
        self.assertEqual(fmt_repo_kb(-5), "0 KB")
        self.assertEqual(fmt_uptime(-10), "0d")

        t = build_sample_telemetry("emptyuser")
        t.repos = []
        t.public_repos = -1
        t.total_bytes = 0
        t.languages = [("Python", 2048)]
        t.push_series = [1, -2, 5]
        t.synced_at = "2027-02-01 00:15 UTC"
        bios = render_bios_terminal(t)
        btop = render_btop_telemetry(t)
        ET.fromstring(bios)
        ET.fromstring(btop)
        self.assertIn("(c) 2027", bios)
        self.assertIn("00 public repositories", bios)
        self.assertNotIn("e.g. emptyuser", bios)
        self.assertIn("100.0%", btop)
        self.assertIn("peak 5/d", btop)

    def test_theme_pacman_svg_edge_cases_and_directory_validation(self) -> None:
        # Prolog + comment + viewBox-only + reordered bg rect + 8-digit hex + sibling <g>
        sample = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<!-- upstream comment -->\n"
            '<svg viewBox="0 0 1166 184" xmlns="http://www.w3.org/2000/svg">'
            '<rect fill="#0d1117" height="100%" width="100%"/>'
            '<g class="pac-in"><rect fill="#ffffff"/><rect fill="#ffffff80"/></g>'
            '<g><rect fill="#0e4429"/><rect fill="#006d32"/><rect fill="#26a641"/><rect fill="#39d353"/></g>'
            "</svg>"
        )
        themed = theme_pacman_svg(sample, dark=True)
        root = ET.fromstring(themed)
        self.assertEqual(root.attrib["data-crt-blue"], "2")
        self.assertEqual((root.attrib["width"], root.attrib["height"]), ("860", "196"))
        for old_color in ("#0e4429", "#006d32", "#26a641", "#39d353"):
            self.assertNotIn(old_color, themed)
        for new_blue in ("#0c2d6b", "#1f6feb", "#58a6ff", "#79c0ff", "#388bfd"):
            self.assertIn(new_blue, themed)
        # 8-digit hex must not be corrupted by 6-digit #ffffff remap
        self.assertIn("#ffffff80", themed)
        # Bezel stroke drawn cleanly without overwrite
        self.assertIn('fill="none" stroke="#30363d"', themed)
        self.assertEqual(theme_pacman_svg(themed, dark=True), themed)

        # Light mode with XML prolog stays valid XML
        light_sample = '<?xml version="1.0"?><svg width="1166" height="184" xmlns="http://www.w3.org/2000/svg"><rect fill="#30a14e"/></svg>'
        light_themed = theme_pacman_svg(light_sample, dark=False)
        ET.fromstring(light_themed)
        self.assertIn("#0969da", light_themed)

        # Tall SVG must constrain height so ty >= 42.0 (never overflows into title bar)
        tall_sample = '<svg width="400" height="400" xmlns="http://www.w3.org/2000/svg"><rect fill="#39d353"/></svg>'
        tall_themed = theme_pacman_svg(tall_sample, dark=True)
        ET.fromstring(tall_themed)
        m = re.search(r'translate\(([\d.-]+),([\d.-]+)\)', tall_themed)
        assert m is not None
        self.assertGreaterEqual(float(m.group(2)), 42.0)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            with self.assertRaises(RuntimeError):
                process_directory(tmp_dir)
            (tmp_dir / "broken-dark.svg").write_text("<svg><unclosed></svg>", encoding="utf-8")
            with self.assertRaises(ET.ParseError):
                process_directory(tmp_dir)

    def test_github_stats_security_parsing_pagination_and_fallback(self) -> None:
        for bad_url in (
            "http://api.github.com/users/rafifnurfariz",
            "https://evil.example.com/users/rafifnurfariz",
            "https://api.github.com:8443/users/rafifnurfariz",
            "https://api.github.com:notaport/users/rafifnurfariz",
            "https://user:pass@api.github.com/users/rafifnurfariz",
            "file:///etc/passwd",
        ):
            self.assertFalse(_is_allowed_api_url(bad_url), bad_url)
            self.assertIsNone(api_get(bad_url, token="secret"))

        self.assertEqual(get_file_text("owner", "repo", "../secrets"), "")

        with self.assertRaises(ValueError):
            collect_telemetry("../evil?x=1")

        # Self-referential Link next URL must terminate after 1 fetch without duplicating items
        calls = 0

        def looping_request(url: str, token: str = ""):
            nonlocal calls
            calls += 1
            return [{"id": 1}], url

        with mock.patch("github_stats._api_request", side_effect=looping_request):
            items = _api_get_paginated_list("https://api.github.com/users/x/repos")
        self.assertEqual(calls, 1)
        self.assertEqual(items, [{"id": 1}])

        pkgs = _parse_requirements_packages(
            "# django==4.2\nmy-flask-helper==1.0\nPillow>=10.0 # image lib\nrequests[socks]==2.31\n"
        )
        self.assertIn("pillow", pkgs)
        self.assertIn("requests", pkgs)
        self.assertNotIn("django", pkgs)
        self.assertNotIn("flask", pkgs)

        # Timezone normalization and naive datetime handling
        dt_plus7 = _parse_iso("2026-11-28T19:00:00+07:00")
        dt_utc = _parse_iso("2026-11-28T15:00:00Z")
        dt_naive = _parse_iso("2026-11-28T10:00:00")
        assert dt_plus7 and dt_utc and dt_naive
        self.assertLess(dt_plus7.isoformat(), dt_utc.isoformat())
        self.assertEqual(dt_naive.tzinfo, timezone.utc)

        now = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)
        series, total = _build_commit_series([dt_naive, dt_plus7], now, days=14)
        self.assertEqual(len(series), 14)
        self.assertEqual(total, 2)
        self.assertEqual(series[-1], 2)

        # Mock API: malformed types, empty 14-day list fallback, and empty commit message
        def fake_api_request(url: str, token: str = ""):
            if url.endswith("/users/tester"):
                return {
                    "login": "tester",
                    "name": "   ",
                    "blog": 12345,
                    "followers": "bad",
                    "created_at": "2025-01-01T00:00:00Z",
                    "public_repos": 1,
                }, None
            if "/repos?" in url:
                return [
                    {
                        "name": "demo",
                        "fork": False,
                        "stargazers_count": True,
                        "forks_count": None,
                        "size": 12,
                        "pushed_at": "2026-10-01T00:00:00Z",
                        "languages_url": "https://evil.example/leak",
                    }
                ], None
            if url.endswith("/repos/tester/demo/languages"):
                return {"Python": 1024}, None
            if "/contents/package.json" in url:
                return {"encoding": "base64", "content": "eyJkZXBlbmRlbmNpZXMiOiBudWxsLCAiZGV2RGVwZW5kZW5jaWVzIjogeyJ2aXRlIjogIjUuMCJ9fQ=="}, None
            if "/contents/requirements.txt" in url:
                return None, None
            if "/commits?since=" in url:
                return [], None
            if "/commits?per_page=20" in url:
                return [
                    {"sha": "1111111aaaa", "commit": {"message": "", "author": {"date": "2026-10-01T19:00:00+07:00"}}},
                    {"sha": "2222222bbbb", "commit": {"message": "real newer commit", "author": {"date": "2026-10-01T15:00:00Z"}}},
                ], None
            return None, None

        with mock.patch("github_stats._api_request", side_effect=fake_api_request):
            tel = collect_telemetry("tester", token="tok")
        self.assertEqual(tel.display_name, "tester")
        self.assertEqual(tel.total_stars, 0)
        self.assertIn("Vite", tel.stacks)
        self.assertEqual(len(tel.recent_commits), 2)
        self.assertEqual(tel.recent_commits[0].sha, "2222222")
        self.assertEqual(tel.recent_commits[1].message, "(no commit message)")

    def test_workflows_are_hardened(self) -> None:
        sync_wf = (ROOT / ".github/workflows/profile-sync.yml").read_text(encoding="utf-8")
        self.assertNotIn("sync_profile.py ${{", sync_wf)
        self.assertIn("concurrency:", sync_wf)
        self.assertIn("timeout-minutes:", sync_wf)
        self.assertIn("[skip ci]", sync_wf)

        pac_wf = (ROOT / ".github/workflows/contrib-pacman.yml").read_text(encoding="utf-8")
        self.assertIn("concurrency:", pac_wf)
        self.assertIn("persist-credentials: false", pac_wf)
        self.assertNotIn("x-access-token:${{", pac_wf)
        self.assertIn("if-no-files-found: error", pac_wf)

    @unittest.skipUnless(HAS_MEDIA_DEPS, "Requires Pillow, NumPy, and SciPy")
    def test_media_crt_currents_and_polish_cow_generators(self) -> None:
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        from ascii_art import _build_spans, render_currents_crt
        from cow_crt import _draw_text_right, render_cow_crt

        spans = _build_spans(np.array([-0.5, float("nan"), 0.5, 1.5]), 10.0, 0.0, 3.5)
        self.assertEqual(len(spans), 2)

        canvas = Image.new("RGBA", (100, 30))
        _draw_text_right(ImageDraw.Draw(canvas), 90, 5, "OK", ImageFont.load_default(), (88, 166, 255))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cur_out = tmp_dir / "currents_crt.svg"
            cow_out = tmp_dir / "polish-cow-crt.gif"

            svg = render_currents_crt(ROOT / "media/images/currents-cover.jpg", cur_out)
            root = ET.fromstring(svg)
            self.assertEqual((root.attrib["width"], root.attrib["height"]), ("350", "356"))
            self.assertIn("Currents", svg)
            self.assertIn("#58a6ff", svg)

            for dims in ((1000, 2), (1, 1)):
                edge_img = tmp_dir / f"edge_{dims[0]}x{dims[1]}.png"
                Image.new("RGB", dims, (180, 180, 180)).save(edge_img)
                ET.fromstring(render_currents_crt(edge_img, tmp_dir / f"edge_{dims[0]}x{dims[1]}.svg"))

            gif_path = render_cow_crt(ROOT / "media/images/mood-cow.webp", cow_out)
            with Image.open(gif_path) as im:
                self.assertEqual(im.size, (350, 356))
                self.assertEqual(im.n_frames, 20)


if __name__ == "__main__":
    unittest.main()
