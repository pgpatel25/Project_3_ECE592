import csv
import matplotlib.pyplot as plt
import sys

tests = []
times = []

# 1. Read the data
try:
    with open('results.csv', 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row
        for row in reader:
            tests.append(row[0])
            times.append(float(row[1]))
except FileNotFoundError:
    print("Error: 'results.csv' not found. Compile and run benchmark.c first.")
    sys.exit(1)

# 2. Setup the plot
plt.figure(figsize=(8, 6))
bars = plt.bar(tests, times, color=['#2ca02c', '#d62728'], width=0.5)

# 3. Format axes and title
plt.ylabel('Execution Time (Seconds)', fontsize=12, fontweight='bold')
plt.title('CPU Pipeline Data Hazard Benchmark\nIndependent vs. Dependent Instructions', fontsize=14)
plt.ylim(0, max(times) * 1.3) # Add 30% headroom for text labels
plt.grid(axis='y', linestyle='--', alpha=0.7)

# 4. Add data labels on top of the bars
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + (max(times)*0.02), 
             f'{yval:.4f} s', ha='center', va='bottom', fontsize=12, fontweight='bold')

# 5. Add a conclusion text box for the report
ratio = times[1] / times[0]
conclusion = (f"Result: The Dependent sequence took {ratio:.2f}x longer.\n"
               "Conclusion: The processor is pipelined/superscalar.\n"
               "Data dependencies caused pipeline stalls, drastically reducing throughput.")
plt.figtext(0.5, 0.03, conclusion, ha="center", fontsize=11, 
            bbox={"facecolor":"#f0f0f0", "edgecolor":"#cccccc", "pad":8, "boxstyle":"round,pad=0.5"})

# Adjust layout to fit the text box at the bottom
plt.subplots_adjust(bottom=0.25)

# 6. Save and show
filename = 'pipeline_benchmark_plot.png'
plt.savefig(filename, dpi=300)
print(f"Plot successfully saved as {filename}")