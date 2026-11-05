#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define ITERATIONS 200000000

// Helper function to calculate elapsed time in seconds
double get_time_diff(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

int main() {
    struct timespec start, end;
    double time_indep, time_dep;

    // Warmup the CPU to ensure it ramps up from idle power states
    for(volatile int i = 0; i < 10000000; i++);

    // ==========================================
    // TEST 1: Independent Instructions
    // ==========================================
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int i = 0; i < ITERATIONS; i++) {
        asm volatile (
            "add $1, %%eax \n\t" "add $1, %%ebx \n\t"
            "add $1, %%ecx \n\t" "add $1, %%edx \n\t"
            "add $1, %%eax \n\t" "add $1, %%ebx \n\t"
            "add $1, %%ecx \n\t" "add $1, %%edx \n\t"
            "add $1, %%eax \n\t" "add $1, %%ebx \n\t"
            "add $1, %%ecx \n\t" "add $1, %%edx \n\t"
            "add $1, %%eax \n\t" "add $1, %%ebx \n\t"
            "add $1, %%ecx \n\t" "add $1, %%edx \n\t"
            "add $1, %%eax \n\t" "add $1, %%ebx \n\t"
            "add $1, %%ecx \n\t" "add $1, %%edx \n\t"
            : : : "eax", "ebx", "ecx", "edx"
        );
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    time_indep = get_time_diff(start, end);

    // ==========================================
    // TEST 2: Dependent Instructions
    // ==========================================
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int i = 0; i < ITERATIONS; i++) {
        asm volatile (
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            "add $1, %%eax \n\t" "add $1, %%eax \n\t"
            : : : "eax"
        );
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    time_dep = get_time_diff(start, end);

    // Output to console and CSV
    printf("Independent Test: %.4f seconds\n", time_indep);
    printf("Dependent Test:   %.4f seconds\n", time_dep);

    FILE *fp = fopen("results_skylark.csv", "w");
    if (fp) {
        fprintf(fp, "Test,Time_Seconds\n");
        fprintf(fp, "Independent,%f\n", time_indep);
        fprintf(fp, "Dependent,%f\n", time_dep);
        fclose(fp);
        printf("Saved to results_skylark.csv\n");
    } else {
        printf("Error: Could not open results_skylark.csv for writing.\n");
    }

    return 0;
}