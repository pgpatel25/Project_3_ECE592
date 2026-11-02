// physicalreg.cpp -- speculative physical-register-file (PRF) size probe.
//
// Idea (same as the ROB experiment, but with a different filler instruction):
//
//     loop:  L1: p1 = *p1          (cache miss, independent chain #1)
//            ICOUNT filler instructions
//            L2: p2 = *p2          (cache miss, independent chain #2)
//            ICOUNT filler instructions
//
// While L1 is waiting on memory it cannot retire, so every filler behind it
// must sit in the ROB *and* hold a renamed destination register.
//   * If L2 fits in the window together with L1, both misses overlap
//     -> ~1 memory latency per iteration.
//   * Once the fillers exhaust a resource (ROB or PRF), the front end stalls
//     before L2 is dispatched, the misses serialize
//     -> ~2 memory latencies per iteration.
// The ICOUNT where the time jumps is the capacity of the scarcest resource.
//   KIND 0 (nop)     : only consumes ROB entries         -> ROB size (control)
//   KIND 1 (add r64) : ROB + integer PRF entry (+flags)   -> integer PRF
//   KIND 2 (lea)     : ROB + integer PRF entry, no flags  -> integer PRF
//   KIND 3 (paddd x) : ROB + vector/FP PRF entry (SSE)    -> FP/SIMD PRF
//   KIND 4 (vpaddd y): ROB + vector/FP PRF entry (AVX2)   -> FP/SIMD PRF
//
// NOTE: the pair (L2 ... L2') must ALSO be separated by fillers (we put fillers
// after L2 too).  If L2 were immediately followed by the next iteration's L1,
// those two misses would overlap in the "small window" case as well and the
// step would disappear.
//
// Build:  g++ -O2 -march=native -std=c++17 -DKIND=1 -DICOUNT=100 physicalreg.cpp -o prf
// Run:    ./prf [buffer_MB=256] [iterations=20000] [trials=11]
// Output: kind,icount,median_tsc,min_tsc,max_tsc,median_ns   (per loop iteration)
//
// x86-64 + GCC/Clang only (uses r8-r15 and xmm8-xmm15).

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <numeric>
#include <random>
#include <vector>
#include <sys/mman.h>
#include <x86intrin.h>

#ifndef ICOUNT
#define ICOUNT 0
#endif
#ifndef KIND
#define KIND 1
#endif

#define BLOCKS (ICOUNT / 8)
#define REM    (ICOUNT % 8)

// Eight independent instructions per block (different destinations -> no long
// dependency chain, so filler execution time never limits the loop).
#if KIND == 0
  #define BLOCK8 "nop\n\t nop\n\t nop\n\t nop\n\t nop\n\t nop\n\t nop\n\t nop\n\t"
  #define ONE    "nop\n\t"
  #define CLOB   "memory", "cc"
  #define KIND_NAME "nop"
#elif KIND == 1
  #define BLOCK8 "add $1,%%r8\n\t add $1,%%r9\n\t add $1,%%r10\n\t add $1,%%r11\n\t" \
                 "add $1,%%r12\n\t add $1,%%r13\n\t add $1,%%r14\n\t add $1,%%r15\n\t"
  #define ONE    "add $1,%%r8\n\t"
  #define CLOB   "memory", "cc", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"
  #define KIND_NAME "int_add"
#elif KIND == 2
  #define BLOCK8 "lea 1(%%r8),%%r8\n\t lea 1(%%r9),%%r9\n\t lea 1(%%r10),%%r10\n\t lea 1(%%r11),%%r11\n\t" \
                 "lea 1(%%r12),%%r12\n\t lea 1(%%r13),%%r13\n\t lea 1(%%r14),%%r14\n\t lea 1(%%r15),%%r15\n\t"
  #define ONE    "lea 1(%%r8),%%r8\n\t"
  #define CLOB   "memory", "cc", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"
  #define KIND_NAME "int_lea"
#elif KIND == 3
  #define BLOCK8 "paddd %%xmm0,%%xmm8\n\t paddd %%xmm0,%%xmm9\n\t paddd %%xmm0,%%xmm10\n\t paddd %%xmm0,%%xmm11\n\t" \
                 "paddd %%xmm0,%%xmm12\n\t paddd %%xmm0,%%xmm13\n\t paddd %%xmm0,%%xmm14\n\t paddd %%xmm0,%%xmm15\n\t"
  #define ONE    "paddd %%xmm0,%%xmm8\n\t"
  #define CLOB   "memory", "cc", "xmm0", "xmm8", "xmm9", "xmm10", "xmm11", "xmm12", "xmm13", "xmm14", "xmm15"
  #define KIND_NAME "sse"
