"""Tests for Retro CRT Amber profile generators."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crt_svg import clamp_text, render_bios_terminal, render_btop_telemetry, render_cli_button
from github_stats import CommitEntry, build_sample_telemetry

HAS_MEDIA_DEPS = all(importlib.util.find_spec(pkg) is not None for pkg in ("PIL", "numpy", "scipy"))


class CrtSvgTests(unittest.TestCase):
    def test_svgs_are_valid_xml_play_once_and_hide_external_deploy_url(self) -> None:
        t = build_sample_telemetry("rafifnurfariz")
        bios = render_bios_terminal(t)
        btop = render_btop_telemetry(t)
        btn = render_cli_button("Instagram @rapip1241")

        for svg in (bios, btop, btn):
            root = ET.fromstring(svg)
            self.assertTrue(root.tag.endswith("svg"))
            self.assertNotIn("photopip.vercel.app", svg)

        for required in ("#121212", "#ffb000", "prefers-reduced-motion:reduce"):
            self.assertIn(required, bios)
            self.assertIn(required, btop)

        self.assertIn("RAFIF-BIOS", bios)
        self.assertIn("whoami", bios)
        self.assertIn("bios-exit 0.35s ease 6.00s forwards", bios)
        self.assertNotIn(".bios-phase{animation:kf-bios-phase", bios)
        self.assertIn("TOP LANGUAGES &amp; TOOLS", btop)
        self.assertIn("Photopip", btop)

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

    def test_escapes_xml_special_characters_and_clamps_long_messages(self) -> None:
        t = build_sample_telemetry("rafifnurfariz")
        t.recent_commits = [
            CommitEntry(
                sha="abc1234",
                repo="Repo&<Test>",
                message='feat: handle <tag> & "quotes" ' + ("x" * 100),
                date="2026-11-28",
            )
        ]
        btop = render_btop_telemetry(t)
        ET.fromstring(btop)
        self.assertIn("&lt;tag&gt; &amp; &quot;quotes&quot;", btop)
        self.assertLessEqual(len(clamp_text("a" * 80, 58)), 58)

    @unittest.skipUnless(HAS_MEDIA_DEPS, "Requires Pillow, NumPy, and SciPy")
    def test_media_crt_currents_and_polish_cow_generators(self) -> None:
        from PIL import Image
        from ascii_art import render_currents_crt
        from cow_crt import render_cow_crt

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cur_out = tmp_dir / "currents_crt.svg"
            cow_out = tmp_dir / "polish-cow-crt.gif"

            svg = render_currents_crt(ROOT / "media/images/currents-cover.jpg", cur_out)
            root = ET.fromstring(svg)
            self.assertEqual((root.attrib["width"], root.attrib["height"]), ("424", "432"))
            self.assertIn("Tame Impala - Currents", svg)
            self.assertIn("#ffb000", svg)

            gif_path = render_cow_crt(ROOT / "media/images/mood-cow.webp", cow_out)
            with Image.open(gif_path) as im:
                self.assertEqual(im.size, (424, 432))
                self.assertEqual(im.n_frames, 20)


if __name__ == "__main__":
    unittest.main()
