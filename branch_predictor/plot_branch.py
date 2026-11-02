import csv
import matplotlib.pyplot as plt
import sys

tests = []
times = []

# 1. Read the data
try:
    with open('results_branch.csv', 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row
        for row in reader:
            tests.append(row[0])
            times.append(float(row[1]))
except FileNotFoundError:
    print("Error: 'results_branch.csv' not found. Compile and run benchmark_branch first.")
    sys.exit(1)

# 2. Setup the plot
plt.figure(figsize=(8, 6))
# Red for the slow unpredictable run, Green for the fast predictable run
bars = plt.bar(tests, times, color=['#d62728', '#2ca02c'], width=0.5)

# 3. Format axes and title
plt.ylabel('Execution Time (Seconds)', fontsize=12, fontweight='bold')
plt.title('CPU Branch Prediction Benchmark\nUnsorted (Unpredictable) vs. Sorted (Predictable)', fontsize=14)
plt.ylim(0, max(times) * 1.3) # Add headroom for text labels
plt.grid(axis='y', linestyle='--', alpha=0.7)

# 4. Add data labels on top of the bars
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + (max(times)*0.02), 
             f'{yval:.4f} s', ha='center', va='bottom', fontsize=12, fontweight='bold')

# 5. Dynamic Conclusion Logic
ratio = times[0] / times[1]

if ratio > 1.2:
    conclusion = (f"Result: The Unpredictable (unsorted) data took {ratio:.2f}x longer.\n"
                   "Conclusion: The processor uses Branch Prediction.\n"
                   "Random data caused constant mispredictions and pipeline flushes,\n"
                   "while sorted data allowed the predictor to achieve near-perfect accuracy.")
else:
    conclusion = (f"Result: The Unpredictable data was only {ratio:.2f}x slower.\n"
                   "Conclusion: No branch prediction detected (or optimized out).\n"
                   "The processor evaluated every branch in real-time without guessing.")

plt.figtext(0.5, 0.02, conclusion, ha="center", fontsize=11, 
            bbox={"facecolor":"#f8f9fa", "edgecolor":"#ced4da", "pad":8, "boxstyle":"round,pad=0.5"})

# Adjust layout to fit the text box at the bottom
plt.subplots_adjust(bottom=0.28)

# 6. Save the plot
filename = 'branch_benchmark_plot.png'
plt.savefig(filename, dpi=300)
print(f"Plot successfully saved as {filename}")