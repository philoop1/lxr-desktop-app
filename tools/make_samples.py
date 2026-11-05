#!/usr/bin/env python3
"""Pack one-shot samples into SAMPLES/SAMPLES.BIN for Mutador (0.2.51).

The firmware copies the file at boot into flash behind the wavetables and
plays sample n as waveform 38+n (SampleBank.h). Sources are WAV files (PCM
8/16/24/32 bit or 32 bit float, any channel count, mixed to mono) or folders
of WAV files in name order. The sample rate stays as it is (8 to 96 kHz): the
firmware plays a sample at its own pitch on coarse 0. The last frames fade to
zero, so a sample ends without a click.

--list reads "name|path" lines (paths relative to the list file), --crash adds
the 909-style crash of the LXR1 (Samples.c, 8 bit, 32 kHz) as the last sample.
--mutador builds the LXR1 Mutador set: the 16 samples of mutador/SDcard/samples
in name order, then the crash, which the LXR1 played as waveform 5.

SAMPLES.TXT next to the BIN lists each sample with its waveform number and the
coarse shift that keeps the LXR1 pitch (tools/import_lxr1_patterns.py).
"""
from __future__ import annotations

import argparse
import math
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b'LXRSM001'
MAX_SAMPLES = 48
FIRST_WAVE = 38
HEADER_BYTES = 1024
ENTRY = struct.Struct('<4sIII')
HEAD = struct.Struct('<8sHHIII')
MIN_RATE, MAX_RATE = 8000, 96000
MAX_FRAMES = (1 << 20) - 1          # 20 bits of frames in the phase
FLASH_BYTES = 4 * 0x40000           # sectors 8 to 11 with a wavetable bank in sector 7
FADE_FRAMES = 64
CRASH_RATE = 32000
LXR1_FS_FACTOR = 1024 * 440.0       # LXR1: frames per second = 1024 * f(note)

MUTADOR_NAMES = {
    'conga lflam': 'cfl', 'conga low': 'clo', 'conga mid': 'cmd', 'dholhi': 'dhl',
    'frame': 'frm', 'htalkdrum': 'tk1', 'htalkdrum2': 'tk2', 'lotom': 'ltm', 'rim': 'rim',
    'snare flam2': 'sf2', 'snare': 'sna', 'snareflam': 'sfl', 'tamindia': 'tmi',
    'tamsch': 'tms', 'upaistebell': 'bel', 'upaisteride': 'rid',
}


