"""Plot OoOE results from any working directory."""
import argparse
import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt


SCRIPT_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="CSV file to plot (defaults to results_oooe_skylark.csv or results_oooe_skylark.cvs beside this script)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SCRIPT_DIR / "oooe_benchmark_plot_skylark.png",
        help="path for the output plot",
    )
    args = parser.parse_args()

    input_path = args.input
    if input_path is None:
        candidates = [
            SCRIPT_DIR / "results_oooe_skylark.csv",
            SCRIPT_DIR / "results_oooe_skylark.cvs",
        ]
        input_path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])

    if not input_path.is_file():
        parser.error(f"input CSV not found: {input_path}")

    try:
        with input_path.open(newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            required_columns = {"Test", "Time_Seconds"}
            if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
                parser.error("input CSV must contain Test and Time_Seconds columns")
            rows = list(reader)
        labels = [row["Test"] for row in rows]
        times = [float(row["Time_Seconds"]) for row in rows]
    except (OSError, csv.Error, TypeError, ValueError) as error:
        parser.error(f"could not read input CSV {input_path}: {error}")

    if not rows:
        parser.error(f"input CSV contains no results: {input_path}")
    if not all(math.isfinite(value) for value in times):
        parser.error(f"input CSV contains a non-finite Time_Seconds value: {input_path}")

    figure, axis = plt.subplots()
    axis.bar(labels, times)
    axis.set_title("OoOE Benchmark Results")
    axis.set_ylabel("Time (seconds)")
    figure.tight_layout()
    figure.savefig(args.output)
    plt.close(figure)
    print(f"Saved plot to {args.output}")


if __name__ == "__main__":
    main()
