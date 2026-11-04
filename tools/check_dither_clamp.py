"""The drum voice dither (dither.c) at full scale.

The amp EG multiply ends in dither_process(). Near full scale the dither and
the error feedback reach 32768, which wrapped to -32768 in the int16 and
clicked (0.2.42 and the original LXR firmware). The check compiles the real
dither.c on the host with a stub random generator and feeds it full-scale DC,
a full-scale sine and a quiet sine: the output must stay on the side of the
input and within 8 LSB of it (noise-shaped dither alone reaches about 6).
--mutate removes the limit; the check must then fail.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"

STUB_HAL = r"""
#include <stdint.h>
"""
STUB_RANDOM = r"""
#include <stdint.h>
uint32_t GetRngValue();
"""
TEST = r"""
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "dither.h"

static uint32_t seed = 12345u;
uint32_t GetRngValue(){seed = seed*1664525u + 1013904223u; return seed;}
static unsigned checks, failures;
static void check(int ok, const char *name){checks++; if(!ok){failures++; printf("FAIL %s\n", name);}}

/* the worst distance between output and input in LSB, and whether the sign ever flipped */
static void run(const char *name, double amp, double freq, double dc)
{
	Dither d = {0};
	double worst = 0; int flipped = 0;
	for(long i=0;i<200000;i++)
	{
		const double x = dc + amp*sin(2*3.14159265358979*freq*i);
		const int16_t out = dither_process(&d, (float)x);
		const double err = fabs(out - x*32768.0);
		if(err > worst) worst = err;
		if((x > 0.5 && out < 0) || (x < -0.5 && out > 0)) flipped = 1;
	}
	char text[120];
	snprintf(text, sizeof(text), "%s: no wrap", name); check(!flipped, text);
	snprintf(text, sizeof(text), "%s: within 8 LSB (worst %.1f)", name, worst); check(worst <= 8.0, text);
}

int main(void)
{
	run("full scale DC", 0, 0, 32767.0/32768.0);
	run("negative full scale DC", 0, 0, -1.0);
	run("full scale sine", 32767.0/32768.0, 0.01, 0);
	run("full scale low sine", 32767.0/32768.0, 0.0003, 0);
	run("quiet sine", 0.25, 0.013, 0);
	{
		Dither d = {0}; long sum = 0;
		for(long i=0;i<200000;i++) sum += dither_process(&d, 0.f);
		check(labs(sum) < 200000/50, "silence has no DC");
	}
	printf("%s %u assertions\n", failures ? "DITHER FAIL" : "DITHER PASS", checks);
	return failures != 0;
}
"""


def main():
    code = (ROOT / 'Core/Src/Soundengine/DSPAudio/dither.c').read_text(encoding='utf-8')
    if '--mutate' in sys.argv:
        old = 'if(out > 32767) out = 32767;'
        assert old in code, 'mutation anchor'
        code = code.replace(old, '')
        code = code.replace('else if(out < -32768) out = -32768;', '')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        build = Path(tmp)
        (build / 'stm32f7xx_hal.h').write_text(STUB_HAL, encoding='utf-8')
        (build / 'random.h').write_text(STUB_RANDOM, encoding='utf-8')
        (build / 'dither.c').write_text(code.replace('"Soundengine/DSPAudio/dither.h"', '"dither.h"'), encoding='utf-8')
        (build / 'dither.h').write_text((ROOT / 'Core/Inc/Soundengine/DSPAudio/dither.h').read_text(encoding='utf-8'),
                                        encoding='utf-8')
        (build / 'test.c').write_text(TEST, encoding='utf-8')
        command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /I. '
                   f'/Fe:dither.exe test.c dither.c >build.log && .\\dither.exe')
        result = subprocess.run(command, shell=True, cwd=build)
        if result.returncode and (build / 'build.log').exists():
            print((build / 'build.log').read_text(errors='replace'))
    sys.exit(result.returncode != 0)


if __name__ == '__main__':
    main()
