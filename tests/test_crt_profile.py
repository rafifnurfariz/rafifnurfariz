"""Tests for GitHub Blue CRT profile generators."""
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
from github_stats import build_sample_telemetry

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

    def test_escapes_xml_special_characters_and_clamps_long_text(self) -> None:
        t = build_sample_telemetry("rafifnurfariz")
        t.display_name = 'Rafif <Dev> & "Code"'
        t.stacks = ["Next.js", "C&C++", "<Tag>"]
        bios = render_bios_terminal(t)
        btop = render_btop_telemetry(t)
        ET.fromstring(bios)
        ET.fromstring(btop)
        self.assertIn("Rafif &lt;Dev&gt; &amp; &quot;Code&quot;", bios)
        self.assertIn("C&amp;C++", btop)
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
            self.assertEqual((root.attrib["width"], root.attrib["height"]), ("350", "356"))
            self.assertIn("Currents", svg)
            self.assertIn("#58a6ff", svg)

            gif_path = render_cow_crt(ROOT / "media/images/mood-cow.webp", cow_out)
            with Image.open(gif_path) as im:
                self.assertEqual(im.size, (350, 356))
                self.assertEqual(im.n_frames, 20)


if __name__ == "__main__":
    unittest.main()
