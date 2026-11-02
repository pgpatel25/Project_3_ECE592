#!/usr/bin/env python3
"""
artemisia_snapshot.py v3 - record artemisia's configuration before an experiment.

    conda activate myenv
    sudo python3 artemisia_snapshot.py --user Joshua
    sudo python3 artemisia_snapshot.py --user Joshua --no-onecli     # skip the ~1 min BMC query

Writes ONE new CSV per run, two columns: key,value. Keys are dotted:
    meta.*                       date, scientist, host, tool status
    system.*                     kernel, cmdline, SMT, isolation, THP, NUMA, tuned ...
    conda.*                      active conda env, its python, every conda and pip package
    uefi.<Group>.<Setting>       every line of `onecli config show`  (e.g. uefi.Processors.TurboMode)
    uncore.<domain>.*            uncore frequency limits per die
    cpu.cpu<N>.*                 per-CPU: governor, min/max/base freq, fixed freq, turbo, EPP,
                                 idle states, prefetcher MSR bits ...
Then prints a per-CPU summary.

Sources: Lenovo OneCLI (UEFI), cpupower (per-CPU frequency/idle; sysfs fills any gaps), MSR 0x1A4 and
0xE1 per CPU (runtime prefetcher / UMWAIT overrides that OneCLI cannot see), sysfs/procfs for the rest.
"""

import argparse
import csv
import datetime as dt
import getpass
import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

SYS_CPU = "/sys/devices/system/cpu"
VERSION = "artemisia_snapshot.py v3"

# --------------------------------------------------------------------------- helpers


