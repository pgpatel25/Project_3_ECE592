#include <iostream>
#include <vector>
#include <numeric>
#include <x86intrin.h>

// ICOUNT is passed at compile time, e.g., g++ -DICOUNT=100 robsize.cpp
#ifndef ICOUNT
#define ICOUNT 10
#endif

// Define a large enough size to exceed the L3 cache (e.g., 64MB)
const int ARRAY_SIZE = 64 * 1024 * 1024 / sizeof(void*);
const int ITERATIONS = 10000;

int main() {
    // 1. Allocate a large array to ensure cache misses
    std::vector<void*> memory_pool(ARRAY_SIZE);
    
    // 2. Initialize pointer chasing (a randomized linked list to defeat prefetchers)
    // For simplicity, this example just links sequentially with a large stride, 
    // but randomizing the indices is highly recommended for exact results.
    int stride = 512; // 4096 bytes / 8 bytes per pointer
    for (int i = 0; i < ARRAY_SIZE; i++) {
        memory_pool[i] = &memory_pool[(i + stride) % ARRAY_SIZE];
    }

    // Set up two independent pointers far apart in the array
    void** p1 = &memory_pool[0];
    void** p2 = &memory_pool[ARRAY_SIZE / 2];

    // Warmup phase (omitted for brevity)
    
    // 3. Measurement phase
    unsigned long long start = __rdtsc();

    for (int i = 0; i < ITERATIONS; i++) {
        // GCC Inline Assembly
        // %0 is p1, %1 is p2, %c2 is the compile-time constant ICOUNT
        asm volatile (
            "mov (%0), %0 \n\t"        // Load 1 (Cache miss)
            ".rept %c2 \n\t"           // Repeat the next instruction ICOUNT times
            "nop \n\t"                 // Filler instruction
            ".endr \n\t"               // End repeat
            "mov (%1), %1 \n\t"        // Load 2 (Cache miss)
            : "+r" (p1), "+r" (p2)     // Output/Input operands
            : "i" (ICOUNT)             // Compile-time constant operand
            : "memory"                 // Clobbers
        );
    }

    unsigned long long end = __rdtsc();
    
    // Calculate cycles per iteration
    double cycles_per_iter = (double)(end - start) / ITERATIONS;
    std::cout << ICOUNT << "," << cycles_per_iter << std::endl;

    return 0;
}