"""Tests for GitHub Blue CRT profile generators and telemetry collectors."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
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
    render_bios_terminal,
    render_btop_telemetry,
    render_cli_button,
)
from github_stats import (
    CommitEntry,
    _build_commit_series,
    _parse_iso,
    _parse_requirements_packages,
    api_get,
    build_sample_telemetry,
    collect_telemetry,
)

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
        self.assertIn("Photopip", btop)
        self.assertIn("363.2 KB", btop)
        self.assertIn("[rafifnurfariz]", btop)
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
        self.assertTrue(pos_bios < pos_cur < pos_cow < pos_ig < pos_stats)

    def test_escapes_xml_special_characters_strips_control_chars_and_clamps(self) -> None:
        t = build_sample_telemetry("rafifnurfariz")
        t.display_name = "Rapi\x00iipp\x1b[31m"
        t.recent_commits = [
            CommitEntry(
                sha="abc1234567890",
                repo="Repo&<Test>\x0c",
                message='feat: handle \x1b[32m<tag>\x00 & "quotes" ' + ("x" * 100),
                date="2026-11-28",
            )
        ]
        bios = render_bios_terminal(t)
        btop = render_btop_telemetry(t)
        btn = render_cli_button("Click\x00\x1bMe", "github", delay_s=-1.0)
        for svg in (bios, btop, btn):
            ET.fromstring(svg)

        self.assertIn("&lt;tag&gt; &amp; &quot;quotes&quot;", btop)
        self.assertIn(">abc1234<", btop)
        self.assertLessEqual(len(clamp_text("a" * 80, 58)), 58)
        self.assertEqual(clamp_text("abcdef", 3), "abc")
        self.assertEqual(clamp_text("abcdef", 2), "ab")
        self.assertEqual(clamp_text("abcdef", 0), "")

    def test_formatting_and_zero_repo_edge_cases(self) -> None:
        self.assertEqual(fmt_bytes(0), "0.0 KB")
        self.assertEqual(fmt_bytes(-50), "0.0 KB")
        self.assertEqual(fmt_bytes(50), "0.1 KB")
        self.assertEqual(fmt_bytes(2_097_152), "2.0 MB")
        self.assertEqual(fmt_bytes(2_147_483_648), "2.0 GB")

        t = build_sample_telemetry("emptyuser")
        t.repos = []
        t.public_repos = 0
        t.total_bytes = 0
        t.languages = []
        t.push_series = [1, -2, 5]
        t.synced_at = "2027-02-01 00:15 UTC"
        bios = render_bios_terminal(t)
        btop = render_btop_telemetry(t)
        ET.fromstring(bios)
        ET.fromstring(btop)
        self.assertIn("(c) 2027", bios)
        self.assertNotIn("e.g. emptyuser", bios)
        self.assertIn("0.0 KB", btop)
        self.assertIn("peak 5/d", btop)

    def test_github_stats_security_parsing_and_fallback(self) -> None:
        self.assertIsNone(api_get("http://api.github.com/users/rafifnurfariz"))
        self.assertIsNone(api_get("https://evil.example.com/users/rafifnurfariz", token="secret"))
        self.assertIsNone(api_get("file:///etc/passwd"))

        with self.assertRaises(ValueError):
            collect_telemetry("../evil?x=1")

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

        # Mock API: empty 14-day commit list must fall back to per_page=20, and empty message must not crash
        def fake_api_request(url: str, token: str = ""):
            if url.endswith("/users/tester"):
                return {
                    "login": "tester",
                    "name": "   ",
                    "created_at": "2025-01-01T00:00:00Z",
                    "public_repos": 1,
                }, None
            if "/repos?" in url:
                return [
                    {
                        "name": "demo",
                        "fork": False,
                        "stargazers_count": 0,
                        "forks_count": 0,
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
        self.assertIn("Vite", tel.stacks)
        self.assertEqual(len(tel.recent_commits), 2)
        self.assertEqual(tel.recent_commits[0].sha, "2222222")
        self.assertEqual(tel.recent_commits[1].message, "(no commit message)")

    def test_workflow_hardening(self) -> None:
        wf = (ROOT / ".github/workflows/profile-sync.yml").read_text(encoding="utf-8")
        self.assertNotIn("sync_profile.py ${{", wf)
        self.assertIn("concurrency:", wf)
        self.assertIn("timeout-minutes:", wf)
        self.assertIn("[skip ci]", wf)

    @unittest.skipUnless(HAS_MEDIA_DEPS, "Requires Pillow, NumPy, and SciPy")
    def test_media_crt_currents_and_polish_cow_generators(self) -> None:
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        from ascii_art import _build_spans, render_currents_crt
        from cow_crt import _draw_text_right, render_cow_crt

        # Out-of-bounds and NaN values must not crash or wrap negatively
        spans = _build_spans(np.array([-0.5, float("nan"), 0.5, 1.5]), 10.0, 0.0, 3.5)
        self.assertEqual(len(spans), 2)

        # Right-aligned text helper works even with bitmap fallback font
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

            # Extreme wide image must not crash with rows == 0
            wide_img = tmp_dir / "wide.png"
            Image.new("RGB", (1000, 2), (180, 180, 180)).save(wide_img)
            wide_svg = render_currents_crt(wide_img, tmp_dir / "wide.svg")
            ET.fromstring(wide_svg)

            gif_path = render_cow_crt(ROOT / "media/images/mood-cow.webp", cow_out)
            with Image.open(gif_path) as im:
                self.assertEqual(im.size, (350, 356))
                self.assertEqual(im.n_frames, 20)


if __name__ == "__main__":
    unittest.main()
