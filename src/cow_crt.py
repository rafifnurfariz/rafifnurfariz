"""Converts mood-cow.webp into a Retro CRT Amber themed animated GIF (424x432)."""
from __future__ import annotations

import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageSequence
from scipy import ndimage

CHASSIS_BG = (12, 10, 8)
CHASSIS_STROKE = (51, 35, 8)
SCREEN_BG = (18, 18, 18)
SCREEN_BAR = (26, 21, 12)
SCREEN_STROKE = (77, 52, 8)
PANEL_DIVIDER = (41, 28, 6)

AMBER_BRIGHT = (255, 213, 79)
AMBER_CORE = (255, 176, 0)
AMBER_SOFT = (255, 232, 163)
AMBER_MID = (204, 136, 0)
AMBER_DIM = (122, 82, 0)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "C:/Windows/Fonts/consolab.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/consola.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _extract_cow_rgba(frame_rgba: Image.Image) -> Image.Image:
    """Remove exterior white background via border-connected component flood fill."""
    arr = np.asarray(frame_rgba.convert("RGBA"), dtype=np.uint8)
    rgb = arr[:, :, :3].astype(np.int16)
    alpha = arr[:, :, 3]

    bg_candidate = (alpha < 128) | ((rgb.min(axis=2) >= 216) & ((rgb.max(axis=2) - rgb.min(axis=2)) <= 26))
    labeled, _ = ndimage.label(bg_candidate)

    border_labels = set()
    border_labels.update(np.unique(labeled[0, :]).tolist())
    border_labels.update(np.unique(labeled[-1, :]).tolist())
    border_labels.update(np.unique(labeled[:, 0]).tolist())
    border_labels.update(np.unique(labeled[:, -1]).tolist())
    border_labels.discard(0)

    fg_mask = ~np.isin(labeled, list(border_labels))

    gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]) / 255.0
    stops = np.array([0.0, 0.25, 0.55, 0.82, 1.0])
    ramp_r = np.interp(gray, stops, [56, 118, 224, 255, 255])
    ramp_g = np.interp(gray, stops, [36, 76, 152, 206, 232])
    ramp_b = np.interp(gray, stops, [8, 12, 8, 60, 156])

    out = np.zeros_like(arr)
    out[:, :, 0] = np.clip(ramp_r, 0, 255).astype(np.uint8)
    out[:, :, 1] = np.clip(ramp_g, 0, 255).astype(np.uint8)
    out[:, :, 2] = np.clip(ramp_b, 0, 255).astype(np.uint8)
    out[:, :, 3] = np.where(fg_mask, 255, 0).astype(np.uint8)
    return Image.fromarray(out, mode="RGBA")


def _build_base_chassis(w: int, h: int, font_b: ImageFont.ImageFont, font_r: ImageFont.ImageFont) -> Image.Image:
    base = Image.new("RGBA", (w, h), (*CHASSIS_BG, 255))
    draw = ImageDraw.Draw(base)

    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=14, fill=CHASSIS_BG, outline=CHASSIS_STROKE, width=2)
    draw.rounded_rectangle([12, 12, w - 13, h - 13], radius=9, fill=SCREEN_BG, outline=SCREEN_STROKE, width=1)

    draw.rounded_rectangle([12, 12, w - 13, 42], radius=9, fill=SCREEN_BAR)
    draw.rectangle([12, 30, w - 13, 42], fill=SCREEN_BAR)
    draw.line([12, 42, w - 13, 42], fill=SCREEN_STROKE, width=1)

    draw.text((40, 21), "TTY4 // polish-cow.gif", font=font_b, fill=AMBER_CORE)
    draw.text((w - 28, 22), "128 BPM", font=font_r, fill=AMBER_MID, anchor="ra")

    draw.line([26, 392, w - 26, 392], fill=PANEL_DIVIDER, width=1)
    draw.text((28, 398), "> mood:", font=font_b, fill=AMBER_CORE)
    draw.text((84, 398), "polish_cow.gif", font=font_r, fill=AMBER_BRIGHT)
    return base


