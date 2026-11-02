import csv
import math
import matplotlib.pyplot as plt
import sys

nops = []
ipc = []

# 1. Read the data
try:
    with open('results_fetch.csv', 'r') as file:
        reader = csv.reader(file)
        next(reader) 
        for row in reader:
            nops.append(str(row[0])) # Keep as string for categorical x-axis
            ipc.append(float(row[1]))
except FileNotFoundError:
    print("Error: 'results_fetch.csv' not found. Run benchmark_fetch first.")
    sys.exit(1)

# 2. Setup the plot
plt.figure(figsize=(9, 6))
bars = plt.bar(nops, ipc, color='#9467bd', width=0.5)

# 3. Format axes and title
plt.xlabel('Number of NOP Instructions per Loop Iteration', fontsize=12, fontweight='bold')
plt.ylabel('Instructions Per Cycle (IPC)', fontsize=12, fontweight='bold')
plt.title('Instruction Fetch Rate Benchmark\nEstimating Processor Fetch Width', fontsize=14)

# 4. Add data labels and estimate max fetch width
max_ipc = max(ipc)
estimated_fetch_width = math.ceil(max_ipc)

# Add a dashed line showing the hardware ceiling
plt.axhline(y=estimated_fetch_width, color='r', linestyle='--', alpha=0.7, 
            label=f'Theoretical Fetch Limit (~{estimated_fetch_width})')
plt.legend()
plt.ylim(0, estimated_fetch_width * 1.4)

for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + (estimated_fetch_width*0.02), 
             f'{yval:.2f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

# 5. Dynamic Conclusion Text
conclusion = (f"Result: As loop overhead diminishes, IPC plateaus at {max_ipc:.2f}.\n"
               f"Conclusion: The processor fetches {estimated_fetch_width} instructions per cycle.\n"
               "The front-end decode/fetch logic is the sole bottleneck for NOP execution.")

plt.figtext(0.5, 0.02, conclusion, ha="center", fontsize=11, 
            bbox={"facecolor":"#f8f9fa", "edgecolor":"#ced4da", "pad":8, "boxstyle":"round,pad=0.5"})

plt.subplots_adjust(bottom=0.25)

# 6. Save
filename = 'fetch_benchmark_plot.png'
plt.savefig(filename, dpi=300)
print(f"Plot successfully saved as {filename}")