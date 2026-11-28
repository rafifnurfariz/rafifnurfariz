"""Converts mood-cow.webp into a compact GitHub Blue CRT animated GIF (350x356)."""
from __future__ import annotations

import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageSequence
from scipy import ndimage

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = REPO_ROOT / "media" / "images" / "mood-cow.webp"
DEFAULT_OUT = REPO_ROOT / "media" / "images" / "polish-cow-crt.gif"

CHASSIS_BG = (9, 13, 19)
CHASSIS_STROKE = (33, 38, 45)
SCREEN_BG = (13, 17, 23)
SCREEN_BAR = (22, 27, 34)
SCREEN_STROKE = (48, 54, 61)
PANEL_DIVIDER = (33, 38, 45)

BLUE_BRIGHT = (121, 192, 255)
BLUE_CORE = (88, 166, 255)
BLUE_MID = (125, 165, 216)
BLUE_DIM = (56, 139, 253)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "C:/Windows/Fonts/consolab.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
            "/System/Library/Fonts/Menlo.ttc",
        ]
        if bold
        else [
            "C:/Windows/Fonts/consola.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/System/Library/Fonts/Menlo.ttc",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_text_right(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
) -> None:
    if isinstance(font, ImageFont.FreeTypeFont):
        draw.text((x, y), text, font=font, fill=fill, anchor="ra")
    else:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text((x - text_w, y), text, font=font, fill=fill)


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
    ramp_r = np.interp(gray, stops, [26, 48, 88, 155, 224])
    ramp_g = np.interp(gray, stops, [52, 98, 166, 212, 240])
    ramp_b = np.interp(gray, stops, [92, 172, 255, 255, 255])

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
    draw.rounded_rectangle([12, 12, w - 13, h - 13], radius=9, fill=SCREEN_BG)

    draw.rounded_rectangle([12, 12, w - 13, 40], radius=9, fill=SCREEN_BAR)
    draw.rectangle([12, 28, w - 13, 40], fill=SCREEN_BAR)
    draw.line([12, 40, w - 13, 40], fill=SCREEN_STROKE, width=1)
    draw.rounded_rectangle([12, 12, w - 13, h - 13], radius=9, outline=SCREEN_STROKE, width=1)

    draw.text((38, 20), "MOOD // Polish Cow", font=font_b, fill=BLUE_CORE)
    _draw_text_right(draw, w - 24, 21, "VIBING", font_r, BLUE_MID)

    draw.line([22, 322, w - 22, 322], fill=PANEL_DIVIDER, width=1)
    status_label = "> status:"
    draw.text((24, 328), status_label, font=font_b, fill=BLUE_CORE)
    status_bbox = draw.textbbox((24, 328), status_label, font=font_b)
    draw.text((max(84, status_bbox[2] + 5), 328), "coding & vibing", font=font_r, fill=BLUE_BRIGHT)
    return base


def _build_blue_palette(rgb_frames: list[Image.Image]) -> Image.Image:
    """Create a deterministic shared 64-color GitHub Blue palette across sampled GIF frames."""
    if len(rgb_frames) == 1:
        sample = rgb_frames[0]
    else:
        indices = sorted({round(i * (len(rgb_frames) - 1) / 3) for i in range(4)})
        w, h = rgb_frames[0].size
        sample = Image.new("RGB", (w, h * len(indices)))
        for row, frame_idx in enumerate(indices):
            sample.paste(rgb_frames[frame_idx], (0, row * h))
    return sample.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def render_cow_crt(
    src_path: str | Path = DEFAULT_SRC,
    out_path: str | Path = DEFAULT_OUT,
) -> Path:
    """Render Polish Cow frames inside a compact 350x356 GitHub Blue CRT GIF."""
    w, h = 350, 356
    font_b = _load_font(11, bold=True)
    font_r = _load_font(10, bold=False)

    base = _build_base_chassis(w, h, font_b, font_r)
    with Image.open(src_path) as src:
        raw_frames = [f.copy() for f in ImageSequence.Iterator(src)]

    if not raw_frames:
        raise ValueError("Source image contains no frames")

    scan = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    s_arr = np.asarray(scan, dtype=np.uint8).copy()
    s_arr[41 : h - 13 : 3, 13 : w - 13] = (0, 0, 0, 52)
    scan_overlay = Image.fromarray(s_arr, mode="RGBA")

    eq_heights = [
        [4, 8, 11, 6],
        [6, 12, 7, 9],
        [10, 5, 12, 8],
        [7, 10, 5, 11],
    ]

    total_f = len(raw_frames)
    rgb_frames: list[Image.Image] = []

    for idx, raw_frame in enumerate(raw_frames):
        cow = _extract_cow_rgba(raw_frame)
        if cow.width <= 0 or cow.height <= 0:
            raise ValueError("Source frame must have non-zero dimensions")
        scale = min(262 / cow.width, 224 / cow.height)
        nw = max(1, round(cow.width * scale))
        nh = max(1, round(cow.height * scale))
        cow_resized = cow.resize((nw, nh), Image.Resampling.LANCZOS)

        cx = (w - nw) // 2
        cy = 48 + (264 - nh) // 2

        canvas = base.copy()

        halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cow_alpha = cow_resized.getchannel("A")
        blue_fill = Image.new("RGBA", (nw, nh), (*BLUE_CORE, 255))
        blue_fill.putalpha(cow_alpha.point(lambda p: int(p * 0.22)))
        halo.paste(blue_fill, (cx, cy))
        halo = halo.filter(ImageFilter.GaussianBlur(radius=4))
        canvas = Image.alpha_composite(canvas, halo)

        cow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cow_layer.paste(cow_resized, (cx, cy), cow_resized)
        canvas = Image.alpha_composite(canvas, cow_layer)

        fdraw = ImageDraw.Draw(canvas)
        pulse = 0.5 + 0.5 * np.sin((idx / total_f) * 2 * np.pi)
        led_col = (
            int(56 + 48 * pulse),
            int(128 + 52 * pulse),
            255,
            255,
        )
        fdraw.ellipse([22, 22, 30, 30], fill=led_col)

        bars = eq_heights[idx % len(eq_heights)]
        for b_i, bh in enumerate(bars):
            bx = w - 84 + b_i * 5
            by = 339 - bh
            fdraw.rectangle([bx, by, bx + 3, 339], fill=(*BLUE_CORE, 235))
        _draw_text_right(fdraw, w - 24, 329, "[GIF]", font_r, BLUE_DIM)

        canvas = Image.alpha_composite(canvas, scan_overlay)
        rgb_frames.append(canvas.convert("RGB"))

    palette_ref = _build_blue_palette(rgb_frames)
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
    src_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    out_arg = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    out_file = render_cow_crt(src_arg, out_arg)
    print(f"Generated {out_file}")
