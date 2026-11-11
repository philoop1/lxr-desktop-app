"""0.2.72: production StepLocks.h/.c as text for the host harnesses."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def plock_source(with_header=True):
    h = (ROOT / 'Core/Inc/Preset/StepLocks.h').read_text(encoding='latin-1')
    c = (ROOT / 'Core/Src/Preset/StepLocks.c').read_text(encoding='latin-1')
    h = h.replace('#include "Preset/SeqStep.h"', '')
    c = c.replace('#include "Preset/StepLocks.h"', '')
    c = re.sub(r'_Static_assert\([^;]*\);', '', c)  # MSVC C mode
    return (h + '\n' if with_header else '') + c + '\n'
