#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

#define ITERATIONS 1000000

// Macros to easily generate massive blocks of NOPs
#define NOP "nop \n\t"
#define NOP5   NOP NOP NOP NOP NOP
#define NOP10  NOP5 NOP5
#define NOP50  NOP10 NOP10 NOP10 NOP10 NOP10
#define NOP100 NOP50 NOP50
#define NOP200 NOP100 NOP100
#define NOP400 NOP200 NOP200
#define NOP600 NOP400 NOP200
#define NOP800 NOP400 NOP400

// Function to read the CPU cycle counter (RDTSC)
static inline uint64_t rdtsc() {
    unsigned int lo, hi;
    __asm__ __volatile__ ("rdtsc" : "=a" (lo), "=d" (hi));
    return ((uint64_t)hi << 32) | lo;
}

int main() {
    uint64_t start, end;
    uint64_t cycles_10, cycles_50, cycles_100, cycles_200, cycles_400;
    
    // Warmup the CPU 
    for(volatile int i = 0; i < 10000000; i++);

    // TEST 1: 10 NOPs
    start = rdtsc();
    for (int i = 0; i < ITERATIONS; i++) { __asm__ __volatile__ (NOP10); }
    end = rdtsc();
    cycles_10 = end - start;

    // TEST 2: 50 NOPs
    start = rdtsc();
    for (int i = 0; i < ITERATIONS; i++) { __asm__ __volatile__ (NOP50); }
    end = rdtsc();
    cycles_50 = end - start;

    // TEST 3: 100 NOPs
    start = rdtsc();
    for (int i = 0; i < ITERATIONS; i++) { __asm__ __volatile__ (NOP100); }
    end = rdtsc();
    cycles_100 = end - start;

    // TEST 4: 200 NOPs
    start = rdtsc();
    for (int i = 0; i < ITERATIONS; i++) { __asm__ __volatile__ (NOP200); }
    end = rdtsc();
    cycles_200 = end - start;

    // TEST 5: 400 NOPs
    start = rdtsc();
    for (int i = 0; i < ITERATIONS; i++) { __asm__ __volatile__ (NOP400); }
    end = rdtsc();
    cycles_400 = end - start;

    //TEST 6: 600 NOPs
    start = rdtsc();
    for (int i = 0; i < ITERATIONS; i++) { __asm__ __volatile__ (NOP600); }
    end = rdtsc();
    uint64_t cycles_600 = end - start;

    //TEST 7: 800 NOPs
    start = rdtsc();
    for (int i = 0; i < ITERATIONS; i++) { __asm__ __volatile__ (NOP800); }
    end = rdtsc();
    uint64_t cycles_800 = end - start;

    // Calculate Instructions Per Cycle (IPC)
    double ipc_10  = (10.0  * ITERATIONS) / cycles_10;
    double ipc_50  = (50.0  * ITERATIONS) / cycles_50;
    double ipc_100 = (100.0 * ITERATIONS) / cycles_100;
    double ipc_200 = (200.0 * ITERATIONS) / cycles_200;
    double ipc_400 = (400.0 * ITERATIONS) / cycles_400;
    double ipc_600 = (600.0 * ITERATIONS) / cycles_600;
    double ipc_800 = (800.0 * ITERATIONS) / cycles_800;

    FILE *fp = fopen("results_fetch.csv", "w");
    if (fp) {
        fprintf(fp, "NOP_Count,IPC\n");
        fprintf(fp, "10,%f\n", ipc_10);
        fprintf(fp, "50,%f\n", ipc_50);
        fprintf(fp, "100,%f\n", ipc_100);
        fprintf(fp, "200,%f\n", ipc_200);
        fprintf(fp, "400,%f\n", ipc_400);
        fprintf(fp, "600,%f\n", ipc_600);
        fprintf(fp, "800,%f\n", ipc_800);
        fclose(fp);
        printf("Saved to results_fetch.csv\n");
    }

    return 0;
}