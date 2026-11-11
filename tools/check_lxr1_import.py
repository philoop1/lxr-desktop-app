"""Small format and timing checks for the offline LXR1 PAT converter."""

import struct
from import_lxr1_patterns import convert, convert_kit, parameter_maps, LXR1_PATTERN_BYTES
from import_lxr1_patterns import convert_lxr1_modulation, enum_values, lxr1_modulation_range, mod_targets
import math
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
    assert len(images) == 8 and all(len(x) == 4462 and x[-341:] == b"CND3" + bytes(337) for x in images)
    step, byte = first_step(images[0])
    assert step == bytes((0x80 | 91, 100, 60, 255, 0, 255, 0)), hits  # LXR1 note 63 is LXR2 note 60 (0.2.52)
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

# 0.2.64: LXR1 modulation scales down from the set value, LXR2 swings around it.
repo = Path(__file__).resolve().parents[1]
enum = enum_values(repo / "Core/Inc/Parameters.h")
targets = mod_targets(repo / "Core/Src/menu/Cc2Text.c")


def lxr2_span(base, depth):
    return min(127, max(0, base - depth)), min(127, max(0, base + depth))


for amount in (1, 20, 64, 100, 127):
    amt = amount / 127
    for base in (0, 30, 64, 100, 127):
        b2, d2 = lxr1_modulation_range("PAR_FILTER_FREQ_1", base, amount, False)
        low, high = lxr2_span(b2, d2)
        assert abs(high - base) <= 1 and abs(low - base * (1 - amt)) <= 1, (base, amount)
        b2, d2 = lxr1_modulation_range("PAR_FINE1", base, amount, False)
        low, high = lxr2_span(b2, d2)
        assert abs(high - 63.5) <= 1 and abs(low - 63.5 * (1 - amt)) <= 1, (base, amount)
        b2, d2 = lxr1_modulation_range("PAR_COARSE1", base, amount, False)
        want = max(12 * math.log2(max(1 - amt, 2 ** -4)), -48)
        if 0 <= base + want and base <= 127:
            low, high = lxr2_span(b2, d2)
            assert abs(high - base) <= 1 and abs(low - (base + want)) <= 1, (base, amount)
        assert lxr1_modulation_range("PAR_PAN1", base, amount, True) == (base, round(amount / 2))
        assert lxr1_modulation_range("PAR_PAN1", base, amount, False) == (round(base * (1 - amt / 2)), round(base * amt / 2))
        for switch in ("PAR_OSC_WAVE_DRUM1", "PAR_FILTER_TYPE_1", "PAR_NONE", "PAR_FX_P1"):
            assert lxr1_modulation_range(switch, base, amount, False) is None
    assert lxr1_modulation_range("PAR_FILTER_FREQ_1", 90, 0, False) is None
assert lxr1_modulation_range("PAR_COARSE1", 10, 127, False) == (5, 5)  # high end stays the set value near 0
assert lxr1_modulation_range("PAR_FM_FREQ1", 0, 65, False) == (0, 0)
probe = bytearray(count)
probe[enum["PAR_COARSE1"]] = 64
probe[enum["PAR_FILTER_FREQ_2"]] = 100
probe[enum["PAR_VEL_DEST_1"]] = targets.index("PAR_COARSE1")
probe[enum["PAR_VELO_MOD_AMT_1"]] = 127
probe[enum["PAR_TARGET_LFO2"]] = targets.index("PAR_FILTER_FREQ_2")
probe[enum["PAR_AMOUNT_LFO2"]] = 64
probe[enum["PAR_TARGET_LFO3"]] = targets.index("PAR_COARSE1")
probe[enum["PAR_AMOUNT_LFO3"]] = 32
mod_notes = convert_lxr1_modulation(probe, enum, targets)
assert probe[enum["PAR_COARSE1"]] == 40 and probe[enum["PAR_VELO_MOD_AMT_1"]] == 24, mod_notes  # -48 semitones at full depth
assert probe[enum["PAR_FILTER_FREQ_2"]] == 75 and probe[enum["PAR_AMOUNT_LFO2"]] == 25, mod_notes
assert probe[enum["PAR_AMOUNT_LFO3"]] != 32 and any("already moved" in n for n in mod_notes), mod_notes
lxr1_coarse = next(old for old, new in target_map.items() if new == targets.index("PAR_COARSE1"))
source_kit = bytearray(b"Example " + bytes(228))
source_kit[8 + enum["PAR_COARSE1"]] = 70
source_kit[8 + enum["PAR_VEL_DEST_1"]] = lxr1_coarse
source_kit[8 + enum["PAR_VELO_MOD_AMT_1"]] = 64
kit, notes = convert_kit(bytes(source_kit), ".snd", old_source)
assert kit[8 + enum["PAR_VEL_DEST_1"]] == targets.index("PAR_COARSE1")
assert kit[8 + enum["PAR_COARSE1"]] == 70 - 6 and kit[8 + enum["PAR_VELO_MOD_AMT_1"]] == 6, notes
assert any("velocity 1 -> COARSE1" in n for n in notes), notes

print("LXR1 import: timing, one/four bars, kit, target map, modulation range, truncation and track order checked")
