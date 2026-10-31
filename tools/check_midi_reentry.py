"""Inject incoming MIDI during production UART dispatch, as kit loading does."""
from pathlib import Path
import os,re,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/midi-reentry-audit';OUT.mkdir(parents=True,exist_ok=True)
src=(ROOT/'Core/Src/Soundengine/MIDI/Uart.c').read_text()
m=re.search(r'void uart_processMidi\(\)\s*\{',src);pos=m.end();depth=1
while depth:
 depth+=(src[pos]=='{')-(src[pos]=='}');pos+=1
body=src[m.start():pos]
code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
unsigned readAt,written,depth,maxDepth,seen;int fifo_midiRx;
uint8_t fifo_bufferOut(int *fifo,uint8_t *data){(void)fifo;if(readAt==written)return 0;*data=(uint8_t)readAt++;return 1;}
void uart_processMidi(void);
void midiParser_parseUartData(uint8_t data){
 depth++;if(depth>maxDepth)maxDepth=depth;
 if(data!=seen++){puts("FIFO dispatch order changed");exit(1);}
 /* A kit sends parameters and calls soundengine_process, which drains UART.
  * More clocks/bytes can arrive while that handler is still on the stack. */
 if(written<128)written++;
 uart_processMidi();
 depth--;
}
'''+body+r'''
int main(void){
 written=1;uart_processMidi();
 if(maxDepth!=1||seen!=128||readAt!=written){printf("FAIL depth=%u seen=%u queued=%u\n",maxDepth,seen,written);return 1;}
 /* The guard must be released after the outer drain completes. */
 written++;uart_processMidi();
 if(seen!=129||depth){puts("Guard did not release");return 1;}
 puts("MIDI REENTRY PASS: 129 bytes in order, handler depth 1, no bytes dropped");return 0;
}
'''
(OUT/'contract.c').write_text(code)
if os.name=='nt':
 vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
 subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /Fe:contract.exe contract.c && contract.exe',shell=True,cwd=OUT,check=True)
else:
 subprocess.run(['cc','-o','contract','contract.c'],cwd=OUT,check=True);subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