#elif KIND == 4
  #define BLOCK8 "vpaddd %%ymm0,%%ymm8,%%ymm8\n\t vpaddd %%ymm0,%%ymm9,%%ymm9\n\t" \
                 "vpaddd %%ymm0,%%ymm10,%%ymm10\n\t vpaddd %%ymm0,%%ymm11,%%ymm11\n\t" \
                 "vpaddd %%ymm0,%%ymm12,%%ymm12\n\t vpaddd %%ymm0,%%ymm13,%%ymm13\n\t" \
                 "vpaddd %%ymm0,%%ymm14,%%ymm14\n\t vpaddd %%ymm0,%%ymm15,%%ymm15\n\t"
  #define ONE    "vpaddd %%ymm0,%%ymm8,%%ymm8\n\t"
  #define CLOB   "memory", "cc", "xmm0", "xmm8", "xmm9", "xmm10", "xmm11", "xmm12", "xmm13", "xmm14", "xmm15"
  #define KIND_NAME "avx"
#else
  #error "KIND must be 0..4"
#endif

// ICOUNT filler instructions, expanded by the assembler (no loop overhead).
#define FILL ".rept %c2\n\t" BLOCK8 ".endr\n\t" \
             ".rept %c3\n\t" ONE    ".endr\n\t"

int main(int argc, char** argv) {
    const size_t mb         = argc > 1 ? std::strtoul(argv[1], nullptr, 10) : 256;
    const long   iterations = argc > 2 ? std::strtol(argv[2], nullptr, 10)  : 20000;
    const int    trials     = argc > 3 ? std::atoi(argv[3])                 : 11;

    const size_t bytes   = mb << 20;
    const size_t line    = 64;
    const size_t nlines  = bytes / line;
    const size_t perline = line / sizeof(void*);          // 8 pointers per line

    // Huge-page-aligned buffer (fewer TLB misses -> cleaner signal).
    void* raw = std::aligned_alloc(2u << 20, bytes);
    if (!raw) { std::fprintf(stderr, "alloc failed\n"); return 1; }
    madvise(raw, bytes, MADV_HUGEPAGE);
    void** buf = static_cast<void**>(raw);

    // Random single-cycle permutation over cache lines (Sattolo) so the
    // hardware prefetchers cannot predict the next address.
    std::vector<uint32_t> next(nlines);
    std::iota(next.begin(), next.end(), 0u);
    std::mt19937_64 rng(12345);
    for (size_t i = nlines - 1; i > 0; --i) {
        std::uniform_int_distribution<size_t> d(0, i - 1);
        std::swap(next[i], next[d(rng)]);
    }
    // next[] is now one big cycle; node i points to node next[i].
    for (size_t i = 0; i < nlines; ++i)
        buf[i * perline] = &buf[(size_t)next[i] * perline];

    // Two cursors half a cycle apart -> two independent, non-overlapping chains.
    uint32_t half = 0;
    for (size_t i = 0; i < nlines / 2; ++i) half = next[half];
    void** p1 = &buf[0];
    void** p2 = &buf[(size_t)half * perline];

    const long total = iterations * (trials + 1);
    if ((size_t)total >= nlines / 2)
        std::fprintf(stderr, "warning: chains wrap; raise buffer MB or lower iterations\n");

    std::vector<double> tsc_per_iter, ns_per_iter;
    for (int t = 0; t <= trials; ++t) {                    // trial 0 = warm-up
        auto  t0 = std::chrono::steady_clock::now();
        unsigned long long c0 = __rdtsc();
        _mm_lfence();
        for (long i = 0; i < iterations; ++i) {
            asm volatile(
                "mov (%0), %0\n\t"                         // L1 (miss)
                FILL
                "mov (%1), %1\n\t"                         // L2 (miss)
                FILL
                : "+r"(p1), "+r"(p2)
                : "i"(BLOCKS), "i"(REM)
                : CLOB);
        }
        _mm_lfence();
        unsigned long long c1 = __rdtsc();
        auto  t1 = std::chrono::steady_clock::now();
#if KIND == 4
        asm volatile("vzeroupper");
#endif
        if (t == 0) continue;
        tsc_per_iter.push_back((double)(c1 - c0) / iterations);
        ns_per_iter.push_back(std::chrono::duration<double, std::nano>(t1 - t0).count() / iterations);
    }

    std::sort(tsc_per_iter.begin(), tsc_per_iter.end());
    std::sort(ns_per_iter.begin(),  ns_per_iter.end());
    std::printf("%s,%d,%.2f,%.2f,%.2f,%.2f\n", KIND_NAME, ICOUNT,
                tsc_per_iter[tsc_per_iter.size() / 2], tsc_per_iter.front(),
                tsc_per_iter.back(), ns_per_iter[ns_per_iter.size() / 2]);

    // Keep the chains observable so nothing is optimized away.
    if ((uintptr_t)p1 == 1 && (uintptr_t)p2 == 1) std::puts("");
    std::free(raw);
    return 0;
}