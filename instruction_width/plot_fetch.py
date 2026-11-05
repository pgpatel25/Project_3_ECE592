"""Plot revised fetch results from any working directory."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from plot_results import main

if __name__ == '__main__':
    main('fetch', Path(__file__).resolve().parent, 'results_fetch.csv', 'fetch_benchmark_plot.png')