def read_text(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def run(cmd, timeout=120, cwd=None):
    """Run a command and return its stdout ('' if it could not run)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def parse_cpulist(s):
    cpus = set()
    for part in (s or "").split(","):
        part = part.strip().split(":")[0]
        if not part or not part[0].isdigit():
            continue
        if "-" in part:
            a, b = part.split("-")
            cpus.update(range(int(a), int(b) + 1))
        else:
            cpus.add(int(part))
    return cpus


def fmt_cpulist(cpus):
    cpus, out, i = sorted(cpus), [], 0
    while i < len(cpus):
        j = i
        while j + 1 < len(cpus) and cpus[j + 1] == cpus[j] + 1:
            j += 1
        out.append(str(cpus[i]) if i == j else f"{cpus[i]}-{cpus[j]}")
        i = j + 1
    return ",".join(out)


def find_tool(explicit, names, extra_paths=()):
    for c in [explicit] + [shutil.which(n) for n in names] + list(extra_paths):
        if c and os.access(c, os.X_OK):
            return c
    return None


_msr_fds = {}


def rdmsr(cpu, reg):
    """Read one 64-bit MSR on one CPU (needs root + `modprobe msr`); None if unreadable."""
    if cpu not in _msr_fds:
        try:
            _msr_fds[cpu] = os.open(f"/dev/cpu/{cpu}/msr", os.O_RDONLY)
        except OSError:
            _msr_fds[cpu] = None
    fd = _msr_fds[cpu]
    if fd is None:
        return None
    try:
        data = os.pread(fd, 8, reg)
        return struct.unpack("<Q", data)[0] if len(data) == 8 else None
    except OSError:
        return None


class Snapshot:
    """Ordered key -> value store; keys are dotted strings."""

    def __init__(self):
        self.data = {}

    def add(self, key, value):
        if isinstance(value, (list, tuple, set)):
            value = " ".join(map(str, value))
        self.data[key] = "" if value is None else str(value)


# =========================================================================== system / OS settings
# One function per setting; each returns the value (str) or None.


def sys_uefi_version():
    v = read_text("/sys/class/dmi/id/bios_version")
    return f"{v} ({read_text('/sys/class/dmi/id/bios_date')})" if v else None


def sys_product():
    return read_text("/sys/class/dmi/id/product_name")


def sys_cpu_model():
    m = re.search(r"^model name\s*:\s*(.*)$", read_text("/proc/cpuinfo", ""), re.M)
    return m.group(1) if m else None


def sys_kernel_release():
    return os.uname().release


def sys_kernel_cmdline():
    return read_text("/proc/cmdline")


def sys_cpus_online():
    return read_text(f"{SYS_CPU}/online")


def sys_cpus_offline():
    return read_text(f"{SYS_CPU}/offline")


def sys_isolated():
    return read_text(f"{SYS_CPU}/isolated")


def sys_nohz_full():
    return read_text(f"{SYS_CPU}/nohz_full")


def sys_smt_control():
    return read_text(f"{SYS_CPU}/smt/control")


def sys_smt_active():
    return read_text(f"{SYS_CPU}/smt/active")


def sys_numa_nodes():
    nodes = sorted(glob.glob("/sys/devices/system/node/node[0-9]*"), key=lambda p: int(p.rsplit("node", 1)[1]))
    return " ".join(f"{os.path.basename(n)}:{read_text(n + '/cpulist') or '-'}" for n in nodes) or None


def sys_cpufreq_boost():
    return read_text(f"{SYS_CPU}/cpufreq/boost")


def sys_intel_pstate_status():
    return read_text(f"{SYS_CPU}/intel_pstate/status")


def sys_intel_pstate_no_turbo():
    return read_text(f"{SYS_CPU}/intel_pstate/no_turbo")


def sys_intel_pstate_hwp_dynamic_boost():
    return read_text(f"{SYS_CPU}/intel_pstate/hwp_dynamic_boost")


def sys_intel_pstate_min_perf_pct():
    return read_text(f"{SYS_CPU}/intel_pstate/min_perf_pct")


def sys_intel_pstate_max_perf_pct():
    return read_text(f"{SYS_CPU}/intel_pstate/max_perf_pct")


def sys_cpuidle_driver():
    return read_text(f"{SYS_CPU}/cpuidle/current_driver")


def sys_cpuidle_governor():
    return read_text(f"{SYS_CPU}/cpuidle/current_governor") or read_text(f"{SYS_CPU}/cpuidle/current_governor_ro")


def sys_umwait_enable_c02():
    return read_text(f"{SYS_CPU}/umwait_control/enable_c02")


def sys_umwait_max_time():
    return read_text(f"{SYS_CPU}/umwait_control/max_time")


def sys_thp_enabled():
    return read_text("/sys/kernel/mm/transparent_hugepage/enabled")


def sys_thp_defrag():
    return read_text("/sys/kernel/mm/transparent_hugepage/defrag")


def sys_numa_balancing():
    return read_text("/proc/sys/kernel/numa_balancing")


def sys_hugepages():
    pages = sorted(glob.glob("/sys/kernel/mm/hugepages/*/nr_hugepages"))
    return " ".join(f"{p.split('/')[-2].replace('hugepages-', '')}:{read_text(p)}" for p in pages) or None


def sys_tuned_profile():
    m = re.search(r"Current active profile:\s*(.+)", run(["tuned-adm", "active"]))
    return m.group(1).strip() if m else None


def sys_irqbalance():
    return run(["systemctl", "is-active", "irqbalance"]).strip() or None


def sys_dimm_speed():
    speeds = re.findall(r"Configured Memory Speed:\s*(\d+ MT/s)", run(["dmidecode", "-t", "17"]))
    if not speeds:
        return None
    return " ".join(f"{speeds.count(s)}x{s.replace(' ', '')}" for s in sorted(set(speeds)))


SYSTEM = [
    ("uefi_version", sys_uefi_version), ("product", sys_product), ("cpu_model", sys_cpu_model),
    ("kernel_release", sys_kernel_release), ("kernel_cmdline", sys_kernel_cmdline),
    ("cpus_online", sys_cpus_online), ("cpus_offline", sys_cpus_offline),
    ("isolated", sys_isolated), ("nohz_full", sys_nohz_full),
    ("smt_control", sys_smt_control), ("smt_active", sys_smt_active), ("numa_nodes", sys_numa_nodes),
    ("cpufreq_boost", sys_cpufreq_boost), ("intel_pstate_status", sys_intel_pstate_status),
    ("intel_pstate_no_turbo", sys_intel_pstate_no_turbo),
    ("intel_pstate_hwp_dynamic_boost", sys_intel_pstate_hwp_dynamic_boost),
    ("intel_pstate_min_perf_pct", sys_intel_pstate_min_perf_pct),
    ("intel_pstate_max_perf_pct", sys_intel_pstate_max_perf_pct),
    ("cpuidle_driver", sys_cpuidle_driver), ("cpuidle_governor", sys_cpuidle_governor),
    ("umwait_enable_c02", sys_umwait_enable_c02), ("umwait_max_time", sys_umwait_max_time),
    ("thp_enabled", sys_thp_enabled), ("thp_defrag", sys_thp_defrag), ("numa_balancing", sys_numa_balancing),
    ("hugepages", sys_hugepages), ("tuned_profile", sys_tuned_profile), ("irqbalance", sys_irqbalance),
    ("dimm_configured_speed", sys_dimm_speed),
]


def collect_system(snap):
    for key, fn in SYSTEM:
        try:
            snap.add(f"system.{key}", fn())
        except Exception as e:  # one broken reading must not kill the snapshot
            snap.add(f"system.{key}", f"ERROR {e!r}")


def collect_uncore(snap):
    """Uncore frequency limits per die; adjustable at runtime, so recorded next to the BIOS knob."""
    for d in sorted(glob.glob(f"{SYS_CPU}/intel_uncore_frequency/*")):
        if not os.path.isdir(d):
            continue
        for k in ("initial_min_freq_khz", "initial_max_freq_khz", "min_freq_khz", "max_freq_khz", "current_freq_khz"):
            v = read_text(f"{d}/{k}")
            if v is not None:
                snap.add(f"uncore.{os.path.basename(d)}.{k}", v)


# =========================================================================== conda environment


def _proc_environ(pid):
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            raw = f.read().decode(errors="replace")
    except OSError:
        return {}
    return dict(x.split("=", 1) for x in raw.split("\0") if "=" in x)


def _parent_pid(pid):
    stat = read_text(f"/proc/{pid}/stat", "")
    try:
        return int(stat.rsplit(")", 1)[1].split()[1])
    except (IndexError, ValueError):
        return 0


def find_conda_env():
    """Find CONDA_PREFIX in this process or its ancestors (sudo strips it from our own environment)."""
    pid = os.getpid()
    for _ in range(12):
        env = dict(os.environ) if pid == os.getpid() else _proc_environ(pid)
        if env.get("CONDA_PREFIX"):
            where = "this process" if pid == os.getpid() else f"parent process {pid} ({read_text(f'/proc/{pid}/comm')})"
            return env, where
        pid = _parent_pid(pid)
        if pid <= 1:
            break
    return {}, None


def collect_conda(snap):
    env, where = find_conda_env()
    snap.add("conda.script_python", f"{sys.executable} ({sys.version.split()[0]})")
    if not env:
        snap.add("conda.env_name", "none (no CONDA_PREFIX in this process or its parents)")
        return
    prefix = env["CONDA_PREFIX"]
    snap.add("conda.env_name", env.get("CONDA_DEFAULT_ENV") or os.path.basename(prefix))
    snap.add("conda.env_prefix", prefix)
    snap.add("conda.detected_in", where)
    snap.add("conda.env_python", run([os.path.join(prefix, "bin", "python"), "-V"]).strip() or None)
    snap.add("conda.conda_version", run([env.get("CONDA_EXE", "conda"), "--version"]).strip() or None)
    for meta in sorted(glob.glob(os.path.join(prefix, "conda-meta", "*.json"))):
        try:
            with open(meta) as f:
                p = json.load(f)
            snap.add(f"conda.pkg.{p['name']}", f"{p.get('version')} {p.get('build', '')} {p.get('channel', '')}".strip())
        except (OSError, ValueError, KeyError):
            pass
    # packages pip installed into the env (conda-meta does not list these)
    for installer in sorted(glob.glob(os.path.join(prefix, "lib", "python*", "site-packages", "*.dist-info", "INSTALLER"))):
        if read_text(installer) == "pip":
            name_ver = os.path.basename(os.path.dirname(installer))[: -len(".dist-info")]
            name, _, ver = name_ver.rpartition("-")
            snap.add(f"conda.pip.{name}", ver)


# =========================================================================== UEFI via OneCLI

ONECLI_LINE = re.compile(r"^([A-Za-z0-9_]+)\.([^=]+?)=(.*)$")


def collect_onecli(snap, exe):
    if not exe:
        return "not found"
    if os.geteuid() != 0:
        return "skipped (needs root)"
    print(f"Reading UEFI settings with {exe} (takes about a minute)...", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:  # OneCLI drops a logs/ folder into its working directory
        out = run([exe, "config", "show"], timeout=900, cwd=tmp)
    n = 0
    for line in out.splitlines():
        m = ONECLI_LINE.match(line.strip())
        if m:
            snap.add(f"uefi.{m.group(1)}.{m.group(2).strip()}", m.group(3).strip())
            n += 1
    return f"ok ({n} settings)" if n else "FAILED (nothing parsed; try `sudo onecli config show` by hand)"


# =========================================================================== per-CPU via cpupower

UNIT_KHZ = {"hz": 1e-3, "khz": 1, "mhz": 1e3, "ghz": 1e6}


def to_khz(s):
    m = re.search(r"([\d.]+)\s*([kMG]?Hz)", s or "", re.I)
    return str(int(round(float(m.group(1)) * UNIT_KHZ[m.group(2).lower()]))) if m else None


def split_cpu_blocks(text):
    parts = re.split(r"analyzing CPU (\d+):", text)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def parse_frequency_info(block):
    d = {}
    if m := re.search(r"^\s*driver:\s*(\S+)", block, re.M):
        d["driver"] = m.group(1)
    if m := re.search(r"hardware limits:\s*(.+?)\s+-\s+(.+)", block):
        d["hw_min_khz"], d["hw_max_khz"] = to_khz(m.group(1)), to_khz(m.group(2))
    if m := re.search(r"available cpufreq governors:\s*(.+)", block):
        d["governors"] = m.group(1).strip()
    if m := re.search(r"frequency should be within\s+(.+?)\s+and\s+(.+?)\.\s", block, re.S):
        d["policy_min_khz"], d["policy_max_khz"] = to_khz(m.group(1)), to_khz(m.group(2))
    if m := re.search(r'governor "([^"]+)"', block):
        d["governor"] = m.group(1)
    if m := re.search(r"current CPU frequency:\s*(.+?)\s*\(asserted by call to kernel\)", block):
        d["cur_khz"] = to_khz(m.group(1))
    if m := re.search(r"Supported:\s*(\w+)", block):
        d["boost_supported"] = m.group(1)
    if m := re.search(r"Active:\s*(\w+)", block):
        d["boost_active"] = m.group(1)
    if m := re.search(r"energy performance preference:\s*(\S+)", block, re.I):
        d["epp"] = m.group(1)
    return d


def parse_idle_info(block):
    d = {}
    if m := re.search(r"Available idle states:\s*(.+)", block):
        d["idle_states"] = m.group(1).strip()
        d["idle_disabled"] = " ".join(re.findall(r"^(\S+) \(DISABLED\)\s*:", block, re.M)) or "none"
    return d


def run_cpupower(exe):
    """{cpu: {field: value}} from the three cpupower queries."""
    per_cpu = {}
    if not exe:
        return per_cpu
    freq = run([exe, "-c", "all", "frequency-info", "-n"])
    if "analyzing CPU" not in freq:  # older cpupower without --no-rounding
        freq = run([exe, "-c", "all", "frequency-info"])
    for c, b in split_cpu_blocks(freq).items():
        per_cpu.setdefault(c, {}).update(parse_frequency_info(b))
    for c, b in split_cpu_blocks(run([exe, "-c", "all", "idle-info"])).items():
        per_cpu.setdefault(c, {}).update(parse_idle_info(b))
    for c, b in split_cpu_blocks(run([exe, "-c", "all", "info", "-b"])).items():
        if m := re.search(r"perf-bias:\s*(\d+)", b):
            per_cpu.setdefault(c, {})["perf_bias"] = m.group(1)
    return per_cpu


class Ctx:
    def __init__(self, cpupower_data):
        self.cp = cpupower_data
        self.from_sysfs = set()  # per-CPU fields where cpupower printed nothing and sysfs was used
        self.isolated = parse_cpulist(read_text(f"{SYS_CPU}/isolated", ""))
        self.nohz = parse_cpulist(read_text(f"{SYS_CPU}/nohz_full", ""))
        self.node = {}
        for n in glob.glob("/sys/devices/system/node/node[0-9]*"):
            for c in parse_cpulist(read_text(f"{n}/cpulist", "")):
                self.node[c] = n.rsplit("node", 1)[1]


def _cpufreq(c, name):
    return read_text(f"{SYS_CPU}/cpu{c}/cpufreq/{name}")


def _pick(ctx, c, cp_key, sysfs_name=None):
    """cpupower's value if it printed one, else the sysfs file cpupower itself reads."""
    v = ctx.cp.get(c, {}).get(cp_key) if cp_key else None
    if v not in (None, ""):
        return v
    v = _cpufreq(c, sysfs_name) if sysfs_name else None
    if v is not None and cp_key:
        ctx.from_sysfs.add(cp_key)
    return v


# ---- per-CPU settings: one function each


def core_package(ctx, c):
    return read_text(f"{SYS_CPU}/cpu{c}/topology/physical_package_id")


def core_core_id(ctx, c):
    return read_text(f"{SYS_CPU}/cpu{c}/topology/core_id")


def core_numa_node(ctx, c):
    return ctx.node.get(c)


def core_smt_siblings(ctx, c):
    return read_text(f"{SYS_CPU}/cpu{c}/topology/thread_siblings_list")


def core_isolated(ctx, c):
    return c in ctx.isolated


def core_nohz_full(ctx, c):
    return c in ctx.nohz


def core_driver(ctx, c):
    return _pick(ctx, c, "driver", "scaling_driver")


def core_governor(ctx, c):
    return _pick(ctx, c, "governor", "scaling_governor")


def core_available_governors(ctx, c):
    return _pick(ctx, c, "governors", "scaling_available_governors")


def core_policy_min_khz(ctx, c):
    return _pick(ctx, c, "policy_min_khz", "scaling_min_freq")


def core_policy_max_khz(ctx, c):
    return _pick(ctx, c, "policy_max_khz", "scaling_max_freq")


def core_hw_min_khz(ctx, c):
    return _pick(ctx, c, "hw_min_khz", "cpuinfo_min_freq")


def core_hw_max_khz(ctx, c):
    return _pick(ctx, c, "hw_max_khz", "cpuinfo_max_freq")


def core_base_khz(ctx, c):
    return _pick(ctx, c, None, "base_frequency")


def core_cur_khz(ctx, c):
    return _pick(ctx, c, "cur_khz", "scaling_cur_freq")


def core_fixed_frequency(ctx, c):
    if core_governor(ctx, c) == "userspace":
        return f"{_cpufreq(c, 'scaling_setspeed')} kHz (userspace setspeed)"
    mn, mx = core_policy_min_khz(ctx, c), core_policy_max_khz(ctx, c)
    return f"{mn} kHz (policy min == max)" if mn and mn == mx else "no"


def core_boost_supported(ctx, c):
    return _pick(ctx, c, "boost_supported")


def core_boost_active(ctx, c):
    return _pick(ctx, c, "boost_active")


def core_turbo_allowed(ctx, c):
    if read_text(f"{SYS_CPU}/intel_pstate/no_turbo") == "1":
        return "no (intel_pstate/no_turbo=1)"
    if read_text(f"{SYS_CPU}/cpufreq/boost") == "0":
        return "no (cpufreq/boost=0)"
    active = core_boost_active(ctx, c)
    if active and active.lower() == "no":
        return "no (cpupower: boost not active)"
    mx, base = core_policy_max_khz(ctx, c), core_base_khz(ctx, c)
    if mx and base and int(mx) <= int(base):
        return "no (policy max <= base frequency)"
    return "yes"


def core_epp(ctx, c):
    return _pick(ctx, c, "epp", "energy_performance_preference")


def core_perf_bias(ctx, c):
    v = ctx.cp.get(c, {}).get("perf_bias")
    return v if v is not None else read_text(f"{SYS_CPU}/cpu{c}/power/energy_perf_bias")


def _sysfs_idle(c):
    states = sorted(glob.glob(f"{SYS_CPU}/cpu{c}/cpuidle/state[0-9]*"), key=lambda p: int(p.rsplit("state", 1)[1]))
    return [(read_text(f"{s}/name"), read_text(f"{s}/disable")) for s in states]


def core_idle_states(ctx, c):
    v = ctx.cp.get(c, {}).get("idle_states")
    if v:
        return v
    st = _sysfs_idle(c)
    return " ".join(n or "?" for n, _ in st) if st else None


def core_idle_states_disabled(ctx, c):
    v = ctx.cp.get(c, {}).get("idle_disabled")
    if v:
        return v
    st = _sysfs_idle(c)
    return (" ".join(n or "?" for n, d in st if d == "1") or "none") if st else None


def _prefetch_bit(c, n):
    v = rdmsr(c, 0x1A4)
    return None if v is None else ("Disabled" if (v >> n) & 1 else "Enabled")


def core_l2_hw_prefetcher(ctx, c):
    return _prefetch_bit(c, 0)


def core_l2_adjacent_prefetcher(ctx, c):
    return _prefetch_bit(c, 1)


def core_dcu_streamer_prefetcher(ctx, c):
    return _prefetch_bit(c, 2)


def core_dcu_ip_prefetcher(ctx, c):
    return _prefetch_bit(c, 3)


def core_msr_0x1a4(ctx, c):
    v = rdmsr(c, 0x1A4)
    return hex(v) if v is not None else None


def core_msr_0xe1_umwait(ctx, c):
    v = rdmsr(c, 0xE1)
    return hex(v) if v is not None else None


CORE = [
    ("package", core_package), ("core_id", core_core_id), ("numa_node", core_numa_node),
    ("smt_siblings", core_smt_siblings), ("isolated", core_isolated), ("nohz_full", core_nohz_full),
    ("driver", core_driver), ("governor", core_governor), ("available_governors", core_available_governors),
    ("policy_min_khz", core_policy_min_khz), ("policy_max_khz", core_policy_max_khz),
    ("hw_min_khz", core_hw_min_khz), ("hw_max_khz", core_hw_max_khz), ("base_khz", core_base_khz),
    ("cur_khz", core_cur_khz), ("fixed_frequency", core_fixed_frequency),
    ("boost_supported", core_boost_supported), ("boost_active", core_boost_active),
    ("turbo_allowed", core_turbo_allowed), ("epp", core_epp), ("perf_bias", core_perf_bias),
    ("idle_states", core_idle_states), ("idle_states_disabled", core_idle_states_disabled),
    ("l2_hw_prefetcher", core_l2_hw_prefetcher), ("l2_adjacent_prefetcher", core_l2_adjacent_prefetcher),
    ("dcu_streamer_prefetcher", core_dcu_streamer_prefetcher), ("dcu_ip_prefetcher", core_dcu_ip_prefetcher),
    ("msr_0x1a4", core_msr_0x1a4), ("msr_0xe1_umwait", core_msr_0xe1_umwait),
]
SUMMARY_KEYS = ["governor", "policy_min_khz", "policy_max_khz", "fixed_frequency", "turbo_allowed", "epp",
                "idle_states_disabled", "l2_hw_prefetcher", "l2_adjacent_prefetcher", "dcu_streamer_prefetcher",
                "dcu_ip_prefetcher", "msr_0xe1_umwait"]


def collect_cpus(snap, ctx):
    online = parse_cpulist(read_text(f"{SYS_CPU}/online", "")) or set(range(os.cpu_count() or 1))
    possible = parse_cpulist(read_text(f"{SYS_CPU}/possible", "")) or online
    for c in sorted(possible):
        snap.add(f"cpu.cpu{c}.online", c in online)
        if c not in online:
            continue
        for key, fn in CORE:
            try:
                snap.add(f"cpu.cpu{c}.{key}", fn(ctx, c))
            except Exception as e:
                snap.add(f"cpu.cpu{c}.{key}", f"ERROR {e!r}")


# =========================================================================== reporting


def cpu_key(key):
    """'cpu.cpu12.governor' -> (12, 'governor'), else None."""
    m = re.match(r"cpu\.cpu(\d+)\.(.+)$", key)
    return (int(m.group(1)), m.group(2)) if m else None


def print_cpu_summary(snap):
    print("\n=== Per-CPU settings (value: cpus) ===")
    groups = {}
    for k, v in snap.data.items():
        ck = cpu_key(k)
        if ck and ck[1] in SUMMARY_KEYS:
            groups.setdefault(ck[1], {}).setdefault(v or "unreadable", []).append(ck[0])
    for field in SUMMARY_KEYS:
        if field in groups:
            print(f"  {field:24} " + " | ".join(f"{v}: {fmt_cpulist(c)}" for v, c in sorted(groups[field].items())))


# =========================================================================== main


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-u", "--user", help="scientist name (default: $SUDO_USER)")
    ap.add_argument("-o", "--outfile", default="./snapshot.csv")
    ap.add_argument("--onecli", help="path to Lenovo OneCLI (default: search PATH and /opt/lenovo)")
    ap.add_argument("--no-onecli", action="store_true", help="skip the UEFI query")
    ap.add_argument("--cpupower", help="path to cpupower (default: search PATH)")
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("WARNING: not root - OneCLI, MSRs and dmidecode will be skipped.", file=sys.stderr)
    else:
        run(["modprobe", "msr"])
        run(["modprobe", "intel_uncore_frequency"])

    now = dt.datetime.now().astimezone()
    snap = Snapshot()
    snap.add("meta.date", now.strftime("%m/%d/%Y %I:%M %p"))
    snap.add("meta.timestamp", now.isoformat())
    snap.add("meta.scientist", args.user or os.environ.get("SUDO_USER") or getpass.getuser())
    snap.add("meta.host", os.uname().nodename)
    snap.add("meta.script", VERSION)
    for key in ("meta.onecli", "meta.cpupower", "meta.cpu_fields_from_sysfs"):
        snap.add(key, "")  # filled in below; keeps meta.* at the top of the file

    collect_system(snap)
    collect_conda(snap)

    onecli = None if args.no_onecli else find_tool(
        args.onecli, ["onecli", "OneCli"], ["/opt/lenovo/onecli/onecli", "/opt/lenovo/toolscenter/onecli/onecli"])
    snap.add("meta.onecli", "disabled (--no-onecli)" if args.no_onecli else collect_onecli(snap, onecli))
    collect_uncore(snap)

    cpupower = find_tool(args.cpupower, ["cpupower"])
    cp_data = run_cpupower(cpupower)
    snap.add("meta.cpupower", (f"ok ({len(cp_data)} cpus)" if cp_data else "FAILED (no output; sysfs used)")
             if cpupower else "not found (sysfs used)")
    ctx = Ctx(cp_data)
    collect_cpus(snap, ctx)
    snap.add("meta.cpu_fields_from_sysfs", sorted(ctx.from_sysfs) or "none")

    # os.makedirs(args.outdir, exist_ok=True)
    path = args.outfile
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "value"])
        w.writerows(snap.data.items())

    print(f"OneCLI:   {snap.data['meta.onecli']}\ncpupower: {snap.data['meta.cpupower']}\n"
          f"conda:    {snap.data.get('conda.env_name')}")
    print_cpu_summary(snap)
    print(f"\nWrote {path} ({len(snap.data)} keys)")


if __name__ == "__main__":
    main()