def read_wav(path: Path) -> tuple[list[int], int]:
    """16 bit mono frames and the sample rate of a WAV file."""
    data = path.read_bytes()
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError(f'{path}: not a WAV file')
    fmt = None
    pcm = None
    pos = 12
    while pos + 8 <= len(data):
        tag, size = data[pos:pos + 4], struct.unpack('<I', data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if tag == b'fmt ':
            fmt = struct.unpack('<HHIIHH', body[:16])
            if fmt[0] == 0xFFFE and len(body) >= 26:  # WAVE_FORMAT_EXTENSIBLE: the sub format
                fmt = (struct.unpack('<H', body[24:26])[0],) + fmt[1:]
        elif tag == b'data':
            pcm = body
        pos += 8 + size + (size & 1)
    if fmt is None or pcm is None:
        raise ValueError(f'{path}: no fmt or data chunk')
    kind, channels, rate, _, _, bits = fmt
    if channels < 1:
        raise ValueError(f'{path}: no channels')
    width = bits // 8
    if (kind, bits) == (3, 32):
        values = list(struct.unpack(f'<{len(pcm) // 4}f', pcm[:len(pcm) // 4 * 4]))
        scale = 32767.0
    elif kind == 1 and bits in (8, 16, 24, 32):
        count = len(pcm) // width
        if bits == 8:
            values = [b - 128 for b in pcm[:count]]
        elif bits == 16:
            values = list(struct.unpack(f'<{count}h', pcm[:count * 2]))
        elif bits == 24:
            values = [int.from_bytes(pcm[i:i + 3], 'little', signed=True) for i in range(0, count * 3, 3)]
        else:
            values = list(struct.unpack(f'<{count}i', pcm[:count * 4]))
        scale = 32768.0 / (1 << (bits - 1))
    else:
        raise ValueError(f'{path}: format {kind} with {bits} bits is not supported')
    frames = len(values) // channels
    mono = [sum(values[i * channels:(i + 1) * channels]) / channels * scale for i in range(frames)]
    return [max(-32768, min(32767, int(round(v)))) for v in mono], rate


def read_crash() -> tuple[list[int], int]:
    source = (ROOT / 'Core/Src/Soundengine/DSPAudio/Samples.c').read_text(encoding='latin-1')
    body = re.search(r'crashSample\[\d+\]\s*=\s*\{(.*?)\}', source, re.S)
    if not body:
        raise ValueError('Samples.c: crashSample not found')
    raw = [int(v, 16) for v in re.findall(r'0x([0-9A-Fa-f]{2})', body.group(1))]
    return [(v - 127) * 256 for v in raw], CRASH_RATE  # as the LXR1 played it


def fade_tail(frames: list[int]) -> list[int]:
    n = min(FADE_FRAMES, len(frames) // 4)
    out = list(frames)
    for i in range(n):
        k = len(out) - n + i
        out[k] = int(round(out[k] * (n - 1 - i) / n))
    if out:
        out[-1] = 0
    return out


def default_name(stem: str, used: set[str]) -> str:
    letters = re.sub(r'[^a-z0-9]', '', stem.lower()) or 'smp'
    name = (letters + 'xxx')[:3]
    digit = 1
    while name in used:
        name = (letters[:2] + 'xx')[:2] + str(digit % 10)
        digit += 1
    return name


def lxr1_shift(rate: int) -> float:
    """Semitones to add to an LXR1 coarse value so the sample keeps its LXR1 pitch."""
    return 60 - 69 + 12 * math.log2(LXR1_FS_FACTOR / rate)


def collect(args: argparse.Namespace) -> list[tuple[str, str, list[int], int]]:
    items: list[tuple[str, str, Path | None]] = []
    used: set[str] = set()
    if args.mutador:
        folder = args.mutador / 'SDcard' / 'samples'
        for path in sorted(folder.glob('*.wav')):
            items.append((MUTADOR_NAMES.get(path.stem) or default_name(path.stem, used), path.name, path))
            used.add(items[-1][0])
    if args.list:
        for line in args.list.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, _, rel = line.partition('|')
            items.append((name.strip(), rel.strip(), args.list.parent / rel.strip()))
            used.add(name.strip())
    for source in args.sources:
        paths = sorted(source.glob('*.wav')) if source.is_dir() else [source]
        for path in paths:
            items.append((default_name(path.stem, used), path.name, path))
            used.add(items[-1][0])
    if args.crash or args.mutador:
        items.append(('crs', 'crash (Samples.c)', None))
    result = []
    for name, label, path in items:
        if not re.fullmatch(r'[ -~]{1,3}', name):
            raise ValueError(f'{label}: name "{name}" must be 1 to 3 printable characters')
        frames, rate = read_crash() if path is None else read_wav(path)
        if not MIN_RATE <= rate <= MAX_RATE:
            raise ValueError(f'{label}: {rate} Hz is outside {MIN_RATE}..{MAX_RATE}')
        if len(frames) < 2:
            raise ValueError(f'{label}: fewer than 2 frames')
        if len(frames) > MAX_FRAMES:
            raise ValueError(f'{label}: more than {MAX_FRAMES} frames')
        result.append((name.ljust(3)[:3], label, fade_tail(frames), rate))
    if not result:
        raise ValueError('no samples given')
    if len(result) > MAX_SAMPLES:
        raise ValueError(f'{len(result)} samples, at most {MAX_SAMPLES}')
    return result


def build(samples: list[tuple[str, str, list[int], int]]) -> bytes:
    data = bytearray()
    entries = bytearray()
    for name, _, frames, rate in samples:
        entries += ENTRY.pack(name.encode('ascii') + b'\0', len(data), len(frames), rate)
        data += struct.pack(f'<{len(frames)}h', *frames)
        data += bytes(-len(data) % 4)
    entries += bytes(ENTRY.size * (MAX_SAMPLES - len(samples)))
    crc = zlib.crc32(bytes(entries) + bytes(data)) & 0xFFFFFFFF
    header = HEAD.pack(MAGIC, len(samples), 0, len(data), crc, 0) + entries
    header += bytes(HEADER_BYTES - len(header))
    assert len(header) == HEADER_BYTES
    if len(header) + len(data) > FLASH_BYTES:
        raise ValueError(f'{len(header) + len(data)} bytes, at most {FLASH_BYTES} fit after one wavetable sector')
    return bytes(header) + bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('output', type=Path, help='folder for SAMPLES.BIN, e.g. F:/SAMPLES')
    parser.add_argument('sources', type=Path, nargs='*', help='WAV files or folders')
    parser.add_argument('--list', type=Path, help='"name|path" lines')
    parser.add_argument('--crash', action='store_true', help='add the LXR1 crash as the last sample')
    parser.add_argument('--mutador', type=Path, help='LXR1 Mutador repository: its 16 samples and the crash')
    args = parser.parse_args()
    try:
        samples = collect(args)
        blob = build(samples)
    except ValueError as error:
        sys.exit(f'error: {error}')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'SAMPLES.BIN').write_bytes(blob)
    lines = ['wave  name  frames  rate   LXR1 shift  source']
    for i, (name, label, frames, rate) in enumerate(samples):
        lines.append(f'{FIRST_WAVE + i:4}  {name}  {len(frames):6}  {rate:5}  {lxr1_shift(rate):+7.3f}    {label}')
    (args.output / 'SAMPLES.TXT').write_text('\r\n'.join(lines) + '\r\n', encoding='ascii')
    print(f'{args.output / "SAMPLES.BIN"}: {len(samples)} samples, {len(blob)} bytes, CRC {zlib.crc32(blob[1024:]) & 0xFFFFFFFF:08X}')


if __name__ == '__main__':
    main()
