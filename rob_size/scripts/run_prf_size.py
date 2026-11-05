#!/usr/bin/env python3
"""run_prf_size.py -- sweep physicalreg.cpp over ICOUNT and locate the PRF knee.

Examples
  python3 run_prf_size.py                                  # nop(ROB control)+int+sse, 0..300
  python3 run_prf_size.py --kinds nop,int_lea --stop 400 --cpu 2
  python3 run_prf_size.py --kinds avx --step 1 --reps 5 --label skylake

Outputs (in --outdir, default prf_results/):
  prf_<label>_<kind>.csv   raw data (one row per ICOUNT per repetition)
  prf_<label>.png          plot of all kinds (needs matplotlib)
  prf_<label>_summary.txt  knee estimates
"""
import argparse, csv, os, platform, shutil, statistics, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

KINDS = {"nop": 0, "int_add": 1, "int_lea": 2, "sse": 3, "avx": 4}
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "physicalreg.cpp")


def compile_one(args, kind, n, bindir):
    exe = os.path.join(bindir, f"prf_{kind}_{n}")
    cmd = [args.cxx, "-O2", "-std=c++17", "-march=native",
           f"-DKIND={KINDS[kind]}", f"-DICOUNT={n}", SRC, "-o", exe]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None, "\n    ".join(r.stderr.strip().splitlines()[:6]) or "compile error"
    return exe, None


def run_one(args, exe):
    def pin():
        if args.cpu is not None and hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(0, {args.cpu})
    r = subprocess.run([exe, str(args.mb), str(args.iters), str(args.trials)],
                       capture_output=True, text=True, preexec_fn=pin)
    if r.returncode != 0:
        return None
    k, n, med, mn, mx, ns = r.stdout.strip().split(",")
    return int(n), float(med), float(mn), float(mx), float(ns)


def find_knee(xs, ys):
    """Return (knee50, start10, end90, low, high) or None if no clear step."""
    m = max(3, len(ys) // 10)
    low, high = statistics.median(ys[:m]), statistics.median(ys[-m:])
    if high < 1.3 * low:
        return None

    def cross(frac):
        thr = low + frac * (high - low)
        for x, y in zip(xs, ys):
            if y >= thr:
                return x
        return None
    return cross(0.5), cross(0.1), cross(0.9), low, high


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", default="nop,int_add,sse",
                    help=f"comma list from {list(KINDS)}; nop = ROB control")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--stop", type=int, default=1000, help="inclusive; go well past the expected knee")
    ap.add_argument("--step", type=int, default=2)
    ap.add_argument("--reps", type=int, default=3, help="process launches per ICOUNT (median is used)")
    ap.add_argument("--mb", type=int, default=256, help="pointer-chase buffer size (>> L3)")
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--trials", type=int, default=11)
    ap.add_argument("--cpu", type=int, default=None, help="pin to this logical CPU")
    ap.add_argument("--cxx", default="g++")
    ap.add_argument("--outdir", default="prf_results")
    ap.add_argument("--label", default=platform.node() or "machine")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4, help="parallel compiles")
    args = ap.parse_args()

    if shutil.which(args.cxx) is None:
        sys.exit(f"compiler '{args.cxx}' not found. On RHEL/Fedora: sudo dnf install gcc-c++ "
                 f"(or pass --cxx <your C++ compiler>)")
    if not os.path.exists(SRC):
        sys.exit(f"{SRC} not found: put physicalreg.cpp in the same directory as this script")
    probe = subprocess.run([args.cxx, "-x", "c++", "-std=c++17", "-fsyntax-only", "-"],
                           input="#include <x86intrin.h>\nint main(){}", capture_output=True, text=True)
    if probe.returncode != 0:
        sys.exit("C++ compiler cannot build a basic x86 program:\n" + probe.stderr[:800])

    os.makedirs(args.outdir, exist_ok=True)
    bindir = os.path.join(args.outdir, "bin")
    os.makedirs(bindir, exist_ok=True)
    counts = list(range(args.start, args.stop + 1, args.step))
    summary, curves = [], {}

    for kind in [k.strip() for k in args.kinds.split(",") if k.strip()]:
        if kind not in KINDS:
            sys.exit(f"unknown kind {kind}; choose from {list(KINDS)}")
        print(f"[{kind}] compiling {len(counts)} binaries ...", flush=True)
        with ThreadPoolExecutor(args.jobs) as ex:
            built = list(ex.map(lambda n: compile_one(args, kind, n, bindir), counts))
        if built[0][0] is None:
            msg = f"[{kind}] SKIPPED, compile failed:\n    {built[0][1]}"
            print(msg); summary.append(msg); continue

        rows, xs, ys = [], [], []
        for n, (exe, _) in zip(counts, built):
            res = [r for r in (run_one(args, exe) for _ in range(args.reps)) if r]
            if not res:
                continue
            for r in res:
                rows.append((kind, n, *r[1:]))
            xs.append(n); ys.append(statistics.median(r[1] for r in res))
            print(f"  {kind:8s} ICOUNT={n:4d}  {ys[-1]:9.1f} TSC cycles/iter", flush=True)
            os.remove(exe)

        with open(os.path.join(args.outdir, f"prf_{args.label}_{kind}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["kind", "icount", "median_tsc", "min_tsc", "max_tsc", "median_ns"])
            w.writerows(rows)

        curves[kind] = (xs, ys)
        k = find_knee(xs, ys)
        if k is None:
            msg = f"[{kind}] no clear step in 0..{args.stop} (try a larger --stop)"
        else:
            knee, lo, hi, a, b = k
            msg = (f"[{kind}] plateau {a:.0f} -> {b:.0f} TSC cyc/iter; step at ICOUNT ~ {knee} "
                   f"(10%-90% transition {lo}..{hi}); approx. window capacity ~ {knee + 2} entries "
                   f"(ICOUNT fillers + the 2 loads)")
        print(msg); summary.append(msg)

    summary.append("")
    summary.append("Interpretation: nop knee = ROB size. A register-writing kind with a knee BELOW the nop "
                   "knee is limited by the PRF; capacity is speculative entries only "
                   "(published PRF size - knee = architectural/non-speculative registers).")
    with open(os.path.join(args.outdir, f"prf_{args.label}_summary.txt"), "w") as f:
        f.write("\n".join(summary) + "\n")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure(figsize=(8, 5))
        for kind, (xs, ys) in curves.items():
            plt.plot(xs, ys, marker=".", label=kind)
        plt.xlabel("filler instructions between loads (ICOUNT)")
        plt.ylabel("TSC cycles per iteration")
        plt.title(f"PRF/ROB probe - {args.label}")
        plt.grid(alpha=.3); plt.legend()
        out = os.path.join(args.outdir, f"prf_{args.label}.png")
        plt.savefig(out, dpi=150, bbox_inches="tight")
        print("plot:", out)
    except ImportError:
        print("matplotlib not installed; skipping plot (CSV files are still written)")


if __name__ == "__main__":
    main()