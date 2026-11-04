"""Build WAVES/WAVES.BIN for the Mutador wavetable oscillator.

Usage: python tools/make_wavetables.py <source> [<source> ...] <card or output folder>
       python tools/make_wavetables.py --each <folder> <card or output folder>

Every source becomes one wavetable (at most 32):
  - a file is one wavetable with its frames:
      Serum WAV (frames of 2048, or the size its `clm ` chunk names),
      Surge WAV (frame size in its `srge` chunk), Surge `.wt` file,
      or any other WAV as one single cycle (one frame);
  - a folder is one wavetable from all its WAV and .wt files in name order,
    each adding its frames (a folder of single cycles scans through them).
With --each, every file in the folder is its own wavetable instead.

WAV: PCM 8, 16, 24 or 32 bit, or 32-bit float; mono, or the channels are
averaged. A wavetable keeps at most 255 frames and all together at most 284
(1280 KB of flash); where there are more, the largest wavetables keep evenly
spaced frames, first and last included.

Each frame loses its DC part and gets 10 band-limited octave levels. Level j
plays below 55 Hz * 2^j and keeps the harmonics below 20 kHz there; its
length is 1024, 512, 256, 128 and then 64 samples. One gain per wavetable
brings its loudest level to 32000, so the frames keep their balance. Names are
the first three letters of the file or folder name; where several share them,
two letters and a number (KR1, KR2, ...).

The firmware copies WAVES.BIN to flash sectors 7 to 11 at boot when its
header differs from the one there. Waveform picks the wavetable, PWM scans its
frames. Layout, little endian:
  0   magic "LXRWT003"
  8   uint16 count, levels (10), length (1024), reserved (0)
  16  uint32 data bytes, uint32 CRC-32 (zlib) of names, frames and data
  24  32 names of 4 bytes (3 letters and 0)
  152 32 frame counts (uint8, 0 past count)
  184 zero padding up to 256
  256 int16 frames, each 2304 samples: the levels one after another
"""

import cmath
import math
import re
import struct
import sys
import zlib
from pathlib import Path

MAX_TABLES = 32
LEVELS = 10
LENGTH = 1024
LEVEL_LENGTHS = [1024, 512, 256, 128] + [64] * 6
FRAME_SAMPLES = sum(LEVEL_LENGTHS)  # 2304
HEADER_BYTES = 256
FLASH_BYTES = 5 * 0x40000  # sectors 7 to 11
MAX_FRAMES = (FLASH_BYTES - HEADER_BYTES) // (FRAME_SAMPLES * 2)  # 284
MAX_TABLE_FRAMES = 255
MAGIC = b'LXRWT003'
PEAK = 32000
SERUM_FRAME = 2048
SOURCE_SUFFIXES = ('.wav', '.wt')
# Level j plays below 55 Hz * 2^j; it keeps the partials below 20 kHz there.
BASE_HZ = 55.0
TOP_HZ = 20000.0


