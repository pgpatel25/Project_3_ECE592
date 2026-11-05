# Project 3: Microarchitecture experiments

These four Linux x86-64 experiments measure evidence for pipelined execution,
out-of-order execution, branch prediction, and effective instruction delivery.
The original `rob_size` experiments are separate and have not been reviewed here.

## Build and run

Requires GCC/G++, GNU make/binutils, Python 3.9+, and matplotlib.

```sh
make
make check
python3 scripts/run_benchmarks.py
```

The runner builds into `build/` and creates a new timestamped `runs/` directory
containing CSV samples, PNG figures, JSON summaries, disassembly, logs, and
machine/source/binary provenance. It never replaces the old tracked binaries,
CSVs, or figures in the experiment folders; those are **legacy results**, not
results from the revised experiments. Do not execute those old binaries.
Generated builds and runs are git-ignored. Use `--output-dir runs/my_run` to choose
a new directory, `--cpu N` to pin to a permitted logical CPU, and `--trials 15` for
more samples. `--quick` checks functionality only.

```sh
# Run and plot a single experiment, from the repository root:
./build/benchmark_branch --trials 9 --output /tmp/branch.csv
python3 branch_predictor/plot_branch.py --input /tmp/branch.csv --output /tmp/branch.png

# Supported by each executable:
./build/benchmark_fetch --help
# --iterations N --trials N --cpu N --output FILE --case NAME --no-counters
```

`--iterations` means 64 multiplies for pipeline/OoOE, one 65,536-element pass for
branch, or one logical batch of 16,384 NOPs for fetch. In fetch, each batch repeats
the selected static NOP block enough times to execute the same total NOP count.
This equal-work design amortizes measurement overhead for every block size.
`--case` selects one case for separate investigation; the comparative plot requires
all cases. The standalone executable's default output is relative to the working
directory; the plotting script's default input is relative to its own folder.
Prefer explicit paths or the runner.

## What was wrong and what changed

| Experiment | Problem in the original | Revised comparison |
| --- | --- | --- |
| `pipline_test/benchmark.cpp` | Independent vs dependent adds conflated superscalar execution with pipelining; one timed sample and no initialized register operands. | 64 integer multiplies with 1, 2, 4, or 8 independent recurrence chains; initialized registers and explicit condition-code clobbers. |
| `OoOE_test/benchmark_oooe.cpp` | Two chains and a hardcoded 1.15 timing threshold did not establish instruction reordering. | Identical four-chain dependency graphs in grouped and interleaved instruction orders, plus a single-chain serial control. |
| `branch_predictor/benchmark_branch.cpp` | The accumulator was never observed. XOR does not prevent if-conversion or elimination of the entire computation. | Explicit assembly conditional branch; shuffled and sorted copies with exactly equal taken fractions; two branchless controls and checked checksums. |
| `instruction_width/benchmark_fetch.c` | Unordered RDTSC reads, TSC ticks mislabeled as core cycles, and rounding observed throughput up to a purported hardware fetch limit. | Ordered timestamps, real core-cycle counters when available, equal dynamic NOP work across static block sizes, and 1-byte/8-byte NOP encodings. Report measured throughput without inventing a physical width. |
| All four Python plot scripts | Single bars and categorical conclusions from arbitrary timing thresholds. | Shared validated parser, all samples, median/range plots, paired timing ratios with bootstrap intervals, and qualified interpretations. |

## Measurement protocol

The common C/C++ harness pins to one allowed CPU before warmup and timing,
warms every selected kernel, rotates/reverses case order across trials, and writes
all samples. It records elapsed wall time, ordered TSC ticks, and a group of
user-mode hardware counters: core cycles, retired instructions, branches, and
branch misses. Counters include the small measurement wrapper around the kernel;
large batches amortize that overhead. Work counts include only the experimental
multiplies/elements/NOPs, not loop-control instructions. The retired-instruction
counter includes loop control and wrapper instructions.

Counter reads with missing data, zero running time, or multiplexing are rejected,
not silently scaled. If the group cannot be opened, timing still works and counter
columns are blank. `--no-counters` exercises this fallback explicitly. The plots
use core cycles only when every sample has a valid count; otherwise they use
nanoseconds/work or NOPs/TSC tick. **TSC ticks are not core cycles.** No CPU
frequency assumption is needed for valid core-cycle measurements.

Plot whiskers are the sample range, not confidence intervals. JSON summaries
include deterministic paired-bootstrap 95% intervals for median wall-time ratios
when at least five trials exist. These describe within-run variation, not all
systematic error. Repeat whole runs to assess stability; inspect raw samples and
compare cycle-based measurements if frequency or scheduling varies.

