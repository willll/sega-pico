import os
import sys
import time

from machine import Pin, Timer

try:
    import micropython
except ImportError:  # CPython fallback
    micropython = None

if "src" not in sys.path:
    sys.path.append("src")

import pico_lcd_1_14 as lcd_mod

FRAME_SKIP = 4
PRINT_FRAMES = False
RAW_FRAMES_DIR = "frames_delta/sega"
USE_RAW_FRAMES = True
FRAME_W = 240
FRAME_H = 135
TARGET_LOOP_MS = 1160
USE_TIMER_PACING = True
FOLDERS_ROOT = "frames_delta"
BUTTON_A_PIN = 15
BUTTON_B_PIN = 17
DEBOUNCE_MS = 200
SETTINGS_FILE = "settings.txt"

_frame_ready = False
_frame_interval = 0
_last_button_ms = 0
_last_a = 1
_last_b = 1


def _timer_cb(_):
    global _frame_ready
    _frame_ready = True


def load_settings():
    settings_path = RAW_FRAMES_DIR + "/" + SETTINGS_FILE
    try:
        with open(settings_path, "r") as handle:
            lines = handle.readlines()
    except OSError:
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if key not in globals():
            continue
        if raw in ("True", "False"):
            value = raw == "True"
        elif raw.startswith("\"") and raw.endswith("\"") and len(raw) >= 2:
            value = raw[1:-1]
        else:
            try:
                value = int(raw)
            except ValueError:
                continue
        globals()[key] = value


def list_animation_folders():
    try:
        names = [name for name in os.listdir(FOLDERS_ROOT)]
    except OSError:
        return []
    folders = []
    for name in names:
        path = FOLDERS_ROOT + "/" + name
        try:
            if "settings.txt" in os.listdir(path):
                folders.append(path)
        except OSError:
            continue
    folders.sort()
    return folders


def read_button(pin):
    return pin.value() == 0


def check_folder_switch(button_a, button_b, folders, folder_index):
    global _last_button_ms
    global _last_a
    global _last_b

    now_ms = time.ticks_ms()
    if time.ticks_diff(now_ms, _last_button_ms) <= DEBOUNCE_MS:
        _last_a = 0 if read_button(button_a) else 1
        _last_b = 0 if read_button(button_b) else 1
        return folder_index, False

    a_now = 0 if read_button(button_a) else 1
    b_now = 0 if read_button(button_b) else 1
    switched = False

    if _last_a == 1 and a_now == 0 and folders:
        folder_index = (folder_index + 1) % len(folders)
        _last_button_ms = now_ms
        switched = True
        print("button A")
    elif _last_b == 1 and b_now == 0 and folders:
        folder_index = (folder_index - 1) % len(folders)
        _last_button_ms = now_ms
        switched = True
        print("button B")

    _last_a = a_now
    _last_b = b_now
    return folder_index, switched


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
        scale_x: int,
        scale_y: int,
        extra_row: int,
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
                    dx = offset_x + (x * scale_x)
                    dy = offset_y + (y * scale_y)
                    for sy in range(scale_y):
                        row = dy + sy
                        dst_index = (row * screen_w + dx) * 2
                        for sx in range(scale_x):
                            dst[dst_index] = src[i]
                            dst[dst_index + 1] = src[i + 1]
                            dst_index += 2
                    if extra_row and y == frame_h - 1:
                        row = dy + scale_y
                        dst_index = (row * screen_w + dx) * 2
                        for sx in range(scale_x):
                            dst[dst_index] = src[i]
                            dst[dst_index + 1] = src[i + 1]
                            dst_index += 2
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
        scale_x,
        scale_y,
        extra_row,
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
                    dx = offset_x + (x * scale_x)
                    dy = offset_y + (y * scale_y)
                    for sy in range(scale_y):
                        row = dy + sy
                        dst = (row * screen_w + dx) * 2
                        for _ in range(scale_x):
                            out[dst] = data[i]
                            out[dst + 1] = data[i + 1]
                            dst += 2
                    if extra_row and y == frame_h - 1:
                        row = dy + scale_y
                        dst = (row * screen_w + dx) * 2
                        for _ in range(scale_x):
                            out[dst] = data[i]
                            out[dst + 1] = data[i + 1]
                            dst += 2
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
    scale_x,
    scale_y,
    extra_row,
):
    with open(path, "rb") as handle:
        data = handle.read()
    _delta_rle_apply(
        data,
        out_buf,
        frame_w,
        frame_h,
        offset_x,
        offset_y,
        screen_w,
        scale_x,
        scale_y,
        extra_row,
    )


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
    global _last_button_ms
    global RAW_FRAMES_DIR
    load_settings()
    button_a = Pin(BUTTON_A_PIN, Pin.IN, Pin.PULL_UP)
    button_b = Pin(BUTTON_B_PIN, Pin.IN, Pin.PULL_UP)
    folders = list_animation_folders()
    if folders:
        if RAW_FRAMES_DIR in folders:
            folder_index = folders.index(RAW_FRAMES_DIR)
        else:
            folder_index = 0
            RAW_FRAMES_DIR = folders[0]
    else:
        folder_index = 0
    lcd = init_lcd()
    if not hasattr(lcd, "buffer"):
        raise RuntimeError("LCD driver missing framebuffer")
    while True:
        loop_start = time.ticks_ms()
        frame_files = [name for name in os.listdir(RAW_FRAMES_DIR) if name.endswith(".drle")]
        frame_files.sort()
        frame_count = 0
        offset_x = 0
        offset_y = 0
        switched = False
        scale_x = lcd.width // FRAME_W
        scale_y = lcd.height // FRAME_H
        extra_row = lcd.height - (FRAME_H * scale_y)
        if _frame_interval <= 0:
            _frame_interval = max(1, TARGET_LOOP_MS // max(1, len(frame_files)))
        timer = None
        if USE_TIMER_PACING:
            timer = Timer(-1)
            timer.init(period=_frame_interval, mode=Timer.PERIODIC, callback=_timer_cb)
        for name in frame_files:
            folder_index, switched = check_folder_switch(
                button_a, button_b, folders, folder_index
            )
            if switched:
                RAW_FRAMES_DIR = folders[folder_index]
                _frame_interval = 0
                load_settings()
                print("animation:", RAW_FRAMES_DIR.split("/")[-1])
                _frame_ready = False
                break
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
                scale_x,
                scale_y,
                extra_row,
            )
            if hasattr(lcd, "show") and (frame_count % FRAME_SKIP == 0):
                lcd.show()
            frame_count += 1
        if timer:
            timer.deinit()
        if switched:
            continue
        loop_elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
        print("frames:", frame_count, "total_ms:", loop_elapsed)
        if USE_TIMER_PACING and frame_count:
            error = TARGET_LOOP_MS - loop_elapsed
            _frame_interval = max(1, _frame_interval + (error // frame_count))


if __name__ == "__main__":
    main()
