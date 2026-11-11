from pathlib import Path
import re,subprocess,os
root=Path('.');out=root/'build/mod-target-audit';out.mkdir(parents=True,exist_ok=True)
s=(root/'Core/Src/Soundengine/DSPAudio/modulationNode.c').read_text();m=re.search(r'void modNode_setDestination\([^)]*\)\s*\{',s);i=m.end();d=1
while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
fn=s[m.start():i]
code='''#include <stdint.h>
#define FREEZE_MARK(f,v) ((void)0)\n#include <stdio.h>\n#include <stdlib.h>\n#define END_OF_SOUND_PARAMETERS 300\ntypedef union {uint32_t itg;float flt;} ptrValue;\ntypedef struct {uint16_t destination;ptrValue originalValue;float amount,lastVal;} ModulationNode;\ntypedef struct {void*ptr;uint8_t type;} Parameter;\nenum {TYPE_UINT8,TYPE_SPECIAL_F,TYPE_SPECIAL_FILTER_F,TYPE_FLT,TYPE_UINT32,TYPE_SPECIAL_P};\nParameter parameterArray[300];unsigned restores,resets;uint8_t oldValue=77,newValue=55;\nvoid paramArray_setParameter(uint16_t i,ptrValue v){if(i==3 && v.itg==77)restores++;}\nvoid modNode_resetTargets(void){resets++;}\n'''+fn+'''\nint main(void){parameterArray[3]=(Parameter){&oldValue,TYPE_UINT8};parameterArray[5]=(Parameter){&newValue,TYPE_UINT8};ModulationNode m={0};m.destination=3;m.originalValue.itg=77;modNode_setDestination(&m,5);if(m.destination!=5||m.originalValue.itg!=55||restores!=1||resets) return 1;modNode_setDestination(&m,999);if(m.destination!=0||restores!=1||resets)return 2;puts("MOD TARGET PASS");return 0;}\n'''
(out/'check.c').write_text(code)
if os.name=='nt':
 vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
 subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:check.exe check.c && check.exe',shell=True,cwd=out,check=True)
else:
 subprocess.run(['cc','check.c','-o','check'],cwd=out,check=True);subprocess.run([str(out/'check')],check=True)
