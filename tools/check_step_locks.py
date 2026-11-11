"""0.2.72 step locks: production StepLocks.c on the host.

Inline <=2, pooled 3..16, shared lists with copy-on-write, a full pool never
changes anything it cannot finish, the 16 limit, legacy import/export and the
P1/P2 slot editor. Every scenario ends with the whole pool free again.
"""
from pathlib import Path
from plock_source import plock_source
import os, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/step-locks-audit'
OUT.mkdir(parents=True, exist_ok=True)
step = (ROOT / 'Core/Inc/Preset/SeqStep.h').read_text(encoding='latin-1').replace('#include "main.h"', '')
code = '#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n' + step + plock_source()
code += r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static Step steps[300];
static uint8_t has(const Step*s,uint8_t d,uint8_t v){StepLock l[PLOCK_MAX];uint8_t n=plock_read(s,l);
 for(uint8_t i=0;i<n;i++)if(l[i].destination==d)return l[i].value==v;return 0;}
static void fill(Step*s,uint8_t n,uint8_t base){for(uint8_t i=0;i<n;i++)check(plock_set(s,(uint8_t)(base+i),(uint8_t)(i*7&127)),"fill");}
static void clearAll(void){for(int i=0;i<300;i++)plock_clear(&steps[i]);check(plock_available()==PLOCK_CAPACITY,"no leak");}
int main(void){
 plock_init();
 for(int i=0;i<300;i++){memset(&steps[i],0,sizeof(Step));steps[i].param1Nr=steps[i].param2Nr=PLOCK_NONE;}
 Step *a=&steps[0],*b=&steps[1],*c=&steps[2];
 check(plock_available()==PLOCK_CAPACITY&&plock_count(a)==0,"empty start");
 /* inline: two locks need no pool */
 check(plock_set(a,10,5)&&plock_set(a,20,6),"two inline");
 check(plock_count(a)==2&&plock_available()==PLOCK_CAPACITY&&a->param1Val<=127&&a->param2Val<=127,"inline layout");
 check(plock_set(a,10,9)&&has(a,10,9)&&plock_count(a)==2,"inline update");
 /* third lock goes to the pool */
 check(plock_set(a,30,7)&&plock_count(a)==3&&plock_available()==PLOCK_CAPACITY-3,"pooled");
 check(a->param1Val==128&&a->param2Val==3,"pooled marker");
 check(has(a,10,9)&&has(a,20,6)&&has(a,30,7),"pooled values");
 check(plock_set(a,20,100)&&has(a,20,100)&&plock_available()==PLOCK_CAPACITY-3,"pooled update in place");
 /* 16 limit */
 fill(a,13,40);check(plock_count(a)==16,"sixteen");
 check(!plock_set(a,99,1)&&plock_count(a)==16,"17th refused");
 check(plock_set(a,40,77)&&has(a,40,77),"update at the limit works");
 StepLock many[PLOCK_MAX+1];for(int i=0;i<17;i++)many[i]=(StepLock){(uint8_t)(100+i),1};
 check(!plock_replace(b,many,17)&&plock_count(b)==0,"replace above limit refused");
 /* copy shares, edit detaches */
 uint16_t freeBefore=plock_available();
 a->note=33;plock_copy(b,a);check(plock_available()==freeBefore&&b->note==33&&plock_count(b)==16,"copy shares");
 check(plock_set(b,40,1)&&plock_available()==freeBefore-16,"edit of a shared list detaches");
 check(has(a,40,77)&&has(b,40,1),"copy on write keeps the source");
 plock_clear(b);check(plock_available()==freeBefore,"detached list freed");
 plock_copy(b,a);plock_clear(a);check(plock_available()==freeBefore&&plock_count(b)==16&&has(b,40,77),"shared survives one release");
 plock_copySteps(c,b,1);plock_copySteps(b,c+1,1);check(plock_count(b)==0&&plock_count(c)==16,"copySteps releases the old list");
 clearAll();
 /* invalid input changes nothing */
 StepLock bad[3]={{1,1},{1,2},{3,3}};check(!plock_replace(a,bad,3)&&plock_count(a)==0,"duplicate destination refused");
 bad[1]=(StepLock){2,128};check(!plock_replace(a,bad,3),"value above 127 refused");
 check(!plock_set(a,PLOCK_NONE,1)&&!plock_set(a,1,200),"bad set refused");
 /* full pool */
 int used=0;while(plock_available()>=16){fill(&steps[used],16,0);used++;}
 check(used==PLOCK_CAPACITY/16&&plock_available()==0,"pool fills exactly");
 Step *x=&steps[used];check(plock_set(x,1,1)&&plock_set(x,2,2),"inline works on a full pool");
 check(!plock_set(x,3,3)&&plock_count(x)==2&&has(x,1,1)&&has(x,2,2),"third lock on a full pool leaves the step untouched");
 check(plock_set(&steps[0],5,99)&&has(&steps[0],5,99),"owned update on a full pool");
 plock_copy(x,&steps[0]);check(plock_available()==0,"share on a full pool");
 check(!plock_set(x,5,1)&&has(x,5,99)&&has(&steps[0],5,99),"shared edit on a full pool fails cleanly");
 plock_clear(x);check(plock_remove(&steps[0],5)&&plock_count(&steps[0])==15&&plock_available()==1,"remove frees a node");
 clearAll();
 /* remove down to inline */
 fill(a,5,10);for(uint8_t d=10;d<13;d++)check(plock_remove(a,d),"remove");
 check(plock_count(a)==2&&a->param1Val<=127&&plock_available()==PLOCK_CAPACITY&&has(a,13,21)&&has(a,14,28),"back to inline");
 check(plock_remove(a,77)&&plock_count(a)==2,"removing a missing lock is harmless");
 clearAll();
 /* untrusted legacy bytes never become a pool reference */
 Step legacy={0};legacy.param1Nr=1;legacy.param1Val=128;legacy.param2Nr=0;legacy.param2Val=5;
 plock_import(a,&legacy);check(plock_available()==PLOCK_CAPACITY&&a->param1Val==0&&plock_count(a)==2,"import masks pool markers");
 legacy.param1Nr=2;legacy.param1Val=200;legacy.param2Nr=PLOCK_NONE;plock_import(a,&legacy);check(a->param1Val==72,"import masks values");
 fill(a,4,50);Step out;plock_export(a,&out);
 check(out.param1Val<=127&&out.param2Val<=127&&out.param1Nr!=PLOCK_NONE&&plock_count(&out)==2,"export keeps two base locks");
 /* P1/P2 slot editor on a pooled step */
 plock_clear(a);fill(a,4,60);
 check(plock_slot(a,0,0,111)&&plock_count(a)==4,"slot value");
 StepLock l[PLOCK_MAX];plock_read(a,l);check(l[0].value==111&&l[0].destination==60,"slot 0 edited");
 check(plock_slot(a,1,1,62)&&plock_count(a)==3,"slot destination merges a duplicate");
 check(plock_slot(a,0,1,PLOCK_NONE)&&plock_count(a)==2&&plock_available()==PLOCK_CAPACITY,"slot clear back to inline");
 plock_clear(b);check(plock_slot(b,1,1,9)&&b->param2Nr==9&&b->param1Nr==PLOCK_NONE,"inline slot keeps empty slot 1");
 check(!plock_slot(b,2,0,1),"slot 2 refused");
 clearAll();
 printf("STEP LOCKS PASS %u assertions\n",checks);return 0;}
'''
(OUT / 'contract.c').write_text(code, encoding='latin-1')
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:contract.exe contract.c && contract.exe',
                   shell=True, cwd=OUT, check=True)
else:
    subprocess.run(['cc', '-std=c11', '-o', 'contract', 'contract.c'], cwd=OUT, check=True)
    subprocess.run([str(OUT / 'contract')], cwd=OUT, check=True)