The supplied snapshot identifies a Xeon Gold 5420+, SMT enabled, isolated CPUs
28–55 and 84–111, and historical frequency settings. Treat that snapshot as
context, not proof of current operating conditions. The live validation process
could use CPU 0 but not those isolated CPUs; CPU 0 shares a physical core with CPU
56. Its live policy differed from the snapshot. Metadata records the actual
allowed affinity mask, selected CPU, SMT sibling, and frequency policy. Prefer a
quiet permitted core with an idle sibling. No system-wide settings are changed.

## How to interpret each experiment

### Pipeline overlap

For a recurrence `x = x * 3`, each multiply must await the previous result. With
multiple independent registers, different multiplies can overlap. The approximate
model is cost per multiply = max(dependent latency / chain count, reciprocal
throughput), plus loop/measurement overhead. A clear fall followed by a plateau
is evidence of overlapped execution consistent with pipelining. It does not
identify total pipeline depth; multiple execution units and scheduling also
influence throughput. Report dependent latency and independent throughput
separately rather than claiming a CPU's entire pipeline was uniquely identified.

### Out-of-order execution

`grouped` performs 16 dependent multiplies on register A, then 16 on B, C, and D.
`interleaved` performs A, B, C, D repeatedly, with the same 16 updates per register.
The instructions and per-register dependency graphs are identical; only their
order changes. A strict in-order issuer must wait behind the early dependent
multiplies in the grouped version, while an out-of-order scheduler can issue later
ready work from other registers. The serial control executes all 64 multiplies
on A, establishing that the recurrence has a measurable latency cost.

Grouped approximately matching interleaved **and both beating serial** is strong
evidence for out-of-order scheduling in this experiment. Similarity alone is not
proof; conversely, a slower grouped version does not prove an in-order CPU:
finite scheduling windows, port contention, and front-end effects can also cause
it. Inspect the saved disassembly to verify compiler scheduling cannot explain
the result.

### Branch prediction

The sorted and shuffled arrays contain the same 32,768 zeros and 32,768 ones.
Both branch cases execute the same kernel with the same taken fraction, data
volume, and checksum. The random case changes branch predictability. The
branchless pair checks whether data order alone changes access cost. Data creation
and shuffling are outside the timed region; seed 592 makes the input reproducible.
The random sequence is reused, so predictor learning remains a possible effect;
it should be checked using measured miss counts rather than assuming every random
branch is unpredictable.

A large random/sorted timing gap, nearly identical branchless controls, and a much
higher miss count on random data support branch prediction. Report misses per
element: the generic branch counters also count loop branches, so misses divided
by *all branches* is not the data-dependent branch's misprediction probability.
The branchless kernel has a different instruction mix; compare order effects
within each pair rather than attributing the entire branch/branchless difference
to misprediction. A missing gap is inconclusive.

### Effective instruction delivery (fetch assignment)

Sweep 16, 64, 256, 1,024, 4,096, and 16,384 static NOP instructions, using both
1-byte and 8-byte encodings. All cases execute the same dynamic NOP count. Loops
are aligned to 64 bytes. The byte footprints span small hot loops, larger decoded
instruction footprints, and (for the longest 8-byte case) 128 KiB of code. This
helps reveal instruction-length and instruction-cache effects.

Compute `NOPs / measured core cycles`; optionally inspect `Instructions /
Core_Cycles` for total retired IPC including loop control. Hot loops may be served
by the decoded-uop cache rather than ordinary instruction-byte fetch/decode.
Larger footprints reduce that shortcut but can introduce instruction-cache
bottlenecks. Retirement can also cap the result. Therefore this is an estimate of
**effective NOP delivery throughput**, not an isolated measurement of physical
fetch width. Do not use `ceil(max IPC)` as a theoretical hardware limit. If a
report requires a single estimate, quote the measured plateau, its encoding and
footprint, and these limitations; do not substitute a processor specification for
an experimental result.

## Validation and references

`make check` verifies computed checksums, work counts, the number of multiplies
and NOPs in generated machine code, retention of the conditional branch, missing
counter fallback, plot generation, duplicate CSV rejection, and invalid CLI inputs.
Full-run observations are in [EXPERIMENT_REVIEW.md](EXPERIMENT_REVIEW.md).

Architecture/timing background: [Intel Optimization Reference Manual](https://cdrdv2-public.intel.com/821612/248966-Optimization-Reference-Manual-V1-050.pdf).
Counter semantics and grouping: [Linux perf_event_open documentation](https://man7.org/linux/man-pages/man2/perf_event_open.2.html).
