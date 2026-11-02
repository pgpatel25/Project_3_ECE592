import csv
import matplotlib.pyplot as plt
import sys

tests = []
times = []

# 1. Read the data
try:
    with open('results_oooe.csv', 'r') as file:
        reader = csv.reader(file)
        next(reader) 
        for row in reader:
            tests.append(row[0])
            times.append(float(row[1]))
except FileNotFoundError:
    print("Error: 'results_oooe.csv' not found. Run benchmark_oooe first.")
    sys.exit(1)

# 2. Setup the plot
plt.figure(figsize=(8, 6))
bars = plt.bar(tests, times, color=['#ff7f0e', '#1f77b4'], width=0.5)

# 3. Format axes
plt.ylabel('Execution Time (Seconds)', fontsize=12, fontweight='bold')
plt.title('Out-of-Order Execution (OoOE) Benchmark\nPoor Scheduling vs. Manual Scheduling', fontsize=14)
plt.ylim(0, max(times) * 1.3) 
plt.grid(axis='y', linestyle='--', alpha=0.7)

# 4. Add data labels
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + (max(times)*0.02), 
             f'{yval:.4f} s', ha='center', va='bottom', fontsize=12, fontweight='bold')

# 5. Dynamic Conclusion Logic
ratio = times[0] / times[1]

if ratio < 1.15:
    conclusion_text = (f"Result: The Poorly Scheduled code was only {ratio:.2f}x slower.\n"
                       "Conclusion: The processor supports Out-of-Order Execution.\n"
                       "The hardware dynamically reordered the poor schedule on the fly,\n"
                       "matching the performance of the manually optimized code.")
else:
    conclusion_text = (f"Result: The Poorly Scheduled code was {ratio:.2f}x slower.\n"
                       "Conclusion: The processor is STRICTLY IN-ORDER.\n"
                       "It blindly stalled at every dependency instead of looking ahead.")

plt.figtext(0.5, 0.02, conclusion_text, ha="center", fontsize=11, 
            bbox={"facecolor":"#f8f9fa", "edgecolor":"#ced4da", "pad":8, "boxstyle":"round,pad=0.5"})

plt.subplots_adjust(bottom=0.28)

# 6. Save
filename = 'oooe_benchmark_plot.png'
plt.savefig(filename, dpi=300)
print(f"Plot successfully saved as {filename}")