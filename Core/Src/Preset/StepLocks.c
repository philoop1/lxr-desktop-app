/* SPDX-License-Identifier: GPL-3.0-only
 * Bounded, shared lists. No heap, compaction, or per-pattern pool. Copy/undo
 * retain a list; edits detach only when shared. All critical sections are
 * bounded by PLOCK_MAX, independent of pool capacity and pattern count.
 */
#include "Preset/StepLocks.h"
#ifdef STM32F765xx
#include "stm32f7xx.h"
static uint32_t lock_enter(void) { uint32_t p=__get_PRIMASK(); __disable_irq(); return p; }
static void lock_leave(uint32_t p) { __set_PRIMASK(p); }
#else
static uint32_t lock_enter(void) { return 0; }
static void lock_leave(uint32_t p) { (void)p; }
#endif

typedef struct { uint16_t packed, next, refs; } LockNode;
static LockNode nodes[PLOCK_CAPACITY];
static uint16_t freeHead, freeCount;
_Static_assert(sizeof(Step)==7 && sizeof(LockNode)==6, "lock storage layout");

static uint16_t head(const Step *s)
{
    uint16_t h=(uint16_t)(s->param1Nr | ((uint16_t)s->param2Nr<<8));
    return s->param1Val==128 && s->param2Val>=3 && s->param2Val<=PLOCK_MAX &&
           h && h<=PLOCK_CAPACITY ? h : 0;
}
static LockNode *node(uint16_t h) { return &nodes[h-1]; }
static void release(uint16_t h)
{
    if(!h || --node(h)->refs)return;
    while(h) {
        uint16_t next=node(h)->next;
        node(h)->next=freeHead; freeHead=h; ++freeCount; h=next;
    }
}
static uint8_t read_locked(const Step *s, StepLock *out)
{
    uint16_t h=head(s);
    uint8_t n=0;
    if(h) {
        while(h && n<s->param2Val) {
            uint16_t p=node(h)->packed;
            out[n++]=(StepLock){(uint8_t)p,(uint8_t)(p>>8)};
            h=node(h)->next;
        }
    } else {
        if(s->param1Nr!=PLOCK_NONE)out[n++]=(StepLock){s->param1Nr,s->param1Val&127u};
        if(s->param2Nr!=PLOCK_NONE) {
            if(n && out[0].destination==s->param2Nr)out[0].value=s->param2Val&127u;
            else out[n++]=(StepLock){s->param2Nr,s->param2Val&127u};
        }
    }
    return n;
}
void plock_init(void)
{
    for(uint16_t i=0;i<PLOCK_CAPACITY;i++) {
        nodes[i].next=i+1<PLOCK_CAPACITY?i+2:0; nodes[i].refs=0;
    }
    freeHead=1; freeCount=PLOCK_CAPACITY;
}
uint8_t plock_read(const Step *s, StepLock out[PLOCK_MAX])
{
    uint32_t irq=lock_enter(); uint8_t n=read_locked(s,out); lock_leave(irq); return n;
}
uint8_t plock_count(const Step *s)
{
    uint32_t irq=lock_enter();
    uint8_t n=head(s)?s->param2Val:(s->param1Nr!=PLOCK_NONE)+
        (s->param2Nr!=PLOCK_NONE && s->param2Nr!=s->param1Nr);
    lock_leave(irq); return n;
}
uint16_t plock_available(void)
{
    uint32_t irq=lock_enter(); uint16_t n=freeCount; lock_leave(irq); return n;
}
uint8_t plock_replace(Step *s, const StepLock *locks, uint8_t count)
{
    uint8_t seen[32]={0};
    if(count>PLOCK_MAX)return 0;
    for(uint8_t i=0;i<count;i++) {
        uint8_t d=locks[i].destination, bit=(uint8_t)(1u<<(d&7));
        if(d==PLOCK_NONE || locks[i].value>127 || (seen[d>>3]&bit))return 0;
        seen[d>>3]|=bit;
    }
    uint32_t irq=lock_enter();
    uint16_t old=head(s);
    if(count<=2) {
        s->param1Nr=count?locks[0].destination:PLOCK_NONE;
        s->param1Val=count?locks[0].value:0;
        s->param2Nr=count>1?locks[1].destination:PLOCK_NONE;
        s->param2Val=count>1?locks[1].value:0;
        release(old); lock_leave(irq); return 1;
    }
    /* Reuse an exclusively owned list. Updating/deleting works with a full
     * pool; a shared edit either allocates the whole replacement or changes
     * nothing (including refcounts and the free list). */
    uint8_t reuse=old && node(old)->refs==1;
    uint8_t have=reuse?s->param2Val:0;
    if(freeCount < (count>have ? count-have : 0)) { lock_leave(irq); return 0; }
    uint16_t ids[PLOCK_MAX], h=reuse?old:0;
    for(uint8_t i=0;i<count;i++) {
        if(h) { ids[i]=h; h=node(h)->next; }
        else { ids[i]=freeHead; freeHead=node(freeHead)->next; --freeCount; }
    }
    if(h) { node(h)->refs=1; release(h); }
    for(uint8_t i=0;i<count;i++) {
        node(ids[i])->packed=(uint16_t)(locks[i].destination | ((uint16_t)locks[i].value<<8));
        node(ids[i])->next=i+1<count?ids[i+1]:0;
        node(ids[i])->refs=i?0:1;
    }
    s->param1Nr=(uint8_t)ids[0]; s->param2Nr=(uint8_t)(ids[0]>>8);
    s->param1Val=128; s->param2Val=count;
    if(!reuse)release(old);
    lock_leave(irq); return 1;
}
uint8_t plock_set(Step *s, uint8_t d, uint8_t v)
{
    if(d==PLOCK_NONE || v>127)return 0;
    uint32_t irq=lock_enter();
    StepLock locks[PLOCK_MAX]; uint8_t n=read_locked(s,locks), i;
    for(i=0;i<n;i++)if(locks[i].destination==d)break;
    if(i==n && n==PLOCK_MAX) { lock_leave(irq); return 0; }
    locks[i]=(StepLock){d,v}; if(i==n)++n;
    uint8_t ok=plock_replace(s,locks,n); lock_leave(irq); return ok;
}
uint8_t plock_remove(Step *s, uint8_t d)
{
    uint32_t irq=lock_enter();
    StepLock locks[PLOCK_MAX]; uint8_t n=read_locked(s,locks);
    for(uint8_t i=0;i<n;i++)if(locks[i].destination==d) {
        for(uint8_t j=i+1;j<n;j++)locks[j-1]=locks[j];
        --n; break;
    }
    uint8_t ok=plock_replace(s,locks,n); lock_leave(irq); return ok;
}
void plock_clear(Step *s) { (void)plock_replace(s,0,0); }
void plock_copyLocks(Step *dst, const Step *src)
{
    uint32_t irq=lock_enter();
    uint16_t old=head(dst), h=head(src);
    if(h)++node(h)->refs;
    dst->param1Nr=src->param1Nr; dst->param1Val=src->param1Val;
    dst->param2Nr=src->param2Nr; dst->param2Val=src->param2Val;
    release(old); lock_leave(irq);
}
void plock_copy(Step *dst, const Step *src)
{
    uint32_t irq=lock_enter();
    plock_copyLocks(dst,src);
    dst->note=src->note; dst->prob=src->prob; dst->volume=src->volume;
    lock_leave(irq);
}
void plock_copySteps(Step *dst, const Step *src, uint16_t count)
{
    for(uint16_t i=0;i<count;i++)plock_copy(dst+i,src+i);
}
void plock_import(Step *dst, const Step *legacy)
{
    Step copy=*legacy;
    /* Untrusted bytes can never become a pool reference. */
    copy.param1Val&=127; copy.param2Val&=127;
    uint32_t irq=lock_enter(); plock_clear(dst); *dst=copy; lock_leave(irq);
}
void plock_export(const Step *src, Step *legacy)
{
    StepLock locks[PLOCK_MAX];
    uint32_t irq=lock_enter();
    if(!head(src)) {
        *legacy=*src; legacy->param1Val&=127; legacy->param2Val&=127;
        lock_leave(irq); return;
    }
    uint8_t n=read_locked(src,locks);
    *legacy=*src;
    legacy->param1Nr=n?locks[0].destination:PLOCK_NONE; legacy->param1Val=n?locks[0].value:0;
    legacy->param2Nr=n>1?locks[1].destination:PLOCK_NONE; legacy->param2Val=n>1?locks[1].value:0;
    lock_leave(irq);
}
uint8_t plock_slot(Step *s, uint8_t slot, uint8_t destinationField, uint8_t value)
{
    if(slot>1)return 0;
    uint32_t irq=lock_enter();
    /* Preserve empty inline slots for the legacy editor. */
    if(!head(s)) {
        if(destinationField) {
            if(slot)s->param2Nr=value; else s->param1Nr=value;
        } else {
            if(slot)s->param2Val=value&127u; else s->param1Val=value&127u;
        }
        lock_leave(irq); return 1;
    }
    StepLock locks[PLOCK_MAX]; uint8_t n=read_locked(s,locks);
    if(destinationField) {
        if(value==PLOCK_NONE) {
            for(uint8_t i=slot+1;i<n;i++)locks[i-1]=locks[i];
            --n;
        } else {
            locks[slot].destination=value;
            /* Merge duplicate destinations, keeping the edited slot's value. */
            for(uint8_t i=0;i<n;i++)if(i!=slot && locks[i].destination==value) {
                for(uint8_t j=i+1;j<n;j++)locks[j-1]=locks[j];
                --n;
                break;
            }
        }
    } else locks[slot].value=value&127u;
    uint8_t ok=plock_replace(s,locks,n); lock_leave(irq); return ok;
}
