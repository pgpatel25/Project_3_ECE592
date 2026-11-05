#define _POSIX_C_SOURCE 199309L
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define ARRAY_SIZE 32768
#define ITERATIONS 10000

// Comparison function for qsort
int compare(const void *a, const void *b) {
    return ( *(int*)a - *(int*)b );
}

double get_time_diff(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

int main() {
    int data[ARRAY_SIZE];
    struct timespec start, end;
    double time_unsorted, time_sorted;
    long long sum = 0;

    // Generate random data between 0 and 255
    for (int i = 0; i < ARRAY_SIZE; i++) {
        data[i] = rand() % 256;
    }

    // ==========================================
    // TEST 1: Unpredictable (Unsorted Array)
    // ==========================================
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int iter = 0; iter < ITERATIONS; iter++) {
        for (int i = 0; i < ARRAY_SIZE; i++) {
            if (data[i] >= 128) {
                sum ^= data[i]; // Bitwise operation to prevent CMOV optimization
            }
        }
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    time_unsorted = get_time_diff(start, end);

    // Sort the array for the next test
    qsort(data, ARRAY_SIZE, sizeof(int), compare);

    // ==========================================
    // TEST 2: Predictable (Sorted Array)
    // ==========================================
    sum = 0; // Reset sum
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int iter = 0; iter < ITERATIONS; iter++) {
        for (int i = 0; i < ARRAY_SIZE; i++) {
            if (data[i] >= 128) {
                sum ^= data[i];
            }
        }
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    time_sorted = get_time_diff(start, end);

    printf("Unpredictable (Unsorted): %.4f seconds\n", time_unsorted);
    printf("Predictable (Sorted):     %.4f seconds\n", time_sorted);

    FILE *fp = fopen("results_branch_skylark.csv", "w");
    if (fp) {
        fprintf(fp, "Test,Time_Seconds\n");
        fprintf(fp, "Unpredictable,%f\n", time_unsorted);
        fprintf(fp, "Predictable,%f\n", time_sorted);
        fclose(fp);
        printf("Saved to results_branch_skylark.csv\n");
    }

    return 0;
}