def _build_amber_palette(sample_rgb: Image.Image) -> Image.Image:
    """Create a deterministic shared 64-color Retro CRT Amber palette for GIF frames."""
    return sample_rgb.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def render_cow_crt(
    src_path: str | Path = "media/images/mood-cow.webp",
    out_path: str | Path = "media/images/polish-cow-crt.gif",
) -> Path:
    """Render Polish Cow frames inside a 424x432 Retro CRT Amber monitor GIF."""
    w, h = 424, 432
    font_b = _load_font(12, bold=True)
    font_r = _load_font(11, bold=False)

    base = _build_base_chassis(w, h, font_b, font_r)
    src = Image.open(src_path)

    scan = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    s_arr = np.asarray(scan, dtype=np.uint8).copy()
    s_arr[43 : h - 13 : 3, 13 : w - 13] = (0, 0, 0, 56)
    scan_overlay = Image.fromarray(s_arr, mode="RGBA")

    eq_heights = [
        [4, 9, 12, 7],
        [7, 13, 8, 10],
        [11, 6, 14, 9],
        [8, 11, 6, 13],
    ]

    raw_frames = [f.copy() for f in ImageSequence.Iterator(src)]
    total_f = max(1, len(raw_frames))
    rgb_frames: list[Image.Image] = []

    for idx, raw_frame in enumerate(raw_frames):
        cow = _extract_cow_rgba(raw_frame)
        scale = min(318 / cow.width, 266 / cow.height)
        nw, nh = round(cow.width * scale), round(cow.height * scale)
        cow_resized = cow.resize((nw, nh), Image.Resampling.LANCZOS)

        cx = (w - nw) // 2
        cy = 56 + (318 - nh) // 2

        canvas = base.copy()

        # Subtle warm amber phosphor rim glow around cow silhouette
        halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cow_alpha = cow_resized.getchannel("A")
        amber_fill = Image.new("RGBA", (nw, nh), (*AMBER_CORE, 255))
        amber_fill.putalpha(cow_alpha.point(lambda p: int(p * 0.22)))
        halo.paste(amber_fill, (cx, cy))
        halo = halo.filter(ImageFilter.GaussianBlur(radius=4))
        canvas = Image.alpha_composite(canvas, halo)

        cow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cow_layer.paste(cow_resized, (cx, cy), cow_resized)
        canvas = Image.alpha_composite(canvas, cow_layer)

        fdraw = ImageDraw.Draw(canvas)
        pulse = 0.5 + 0.5 * np.sin((idx / total_f) * 2 * np.pi)
        led_col = (
            int(175 + 80 * pulse),
            int(115 + 65 * pulse),
            0,
            255,
        )
        fdraw.ellipse([24, 23, 32, 31], fill=led_col)

        bars = eq_heights[idx % len(eq_heights)]
        for b_i, bh in enumerate(bars):
            bx = w - 98 + b_i * 6
            by = 411 - bh
            fdraw.rectangle([bx, by, bx + 4, 411], fill=(*AMBER_CORE, 235))
        fdraw.text((w - 28, 399), "[GIF]", font=font_r, fill=AMBER_DIM, anchor="ra")

        canvas = Image.alpha_composite(canvas, scan_overlay)
        rgb_frames.append(canvas.convert("RGB"))

    palette_ref = _build_amber_palette(rgb_frames[0])
    paletted_frames = [
        fr.quantize(palette=palette_ref, dither=Image.Dither.NONE)
        for fr in rgb_frames
    ]

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    paletted_frames[0].save(
        out,
        save_all=True,
        append_images=paletted_frames[1:],
        duration=65,
        loop=0,
        optimize=True,
    )
    return out


if __name__ == "__main__":
    src_arg = sys.argv[1] if len(sys.argv) > 1 else "media/images/mood-cow.webp"
    out_arg = sys.argv[2] if len(sys.argv) > 2 else "media/images/polish-cow-crt.gif"
    out_file = render_cow_crt(src_arg, out_arg)
    print(f"Generated {out_file}")
