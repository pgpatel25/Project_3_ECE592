import subprocess
import os
import pandas as pd
import matplotlib.pyplot as plt

# Define paths relative to the 'scripts' directory
SRC_DIR = "../src"
CPP_FILE = os.path.join(SRC_DIR, "benchmark.cpp")
EXE_FILE = os.path.join(SRC_DIR, "benchmark")
CSV_FILE = os.path.join(SRC_DIR, "results2.csv")
PLOT_FILE = "rob_size_artimesia2.pdf"

def run_benchmark():
    # Initialize the CSV file with headers
    with open(CSV_FILE, "w") as f:
        f.write("ICOUNT,Cycles\n")

    # Loop from 0 to 1000. Using a step of 10 for efficiency.
    # Change to range(0, 1001, 1) if you need every single integer.
    for icount in range(0, 1001, 5):
        print(f"Compiling and running ICOUNT = {icount}...")
        
        # 1. Compile the code with the specific ICOUNT
        compile_cmd = ["g++", "-O3", f"-DICOUNT={icount}", CPP_FILE, "-o", EXE_FILE]
        subprocess.run(compile_cmd, check=True)
        
        # 2. Run the compiled executable, pinned to core 0
        run_cmd = ["taskset", "-c", "0", EXE_FILE]
        
        # Append the stdout (which prints "ICOUNT,Cycles") directly to the CSV
        with open(CSV_FILE, "a") as f:
            subprocess.run(run_cmd, stdout=f, check=True)

def plot_results():
    print(f"Reading data from {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)
    
    # Create the plot
    plt.figure(figsize=(10, 6))
    
    # Plot data with the requested legend label
    plt.plot(df["ICOUNT"], df["Cycles"], marker='o', markersize=4, linestyle='-', label="artimesia")
    
    # Format axes and titles
    plt.xlabel("Filler Instructions (ICOUNT)")
    plt.ylabel("Average Cycles per Iteration")
    plt.title("ROB Size Measurement on artimesia")
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()
    
    # Save strictly as a PDF
    plt.savefig(PLOT_FILE, format="pdf", bbox_inches="tight")
    print(f"Plot successfully saved to {PLOT_FILE} in the scripts directory.")

if __name__ == "__main__":
    # Ensure matplotlib is installed, or alert the user
    try:
        import matplotlib
    except ImportError:
        print("Error: matplotlib is not installed. Please run 'pip install matplotlib pandas' first.")
        exit(1)
        
    run_benchmark()
    plot_results()