def level_harmonics(level):
    return min(LEVEL_LENGTHS[level] // 2 - 1, int(TOP_HZ / (BASE_HZ * 2 ** level)))


def read_wav(path):
    """Samples and the frame size the file names (0 when it names none)."""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError(f'{path.name}: not a WAV file')
    pos, fmt, frames, frame_size = 12, None, None, 0
    while pos + 8 <= len(data):
        tag, size = data[pos:pos + 4], struct.unpack_from('<I', data, pos + 4)[0]
        body = data[pos + 8:pos + 8 + size]
        if tag == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', body)
            if fmt[0] == 0xFFFE and len(body) >= 26:
                # WAVE_FORMAT_EXTENSIBLE: the real format code opens the subformat GUID
                fmt = (struct.unpack_from('<H', body, 24)[0],) + fmt[1:]
        elif tag == b'data':
            frames = body
        elif tag in (b'srge', b'srgo') and len(body) >= 8:
            frame_size = struct.unpack_from('<I', body, 4)[0]  # Surge: version, frame size
        elif tag == b'clm ':
            match = re.match(rb'<!>(\d+)', body)  # Serum: "<!>2048 ..."
            if match:
                frame_size = int(match.group(1))
        pos += 8 + size + (size & 1)
    if fmt is None or frames is None:
        raise ValueError(f'{path.name}: no fmt or data chunk')
    code, channels, _, _, align, bits = fmt
    if code not in (1, 3) or (code == 3 and bits != 32) or bits not in (8, 16, 24, 32):
        raise ValueError(f'{path.name}: format {code} with {bits} bit is not supported')
    width = bits // 8
    count = len(frames) // align
    samples = []
    for i in range(count):
        total = 0.0
        for c in range(channels):
            raw = frames[i * align + c * width:i * align + (c + 1) * width]
            if code == 3 and bits == 32:
                v = struct.unpack('<f', raw)[0]
            elif bits == 8:
                v = (raw[0] - 128) / 128.0
            else:
                v = int.from_bytes(raw, 'little', signed=True) / float(1 << (bits - 1))
            total += v
        samples.append(total / channels)
    if count < 8:
        raise ValueError(f'{path.name}: only {count} samples')
    return samples, frame_size


def read_wt(path):
    """Surge .wt: "vawt", uint32 frame size, uint16 frames, uint16 flags, then the data."""
    data = Path(path).read_bytes()
    if data[:4] != b'vawt' or len(data) < 12:
        raise ValueError(f'{path.name}: not a Surge .wt file')
    size, count, flags = struct.unpack_from('<IHH', data, 4)
    if flags & 0x04:
        values = struct.unpack_from(f'<{size * count}h', data, 12)
        scale = 32768.0 if flags & 0x08 else 16384.0
        samples = [v / scale for v in values]
    else:
        samples = list(struct.unpack_from(f'<{size * count}f', data, 12))
    if size < 8 or not count:
        raise ValueError(f'{path.name}: no frames')
    return samples, size


def split_frames(samples, frame):
    """Frames of a file; frame 0 means Serum style 2048 when it divides, else one cycle."""
    n = len(samples)
    if frame <= 0:
        frame = SERUM_FRAME if n % SERUM_FRAME == 0 and n >= 2 * SERUM_FRAME else n
    count = n // frame
    if count == 0:
        return [samples]
    return [samples[i * frame:(i + 1) * frame] for i in range(count)]


def file_frames(path):
    path = Path(path)
    samples, frame = read_wt(path) if path.suffix.lower() == '.wt' else read_wav(path)
    frames = split_frames(samples, frame)
    if frame and len(samples) % frame:
        print(f'{path.name}: {len(samples) % frame} samples after the last whole frame are dropped')
    return frames


def source_files(folder):
    return sorted(p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES)


def fft(x, inverse=False):
    """Iterative radix-2 FFT for power-of-two lengths."""
    n = len(x)
    a = list(x)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    sign = 1 if inverse else -1
    while size <= n:
        w_step = cmath.exp(sign * 2j * math.pi / size)
        for start in range(0, n, size):
            w = 1
            for k in range(size // 2):
                u, v = a[start + k], a[start + k + size // 2] * w
                a[start + k], a[start + k + size // 2] = u + v, u - v
                w *= w_step
        size *= 2
    return a


def spectrum(samples):
    """Complex amplitudes of harmonics 0..LENGTH/2-1 of one cycle."""
    n = len(samples)
    if n & (n - 1) == 0:
        bins = fft([complex(s) for s in samples])
        return [bins[k] / n if k < n // 2 else 0j for k in range(LENGTH // 2)]
    out = []
    for k in range(LENGTH // 2):
        if k >= n // 2:
            out.append(0j)
            continue
        out.append(sum(s * cmath.exp(-2j * math.pi * k * i / n) for i, s in enumerate(samples)) / n)
    return out


def synthesize(spec, harmonics, length):
    bins = [0j] * length
    for k in range(1, harmonics + 1):
        bins[k] = spec[k]
        bins[length - k] = spec[k].conjugate()
    return [v.real for v in fft(bins, inverse=True)]


def build_table(frames):
    """All frames of one wavetable: a list of frames, each a list of levels."""
    out = []
    for cycle in frames:
        spec = spectrum(cycle)
        out.append([synthesize(spec, level_harmonics(j), LEVEL_LENGTHS[j]) for j in range(LEVELS)])
    peak = max(abs(v) for frame in out for level in frame for v in level)
    if peak < 1e-9:
        raise ValueError('silent wavetable')
    gain = PEAK / peak
    return [[[max(-32767, min(32767, int(round(v * gain)))) for v in level] for level in frame] for frame in out]


def pick_frames(counts, budget=MAX_FRAMES, cap=MAX_TABLE_FRAMES):
    """Frames each wavetable keeps so that all fit: the largest give way first."""
    keep = [min(c, cap) for c in counts]
    while sum(keep) > budget:
        largest = max(range(len(keep)), key=lambda i: keep[i])
        if keep[largest] == 1:
            raise SystemExit('too many wavetables for the flash')
        keep[largest] -= 1
    return keep


def spaced(frames, keep):
    if keep >= len(frames):
        return frames
    if keep == 1:
        return frames[:1]
    return [frames[round(i * (len(frames) - 1) / (keep - 1))] for i in range(keep)]


def short_names(stems):
    prefixes = [''.join(ch for ch in s.upper() if ch.isalnum())[:3].ljust(3, '_') for s in stems]
    names, seen = [], {}
    for p in prefixes:
        if prefixes.count(p) == 1:
            names.append(p)
        else:
            seen[p] = seen.get(p, 0) + 1
            names.append(p[:2] + '123456789ABC'[seen[p] - 1])
    return names


def collect(sources, each=False):
    """(label, frames) per wavetable, in order."""
    tables = []
    for source in sources:
        source = Path(source)
        if source.is_dir():
            files = source_files(source)
            if not files:
                raise SystemExit(f'no .wav or .wt files in {source}')
            if each:
                tables += [(p.stem, file_frames(p)) for p in files]
            else:
                tables.append((source.name, [f for p in files for f in file_frames(p)]))
        else:
            tables.append((source.stem, file_frames(source)))
    if len(tables) > MAX_TABLES:
        print(f'{len(tables)} wavetables, using the first {MAX_TABLES}')
        tables = tables[:MAX_TABLES]
    return tables


def build(sources, out_root, each=False):
    if isinstance(sources, (str, Path)):
        sources = [sources]
    tables = collect(sources, each)
    names = short_names([label for label, _ in tables])
    keep = pick_frames([len(frames) for _, frames in tables])
    data = bytearray()
    for (_, frames), k in zip(tables, keep):
        for levels in build_table(spaced(frames, k)):
            for level in levels:
                data += struct.pack(f'<{len(level)}h', *level)
    name_block = b''.join(n.encode('ascii') + b'\0' for n in names).ljust(MAX_TABLES * 4, b'\0')
    frame_block = bytes(keep).ljust(MAX_TABLES, b'\0')
    crc = zlib.crc32(name_block + frame_block + data) & 0xFFFFFFFF
    header = MAGIC + struct.pack('<HHHHII', len(tables), LEVELS, LENGTH, 0, len(data), crc) + name_block + frame_block
    header = header.ljust(HEADER_BYTES, b'\0')
    target = Path(out_root) / 'WAVES'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'WAVES.BIN').write_bytes(header + data)
    for slot, (name, (label, frames), k) in enumerate(zip(names, tables, keep), 1):
        note = f' (of {len(frames)})' if k < len(frames) else ''
        print(f'{slot:2d}  {name}  {k:3d} frames{note}  {label}')
    print(f'{target / "WAVES.BIN"}: {len(header) + len(data)} bytes, {sum(keep)} of {MAX_FRAMES} frames, CRC {crc:08X}')
    return names, keep


if __name__ == '__main__':
    args = sys.argv[1:]
    each = bool(args) and args[0] == '--each'
    if each:
        args = args[1:]
    if len(args) < 2 or (each and len(args) != 2):
        raise SystemExit(__doc__)
    build(args[:-1], args[-1], each)
