"""The end of the amp EG (SlopeEg2.c) and the pitch EG (Decay.c).

The decay subtracts one step per call. The last step went below 0, and the
slope curve turned that into a negative gain, about (1+slope) steps deep,
before the next call returned 0: a click at the end of every note with
slope above about 11 (original LXR code). The check compiles the real
SlopeEg2.c and Decay.c on the host and runs every slope and decay setting,
also in repeat mode: the output never goes below 0, and it never rises while
decaying. The pitch EG slope at 127 divided by zero; every slope must give a
finite curve.
--mutate removes the limit at 0 and the slope limit; the check must then fail.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"

ENV = r"""
#include <stdint.h>
#define IN_ITCM_RAM
#define USE_BIG_SAMPLE_BUFFER 1
"""
TEST = r"""
#include <stdio.h>
#include <math.h>
#include "SlopeEg2.h"
#include "Decay.h"

static unsigned checks, failures;
static void check(int ok, const char *name){checks++; if(!ok){failures++; printf("FAIL %s\n", name);}}

int main(void)
{
	double lowest = 0; int rises = 0, ends = 1;
	for(unsigned slope=0;slope<128;slope++)
		for(unsigned decay=0;decay<128;decay+=3)
			for(unsigned repeat=0;repeat<3;repeat++)
			{
				SlopeEg2 eg; slopeEg2_init(&eg);
				slopeEg2_setSlope(&eg,(uint8_t)slope);
				slopeEg2_setAttack(&eg,(uint8_t)(decay/2),0);
				slopeEg2_setDecay(&eg,(uint8_t)decay,0);
				eg.repeat = (uint8_t)repeat;
				slopeEg2_trigger(&eg);
				double previous = 2;
				long n;
				for(n=0;n<2000000 && !(eg.state == EG_D && eg.value <= 0);n++)
				{
					const double v = slopeEg2_calc(&eg);
					if(v < lowest) lowest = v;
					if(eg.state == EG_D && v > previous + 1e-12) rises++;
					previous = eg.state == EG_D ? v : 2;
				}
				ends &= slopeEg2_calc(&eg) == 0.0;
			}
	check(lowest >= 0, "the amp EG never gives a negative gain");
	check(!rises, "the amp EG never rises while decaying");
	check(ends, "the amp EG ends at 0");
	{
		float lowestPitch = 0; int pitchEnds = 1, finite = 1;
		for(unsigned slope=0;slope<128;slope++)
			for(unsigned decay=0;decay<128;decay+=3)
			{
				DecayEg eg; DecayEg_init(&eg);
				DecayEg_setSlope(&eg,(uint8_t)slope);
				DecayEg_setDecay(&eg,(uint8_t)decay);
				DecayEg_trigger(&eg);
				for(long n=0;n<2000000 && eg.value>0;n++)
				{
					const float v = DecayEg_calc(&eg);
					if(v < lowestPitch) lowestPitch = v;
					finite &= isfinite(v) != 0;
				}
				pitchEnds &= DecayEg_calc(&eg) == 0.f;
			}
		check(lowestPitch >= 0, "the pitch EG never bends below its base");
		check(pitchEnds, "the pitch EG ends at 0");
		check(finite, "every pitch EG slope gives a finite curve, also 127");
	}
	printf("%s %u assertions\n", failures ? "ENVELOPE FAIL" : "ENVELOPE PASS", checks);
	return failures != 0;
}
"""


def local(text):
    """Drop the firmware includes; env.h stands in for HAL and config."""
    text = re.sub(r'#include "stm32f7xx_hal.h"', '#include "env.h"', text)
    text = re.sub(r'#include "Soundengine/config.h"', '', text)
    return re.sub(r'#include "Soundengine/DSPAudio/(\w+\.h)"', r'#include "\1"', text)


def main():
    slope = (ROOT / 'Core/Src/Soundengine/DSPAudio/SlopeEg2.c').read_text(encoding='utf-8')
    decay = (ROOT / 'Core/Src/Soundengine/DSPAudio/Decay.c').read_text(encoding='utf-8')
    if '--mutate' in sys.argv:
        old = '\t\t\tif(val < 0) val = 0;\n'
        assert slope.replace('\r\n', '\n').count(old) == 2, 'mutation anchor'
        slope = slope.replace('\r\n', '\n').replace(old, '')
        old = '\t\tif(val < 0) val = 0;\n'
        assert decay.replace('\r\n', '\n').count(old) == 1, 'mutation anchor'
        decay = decay.replace('\r\n', '\n').replace(old, '')
        old = '\tif(amount > 0.9995f) amount = 0.9995f;\n'
        assert old in decay, 'mutation anchor'
        decay = decay.replace(old, '')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        build = Path(tmp)
        (build / 'env.h').write_text(ENV, encoding='utf-8')
        for name in ('SlopeEg2.h', 'Decay.h'):
            (build / name).write_text(local((ROOT / 'Core/Inc/Soundengine/DSPAudio' / name).read_text(encoding='utf-8')),
                                      encoding='utf-8')
        (build / 'SlopeEg2.c').write_text(local(slope), encoding='utf-8')
        (build / 'Decay.c').write_text(local(decay), encoding='utf-8')
        (build / 'test.c').write_text(TEST, encoding='utf-8')
        command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /I. /D_CRT_SECURE_NO_WARNINGS '
                   f'/Fe:envelope.exe test.c SlopeEg2.c Decay.c >build.log && .\\envelope.exe')
        result = subprocess.run(command, shell=True, cwd=build)
        if result.returncode and (build / 'build.log').exists():
            print((build / 'build.log').read_text(errors='replace'))
    sys.exit(result.returncode != 0)


if __name__ == '__main__':
    main()
