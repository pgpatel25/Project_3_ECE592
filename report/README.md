# Track B Overleaf report

Upload ../track_b_overleaf.zip to Overleaf as a new project. Main file: main.tex.
Compiler: pdfLaTeX. main.pdf is the locally compiled preview.

The report covers exercises 1, 2, 3, 4, 5, and 14 (105 available points).
It describes existing evidence, not a claim that every requirement is complete.

Items requiring attention before submission:
- Replace Skylark CPU/model placeholders using its actual machine metadata.
- Four simple experiments have only one saved timing per condition. New repeated
  measurements are needed; loops inside one timing are not independent samples.
- Review the compiler/measurement limitations stated for each experiment.
- Enclave experiments were not performed. No unverified access limitation is claimed.
- Review author name and AI disclosure; add any earlier AI use to AI_USE_LOG.md.

Confirmed file mapping:
- Simple experiments: unsuffixed CSV = Artemisia; _skylark.csv = Skylark.
- PRF files: mymachine = Artemisia; skylark.ece.ncsu.edu = Skylark.

Regenerate plots: python3 build_figures.py (Python 3 and matplotlib).
Compile: pdflatex main.tex (twice for citations).
Figures use only the CSVs in data/. No new timings were taken for this report.

Sources are preserved in source/. The simple programs write fixed output names,
including _skylark on either host, so filenames do not automatically identify the
machine. For new runs, use a fresh working directory for every host and trial,
record hostname/lscpu and compiler flags, and preserve stdout and the CSV output.
Do not overwrite the original data. Fix the methodological issues described in
main.tex before treating newly compiled results as confirmation.

The repeated probe's runner can create a fresh sweep, for example:
  python3 source/run_prf_size.py --label HOSTNAME --outdir new_sweep \
    --kinds nop,int_add,sse --stop 400 --step 1 --reps 5 --trials 11 --jobs 2
Add --cpu N for a permitted quiet CPU; record its SMT sibling and activity.
This is a suggested future command, not a record of historical run settings.
The original internal trial samples were summarized by the benchmark; they cannot
be reconstructed from its median/min/max CSV columns.
