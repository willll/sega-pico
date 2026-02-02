# sega-pico

MicroPython starter project for the Sega Pico.

## Quick start

1. Flash MicroPython to your board.
2. Copy boot.py and main.py to the device filesystem.
3. Reset the board to run the program.

## Project layout

- boot.py: runs on boot
- main.py: main application entry
- src/: optional app modules
- lib/: third-party MicroPython libs
- tests/: test files

## Flashing and upload

Use your preferred tool to copy files to the board. Common steps:

1. Connect the board over USB.
2. Copy boot.py and main.py to the root of the device.
3. Copy any modules from src/ or lib/ as needed.
