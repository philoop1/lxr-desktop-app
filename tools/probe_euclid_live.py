"""Exercise Euclid through the known Lxr2Menu IMG-live runtime.

Requires PYTHONPATH to include Lxr2Menu and its emulator/_deps directory.
The SD-card directory is read through the emulator's RAM overlay.
"""

import argparse
import time
from pathlib import Path

from live_menu import LiveMenu


def wait_for(menu, serial=0, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        menu.poll()
        if not menu.thread.is_alive():
            raise RuntimeError(menu.message)
        if menu.state and menu.state.get("input_serial", -1) >= serial:
            return menu.state
        time.sleep(0.1)
    raise TimeoutError(menu.message)


def tap(menu, number):
    wait_for(menu, menu.button(number, True))
    return wait_for(menu, menu.button(number, False))


def active_steps(state):
    data = state.get("pattern_data") or {}
    masks = data.get("masks") or []
    if not masks:
        return None
    return sum(int(mask).bit_count() for mask in masks[0])


def pattern_masks(state):
    data = state.get("pattern_data") or {}
    masks = data.get("masks") or []
    return tuple(int(mask) for mask in masks[0]) if masks else ()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("card", type=Path)
    args = parser.parse_args()
    menu = LiveMenu(args.image, args.card)
    try:
        state = wait_for(menu)
        print("READY", state.get("lcd_lines"), flush=True)
        wait_for(menu, menu.button(32, True))  # SHIFT
        state = tap(menu, 25)  # PERF / Euclid
        state = wait_for(menu, menu.button(32, False))
        print("EUCLID", state.get("menu_active_page"), state.get("lcd_lines"),
              "active", active_steps(state), flush=True)
        state = wait_for(menu, menu.knob(1, 1))  # increase number of steps
        print("STEPS+1", state.get("menu_active_page"), state.get("lcd_lines"),
              "active", active_steps(state), flush=True)
        if state.get("menu_active_page") != 12:
            raise AssertionError("Euclid page was not reached")
        if active_steps(state) != 5:
            raise AssertionError("Expected five generated steps after steps +1")
        original_masks = pattern_masks(state)
        state = wait_for(menu, menu.knob(2, 1))  # rotate
        print("ROT+1", state.get("lcd_lines"), "masks", pattern_masks(state),
              flush=True)
        if active_steps(state) != 5 or pattern_masks(state) == original_masks:
            raise AssertionError("Rotation did not preserve and move five steps")
        state = wait_for(menu, menu.knob(0, -1))  # length 16 -> 15
        print("LEN-1", state.get("lcd_lines"), "active", active_steps(state),
              flush=True)
        if active_steps(state) != 5:
            raise AssertionError("Length change lost generated steps")
    finally:
        menu.close()
        menu.thread.join(15)


if __name__ == "__main__":
    main()
