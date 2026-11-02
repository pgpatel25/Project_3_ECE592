#define _POSIX_C_SOURCE 199309L
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define ITERATIONS 100000000

double get_time_diff(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

int main() {
    struct timespec start, end;
    double time_poor, time_manual;

    // Warmup
    for(volatile int i = 0; i < 10000000; i++);

    // ==========================================
    // TEST 1: Poorly Scheduled (Interleaved)
    // ==========================================
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int i = 0; i < ITERATIONS; i++) {
        // imul is slow, add is fast. The add depends on the imul right above it.
        asm volatile (
            "imul %%eax, %%eax \n\t" "add $1, %%eax \n\t"
            "imul %%ebx, %%ebx \n\t" "add $1, %%ebx \n\t"
            "imul %%eax, %%eax \n\t" "add $1, %%eax \n\t"
            "imul %%ebx, %%ebx \n\t" "add $1, %%ebx \n\t"
            "imul %%eax, %%eax \n\t" "add $1, %%eax \n\t"
            "imul %%ebx, %%ebx \n\t" "add $1, %%ebx \n\t"
            "imul %%eax, %%eax \n\t" "add $1, %%eax \n\t"
            "imul %%ebx, %%ebx \n\t" "add $1, %%ebx \n\t"
            "imul %%eax, %%eax \n\t" "add $1, %%eax \n\t"
            "imul %%ebx, %%ebx \n\t" "add $1, %%ebx \n\t"
            : : : "eax", "ebx"
        );
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    time_poor = get_time_diff(start, end);

    // ==========================================
    // TEST 2: Manually Scheduled (Grouped)
    // ==========================================
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int i = 0; i < ITERATIONS; i++) {
        // Slow independent instructions grouped together, fast ones grouped together.
        asm volatile (
            "imul %%eax, %%eax \n\t" "imul %%ebx, %%ebx \n\t"
            "add $1, %%eax \n\t"     "add $1, %%ebx \n\t"
            "imul %%eax, %%eax \n\t" "imul %%ebx, %%ebx \n\t"
            "add $1, %%eax \n\t"     "add $1, %%ebx \n\t"
            "imul %%eax, %%eax \n\t" "imul %%ebx, %%ebx \n\t"
            "add $1, %%eax \n\t"     "add $1, %%ebx \n\t"
            "imul %%eax, %%eax \n\t" "imul %%ebx, %%ebx \n\t"
            "add $1, %%eax \n\t"     "add $1, %%ebx \n\t"
            "imul %%eax, %%eax \n\t" "imul %%ebx, %%ebx \n\t"
            "add $1, %%eax \n\t"     "add $1, %%ebx \n\t"
            : : : "eax", "ebx"
        );
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    time_manual = get_time_diff(start, end);

    printf("Poorly Scheduled:   %.4f seconds\n", time_poor);
    printf("Manually Scheduled: %.4f seconds\n", time_manual);

    FILE *fp = fopen("results_oooe.csv", "w");
    if (fp) {
        fprintf(fp, "Test,Time_Seconds\n");
        fprintf(fp, "Poorly Scheduled,%f\n", time_poor);
        fprintf(fp, "Manually Scheduled,%f\n", time_manual);
        fclose(fp);
        printf("Saved to results_oooe.csv\n");
    }

    return 0;
}