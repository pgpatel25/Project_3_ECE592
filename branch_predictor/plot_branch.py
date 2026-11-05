"""Plot revised branch results from any working directory."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from plot_results import main

if __name__ == '__main__':
    main('branch', Path(__file__).resolve().parent, 'results_branch.csv', 'branch_benchmark_plot.png')
