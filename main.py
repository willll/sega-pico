import os
import sys
import time

from machine import Timer

try:
    import micropython
except ImportError:  # CPython fallback
    micropython = None

if "src" not in sys.path:
    sys.path.append("src")

import pico_lcd_1_14 as lcd_mod

from gif_decoder import GifDecoder

GIF_PATH = "gif/sega-small.gif"
FRAME_SKIP = 4
PRINT_FRAMES = False
RAW_FRAMES_DIR = "frames_delta"
USE_RAW_FRAMES = True
FRAME_W = 240
FRAME_H = 135
TARGET_LOOP_MS = 1160
USE_TIMER_PACING = True

_frame_ready = False
_frame_interval = 0


def _timer_cb(_):
    global _frame_ready
    _frame_ready = True


def _advance_pos(count, frame_w, cur_x, cur_y):
    cur_x += count
    if cur_x >= frame_w:
        cur_y += cur_x // frame_w
        cur_x = cur_x % frame_w
    return cur_x, cur_y


if micropython:
    @micropython.viper
    def _delta_rle_apply(
        data: object,
        out_buf: object,
        frame_w: int,
        frame_h: int,
        offset_x: int,
        offset_y: int,
        screen_w: int,
    ) -> int:
        src = ptr8(data)
        dst = ptr8(out_buf)
        length = int(len(data))
        i = 0
        pos = 0
        frame_pixels = frame_w * frame_h
        while i + 1 < length:
            skip = int(src[i])
            write = int(src[i + 1])
            i += 2
            pos += skip
            if pos >= frame_pixels:
                break
            if write:
                for _ in range(write):
                    if i + 1 >= length or pos >= frame_pixels:
                        break
                    x = pos % frame_w
                    y = pos // frame_w
                    dst_index = ((offset_y + y) * screen_w + (offset_x + x)) * 2
                    dst[dst_index] = src[i]
                    dst[dst_index + 1] = src[i + 1]
                    i += 2
                    pos += 1
            else:
                if pos >= frame_pixels:
                    break
        return pos
else:
    def _delta_rle_apply(
        data,
        out_buf,
        frame_w,
        frame_h,
        offset_x,
        offset_y,
        screen_w,
    ):
        pos = 0
        frame_pixels = frame_w * frame_h
        i = 0
        length = len(data)
        out = memoryview(out_buf)
        while i + 1 < length:
            skip = data[i]
            write = data[i + 1]
            i += 2
            pos += skip
            if pos >= frame_pixels:
                break
            if write:
                for _ in range(write):
                    if i + 1 >= length or pos >= frame_pixels:
                        break
                    x = pos % frame_w
                    y = pos // frame_w
                    dst = ((offset_y + y) * screen_w + (offset_x + x)) * 2
                    out[dst] = data[i]
                    out[dst + 1] = data[i + 1]
                    i += 2
                    pos += 1
        return pos


def delta_rle_decode_into(
    path,
    out_buf,
    frame_w,
    frame_h,
    offset_x,
    offset_y,
    screen_w,
):
    with open(path, "rb") as handle:
        data = handle.read()
    _delta_rle_apply(data, out_buf, frame_w, frame_h, offset_x, offset_y, screen_w)


def init_lcd():
    if hasattr(lcd_mod, "LCD_1inch14"):
        lcd = lcd_mod.LCD_1inch14()
    else:
        raise RuntimeError("Unsupported pico_lcd_1_14 driver")

    if hasattr(lcd, "init"):
        lcd.init()
    if hasattr(lcd, "fill"):
        lcd.fill(0)
    if hasattr(lcd, "show"):
        lcd.show()
    return lcd


def main() -> None:
    global _frame_ready
    global _frame_interval
    lcd = init_lcd()
    if not hasattr(lcd, "buffer"):
        raise RuntimeError("LCD driver missing framebuffer")
    decoder = GifDecoder(GIF_PATH)

    while True:
        if USE_RAW_FRAMES:
            loop_start = time.ticks_ms()
            frame_files = [name for name in os.listdir(RAW_FRAMES_DIR) if name.endswith(".drle")]
            frame_files.sort()
            frame_count = 0
            offset_x = 0
            offset_y = 0
            if _frame_interval <= 0:
                _frame_interval = max(1, TARGET_LOOP_MS // max(1, len(frame_files)))
            timer = None
            if USE_TIMER_PACING:
                timer = Timer(-1)
                timer.init(period=_frame_interval, mode=Timer.PERIODIC, callback=_timer_cb)
            for name in frame_files:
                if USE_TIMER_PACING:
                    while not _frame_ready:
                        time.sleep_ms(1)
                    _frame_ready = False
                delta_rle_decode_into(
                    RAW_FRAMES_DIR + "/" + name,
                    lcd.buffer,
                    FRAME_W,
                    FRAME_H,
                    offset_x,
                    offset_y,
                    lcd.width,
                )
                if hasattr(lcd, "show") and (frame_count % FRAME_SKIP == 0):
                    lcd.show()
                frame_count += 1
            if timer:
                timer.deinit()
            loop_elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
            print("frames:", frame_count, "total_ms:", loop_elapsed)
            if USE_TIMER_PACING and frame_count:
                error = TARGET_LOOP_MS - loop_elapsed
                _frame_interval = max(1, _frame_interval + (error // frame_count))
            continue

        loop_start = time.ticks_ms()
        frame_count = 0
        for delay_ms in decoder.decode_into(lcd.buffer, lcd.width, lcd.height):
            frame_start = time.ticks_ms()
            if hasattr(lcd, "show") and (frame_count % FRAME_SKIP == 0):
                lcd.show()
            frame_count += 1
            if PRINT_FRAMES:
                print("frame", frame_count)
            elapsed = time.ticks_diff(time.ticks_ms(), frame_start)
            remaining = delay_ms - elapsed
            if remaining > 0:
                time.sleep_ms(remaining)
        loop_elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
        print("frames:", frame_count, "total_ms:", loop_elapsed)


if __name__ == "__main__":
    main()
