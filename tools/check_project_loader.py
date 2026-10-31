"""Compile the real FAT wildcard selector with a deterministic directory spy."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "loader-audit"
OUT.mkdir(parents=True, exist_ok=True)
source = (ROOT / "Core/Src/Preset/presetManager.c").read_text()
start = source.index("static FRESULT preset_makeFileNameLoad(char *buf, uint8_t num, uint8_t type)\n{")
brace = source.index("{", start)
depth = 0
end = brace
for end in range(brace, len(source)):
    depth += (source[end] == "{") - (source[end] == "}")
    if depth == 0:
        end += 1
        break
actual = source[start:end]

harness = r'''
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
typedef int FRESULT;
typedef int DIR;
typedef int FIL;
typedef struct { char fname[32]; } FILINFO;
#define FR_OK 0
#define FR_NO_FILE 4
#define FA_OPEN_EXISTING 0
#define FA_READ 1
#define FEXT_SOUND 1
#define FEXT_PAT 2
#define FEXT_ALL 3
#define FEXT_SONG 4
#define FEXT_PROJ 5
#define PSTR(x) (x)
static FIL SDFile;
static const char *entries[4];
static unsigned cursor;
static char opened[32];
static void numtostrpu_2Bytes(char *p, unsigned num, char pad) {
    p[0]=(char)(pad+num/10); p[1]=(char)(pad+num%10);
}
static FRESULT f_findfirst(DIR *d, FILINFO *f, const char *path, const char *mask) {
    (void)d; (void)path; (void)mask; cursor=0;
    strcpy(f->fname, entries[0] ? entries[0] : ""); return FR_OK;
}
static FRESULT f_findnext(DIR *d, FILINFO *f) {
    (void)d; cursor++; strcpy(f->fname, entries[cursor] ? entries[cursor] : "");
    return FR_OK;
}
static FRESULT f_closedir(DIR *d) { (void)d; return FR_OK; }
static FRESULT f_open(FIL *f, const char *name, int flags) {
    (void)f; (void)flags; strcpy(opened,name); return FR_OK;
}
'''
tests = r'''
static void check(const char *a, const char *b, const char *expected) {
    char mask[13]={0};
    entries[0]=a; entries[1]=b; entries[2]=NULL; entries[3]=NULL;
    opened[0]=0;
    FRESULT result=preset_makeFileNameLoad(mask,0,FEXT_PAT);
    if((expected && (result!=FR_OK || strcmp(opened,expected))) ||
       (!expected && (result!=FR_NO_FILE || opened[0]))) {
        fprintf(stderr,"FAIL: %s/%s -> %s, result=%d\n",a?a:"",b?b:"",opened,result);
        exit(1);
    }
}
int main(void) {
    check("00-.PAT","00-LXR.PAT","00-LXR.PAT");
    check("00-LXR.PAT","00-.PAT","00-LXR.PAT");
    check("00-.PAT",NULL,"00-.PAT");
    check("00-ZUPTY.PAT",NULL,"00-ZUPTY.PAT");
    check(NULL,NULL,NULL);
    puts("PROJECT LOADER PASS: 5 real-source FAT selection cases");
    return 0;
}
'''
(OUT / "project_loader.c").write_text(harness + actual + tests)
if os.name == "nt":
    vsdev = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / (
        "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat")
    subprocess.run(f'call "{vsdev}" -arch=x64 >nul && cl /nologo /W3 /TC '
                   '/Fe:project_loader.exe project_loader.c && project_loader.exe',
                   shell=True, cwd=OUT, check=True)
else:
    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra",
                    "-o", "project_loader", "project_loader.c"], cwd=OUT, check=True)
    subprocess.run([str(OUT / "project_loader")], cwd=OUT, check=True)
