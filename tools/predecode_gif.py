import os
import struct
from pathlib import Path

from PIL import Image, ImageSequence


def rgb888_to_rgb565(pixels):
    out = bytearray(len(pixels) * 2)
    for i, (r, g, b) in enumerate(pixels):
        color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out[i * 2] = (color >> 8) & 0xFF
        out[i * 2 + 1] = color & 0xFF
    return out


def full_frame_encode(raw_bytes):
    out = bytearray()
    total_pixels = len(raw_bytes) // 2
    index = 0
    while index < total_pixels:
        run = min(255, total_pixels - index)
        out.append(0)
        out.append(run)
        start = index * 2
        out.extend(raw_bytes[start : start + run * 2])
        index += run
    return out


def delta_rle_encode(prev_bytes, cur_bytes):
    out = bytearray()
    total_pixels = len(cur_bytes) // 2
    index = 0
    while index < total_pixels:
        skip = 0
        while index < total_pixels and skip < 255:
            cur_hi = cur_bytes[index * 2]
            cur_lo = cur_bytes[index * 2 + 1]
            prev_hi = prev_bytes[index * 2]
            prev_lo = prev_bytes[index * 2 + 1]
            if cur_hi != prev_hi or cur_lo != prev_lo:
                break
            skip += 1
            index += 1

        write_start = index
        write = 0
        while index < total_pixels and write < 255:
            cur_hi = cur_bytes[index * 2]
            cur_lo = cur_bytes[index * 2 + 1]
            prev_hi = prev_bytes[index * 2]
            prev_lo = prev_bytes[index * 2 + 1]
            if cur_hi == prev_hi and cur_lo == prev_lo:
                break
            write += 1
            index += 1

        out.append(skip)
        out.append(write)
        if write:
            start = write_start * 2
            out.extend(cur_bytes[start : start + write * 2])

        if skip == 0 and write == 0:
            break
    return out


TARGET_W = 240
TARGET_H = 135


def main():
    src = Path("gif/sega-small.gif")
    out_dir = Path("frames_delta")
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        width, height = im.size
        if width != 240 or height != 135:
            raise SystemExit("GIF must be 240x135")

        frame_count = 0
        prev_raw = None
        for frame in ImageSequence.Iterator(im):
            frame = frame.convert("RGB")
            pixels = list(frame.getdata())
            raw = rgb888_to_rgb565(pixels)
            if frame_count == 0:
                encoded = full_frame_encode(raw)
            else:
                encoded = delta_rle_encode(prev_raw, raw)
            frame_path = out_dir / f"frame_{frame_count:03d}.drle"
            frame_path.write_bytes(encoded)
            prev_raw = raw
            frame_count += 1

    print(f"Wrote {frame_count} frames to {out_dir}")


if __name__ == "__main__":
    main()
