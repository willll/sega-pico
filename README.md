# sega-pico

MicroPython project for Raspberry Pi Pico with a Pico LCD (1.14). It plays an animated GIF on the LCD by pre-decoding frames on your PC into a compact delta-RLE format and then streaming them to the Pico.

## Quick start

1. Flash MicroPython to your Raspberry Pi Pico.
2. Copy `boot.py`, `main.py`, `src/pico_lcd_1_14.py`, and the `frames_delta/` folder to the Pico filesystem.
3. Reset the board to run the animation.

## Project layout

- boot.py: runs on boot
- main.py: playback loop and timing
- src/pico_lcd_1_14.py: LCD driver (Waveshare 1.14)
- tools/predecode_gif.py: PC-side delta-RLE encoder
- frames_delta/: delta-RLE frames generated from the source GIF

## Generate frames (PC)

The Pico does not decode GIFs fast enough for smooth playback. Use the PC encoder to generate delta-RLE frames.

1. Install Python 3 and Pillow.
2. Place your source GIF at `gif/sega-small.gif` (240x135).
3. Run the encoder:

	- `/home/will/tmp/sega-pico/.venv/bin/python tools/predecode_gif.py`

This writes `frames_delta/frame_###.drle` files.

## Configure playback

Key settings in `main.py`:

- `RAW_FRAMES_DIR`: folder for delta-RLE frames (default `frames_delta`).
- `FRAME_SKIP`: render every Nth frame (default 4).
- `TARGET_LOOP_MS`: target total loop duration in ms (default 1160).
- `USE_TIMER_PACING`: hardware timer pacing (default true).

## Flashing and upload

Use your preferred tool to copy files to the board. Common steps:

1. Connect the board over USB.
2. Copy `boot.py`, `main.py`, and `src/pico_lcd_1_14.py` to the device.
3. Copy the `frames_delta/` folder to the device.
4. Reset the board to run.

## Troubleshooting

- If you see noise, regenerate `frames_delta` and ensure the GIF is 240x135.
- If playback is too slow, increase `FRAME_SKIP` or reduce the GIF size before encoding.
- If timing drifts, adjust `TARGET_LOOP_MS`.
