"""Small format and timing checks for the offline LXR1 PAT converter."""

import struct
from import_lxr1_patterns import convert, convert_kit, parameter_maps, LXR1_PATTERN_BYTES
from pathlib import Path


def sample(hits):
    block = bytearray(LXR1_PATTERN_BYTES)
    for k in hits:
        block[k * 7:k * 7 + 7] = bytes((0x80 | 91, 127, 63, 255, 0, 255, 0))
    step_end = 7 * 8 * 128 * 7
    struct.pack_into("<H", block, step_end, 1)
    block[step_end + 112 + 16] = 42
    return b"Example " + block


def first_step(image):
    return image[14:21], image[14 + 64 * 7]


for hits, timing in (((0,), 0x70), ((3,), 0xA0), ((0, 4), 0x71),
                     ((0, 2, 4, 6), 0x73), (tuple(range(8)), 0x75)):
    images, warnings = convert(sample(hits), ".pat")
    assert len(images) == 8 and all(len(x) == 4574 for x in images)
    step, byte = first_step(images[0])
    assert step == bytes((0x80 | 91, 100, 63, 255, 0, 255, 0)), hits
    assert byte == timing, hits
    assert images[0][14 + 16 * 7] == 100  # bar 2 empty by default
    assert not warnings, warnings[:2]

images, warnings = convert(sample((0, 3, 7)), ".pat")
assert any("irregular substeps" in note for note in warnings)
assert images[0][14 + 64 * 7] == 0x70
try:
    convert(sample((0,))[:-1], ".pat")
except ValueError:
    pass
else:
    raise AssertionError("truncated pattern accepted")

images, _ = convert(sample((0,)), ".pat", repeat=True)
assert images[0][14 + 16 * 7] == 0x80 | 91
old_source = Path(__file__).resolve().parents[2] / "mutador"
target_map, valid_ids, count = parameter_maps(old_source)
assert count > 228 and 8 in valid_ids and target_map[0] == 0
kit, notes = convert_kit(b"Example " + bytes(228), ".snd", old_source)
assert len(kit) == 8 + count + 4 + 16 + 46
assert kit[8 + count:8 + count + 4] == b"SNE2"
source = bytearray(sample((0,)))
source[8 + 3] = 8  # PAR_COARSE1 is an allowed automation target in both firmwares
source[8 + 4] = 75
images, warnings = convert(bytes(source), ".pat", valid_automation=valid_ids)
assert images[0][14 + 3:14 + 7] == bytes((8, 75, 255, 0))
assert not any("automation" in note for note in warnings)
source[8 + 3] = 222  # old MIDI note ID cannot control an LXR2 sound parameter
images, warnings = convert(bytes(source), ".pat", valid_automation=valid_ids)
assert images[0][14 + 3] == 255 and any("automation" in note for note in warnings)

main_offset = 14 + 7 * (64 * 7 + 64)  # firmware order: every bar of track 0, then track 1
for track in range(7):
    block = bytearray(sample(()))[8:]
    start = track * 8 * 128 * 7
    block[start:start + 7] = bytes((0x80 | 91, 127, 63, 255, 0, 255, 0))
    struct.pack_into("<H", block, 7 * 8 * 128 * 7, 0)
    struct.pack_into("<H", block, 7 * 8 * 128 * 7 + track * 2, 1)
    images, _ = convert(b"Example " + bytes(block), ".pat")
    words = struct.unpack_from("<28H", images[0], main_offset)
    assert words[track * 4] == 1 and sum(words) == 1, track

print("LXR1 import: timing, one/four bars, kit, target map, truncation and track order checked")
