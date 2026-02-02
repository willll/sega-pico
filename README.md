# sega-pico

MicroPython project for Raspberry Pi Pico with a Pico LCD (1.14). It plays an animated GIF on the LCD by pre-decoding frames on your PC into a compact delta-RLE format and then streaming them to the Pico.

## Quick start

1. Flash MicroPython to your Raspberry Pi Pico.
2. Copy `boot.py`, `main.py`, `src/pico_lcd_1_14.py`, and the `frames_delta/` folder to the Pico filesystem.
3. Reset the board to run the animation.

## Project layout

- boot.py: runs on boot
- main.py: playback loop, button handling, and timing
- src/pico_lcd_1_14.py: LCD driver (Waveshare 1.14)
- tools/predecode_gif.py: PC-side delta-RLE encoder
- frames_delta/: per-animation folders with delta-RLE frames and settings.txt

## Generate frames (PC)

The Pico does not decode GIFs fast enough for smooth playback. Use the PC encoder to generate delta-RLE frames.

1. Install Python 3 and Pillow.
2. Place your source GIF under `gif/`.
3. Run the encoder with input, output folder, optional frame step, and optional target size:

	- `/home/will/tmp/sega-pico/.venv/bin/python tools/predecode_gif.py gif/sega-small.gif frames_delta/sega 1 120 67`

This writes `frames_delta/<name>/frame_###.drle` files. For full resolution, use `240 135`.

## Configure playback

Each animation folder under `frames_delta/` must include a `settings.txt` file. Settings are loaded at startup and when switching animations.

Example settings:

- `FRAME_SKIP = 4`
- `PRINT_FRAMES = False`
- `RAW_FRAMES_DIR = "frames_delta/sega"`
- `FRAME_W = 120`
- `FRAME_H = 67`
- `TARGET_LOOP_MS = 1160`
- `USE_TIMER_PACING = True`

## Flashing and upload

Use your preferred tool to copy files to the board. Common steps:

1. Connect the board over USB.
2. Copy `boot.py`, `main.py`, and `src/pico_lcd_1_14.py` to the device.
3. Copy the `frames_delta/` folder to the device.
4. Reset the board to run.

## Controls

- Button A (GP15, active-low): next animation folder
- Button B (GP17, active-low): previous animation folder

## Troubleshooting

- If you see noise, regenerate frames for that folder.
- If playback is too slow, increase `FRAME_SKIP` or reduce the GIF size before encoding.
- If timing drifts, adjust `TARGET_LOOP_MS`.

## Project tree

```
.
├── boot.py
├── main.py
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── .gitignore
├── .github/
├── frames_delta/
│   ├── sega/
│   ├── sega-alternate/
│   ├── sega-bouncing/
│   └── sega-sonic/
├── src/
│   └── pico_lcd_1_14.py
└── tools/
	└── predecode_gif.py
```

## Project video

[![Project demo thumbnail](https://img.youtube.com/vi/TMqXyAvfdKo/hqdefault.jpg)](https://www.youtube.com/shorts/TMqXyAvfdKo)
