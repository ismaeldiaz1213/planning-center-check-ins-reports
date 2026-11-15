#!/usr/bin/env python3
# bench/render_bench.py
#
# How fast does the renderer draw PDFs? No network, no Planning Center: every
# roster is built from mock_data, scaled to the size of IBL's real weekly run.
#
#   cd backend && python -m bench.render_bench            # table for docs/benchmarks.md
#   cd backend && python -m bench.render_bench --json     # machine-readable
#   cd backend && python -m bench.render_bench --repeat 30
#
# Two kinds of numbers:
#   • per PDF type — one document rendered --repeat times: median and p95
#   • a whole run  — an IBL-shaped set (51 rosters, 3 volunteer sheets, one
#                    instructions bundle) at 1× and 5× IBL, timed end to end
#
# The IBL shape comes from the live baseline of 2026-11-14 (counts only: 51
# rosters, 1,242 active / 419 inactive / 148 workers, 136 roster pages). The
# three lists below reproduce those totals and the measured min/median/max.
# The same input shapes are what a Rust/Typst renderer must be timed against.

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import resource
import statistics
import subprocess
import tempfile
import time

import pypdf
import reportlab
from pypdf import PdfReader

from planning_center_reports import legacy
from planning_center_reports.mock_data import mock_roster, mock_volunteers
from planning_center_reports.pdf.instructions import build_instructions_pdf
from planning_center_reports.pdf.rosters import generate_roster_pdf
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf
from planning_center_reports.roster_data import LocationRoster, VolunteerReport

IBL_ACTIVE = [0, 1, 2, 2, 3, 4, 5, 6, 6, 7, 8, 9, 10, 10, 11, 12, 13, 14, 14, 15, 16, 17, 18, 18, 19, 20,
              20, 20, 20, 20, 21, 21, 22, 23, 24, 25, 26, 28, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 74,
              81, 89]
IBL_INACTIVE = [0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6,
                6, 7, 7, 7, 8, 8, 9, 10, 10, 11, 13, 14, 15, 17, 18, 20, 22, 24, 27, 29, 32]
IBL_WORKERS = [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
               2, 2, 2, 2, 2, 2, 3, 3, 3, 4, 4, 5, 5, 6, 7, 7, 9, 10, 11, 12, 14]
IBL_VOLUNTEER_ROWS = [60, 50, 0]   # Rutas, Escuela Dominical, "C" (nobody tagged yet)

CTX = legacy.render_context()      # IBL's words, branding and default colours


def _cycle(members: list, count: int) -> list:
    """`count` members, repeating the mock ones (copies, so rows stay independent)."""
    return [dataclasses.replace(members[i % len(members)]) for i in range(count)] if members else []


def scaled_roster(name: str, active: int, inactive: int, workers: int) -> LocationRoster:
    base = mock_roster(name)
    pool = base.active + base.inactive
    roster = dataclasses.replace(base)
    roster.active = _cycle(base.active, active)
    roster.inactive = _cycle(base.inactive or pool, inactive)
    roster.workers = _cycle(base.workers or pool, workers)
    return roster


def scaled_volunteers(rows: int) -> VolunteerReport:
    base = mock_volunteers()
    if rows == 0:
        return VolunteerReport(base.title, base.periods, [])
    out = [dataclasses.replace(base.rows[i % len(base.rows)], person_id=str(i)) for i in range(rows)]
    out.sort(key=lambda r: r.group)
    return VolunteerReport(base.title, base.periods, out)


def _pages(path: str) -> int:
    return len(PdfReader(path).pages)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


def time_one(label: str, render, repeat: int, workdir: str) -> dict:
    path = os.path.join(workdir, "one.pdf")
    render(path)                      # warm-up: fonts, images and imports load once
    pages = _pages(path)
    seconds = []
    for _ in range(repeat):
        start = time.perf_counter()
        render(path)
        seconds.append(time.perf_counter() - start)
    median = statistics.median(seconds)
    return {"pdf": label, "pages": pages, "repeat": repeat,
            "median_ms": round(median * 1000, 2), "p95_ms": round(_percentile(seconds, 95) * 1000, 2),
            "ms_per_page": round(median * 1000 / pages, 2),
            "bytes": os.path.getsize(path)}


def time_run(scale: int, repeat: int, workdir: str) -> dict:
    """Render a whole IBL-shaped run `scale` times over (scale × the rosters)."""
    rosters = [scaled_roster(f"Clase {i}", a, n, w)
               for _ in range(scale)
               for i, (a, n, w) in enumerate(zip(IBL_ACTIVE, IBL_INACTIVE, IBL_WORKERS, strict=True))]
    volunteers = [scaled_volunteers(rows) for _ in range(scale) for rows in IBL_VOLUNTEER_ROWS]
    seconds, pages = [], 0
    for _ in range(repeat):
        pages = 0
        start = time.perf_counter()
        for i, roster in enumerate(rosters):
            path = os.path.join(workdir, f"r{i}.pdf")
            generate_roster_pdf(roster, "Escuela Dominical", path, CTX, show_route=True,
                                attendance_summary=True)
        for i, report in enumerate(volunteers):
            generate_volunteer_pdf(report, "Escuela Dominical", os.path.join(workdir, f"v{i}.pdf"), CTX)
        build_instructions_pdf(os.path.join(workdir, "i.pdf"), CTX)
        seconds.append(time.perf_counter() - start)
    for name in os.listdir(workdir):
        if name.endswith(".pdf") and name != "one.pdf":
            pages += _pages(os.path.join(workdir, name))
    median = statistics.median(seconds)
    return {"scale": f"{scale}× IBL", "rosters": len(rosters), "volunteer_sheets": len(volunteers),
            "people_rows": sum(len(r.active) + len(r.inactive) + len(r.workers) for r in rosters),
            "pages": pages, "repeat": repeat,
            "median_s": round(median, 3), "p95_s": round(_percentile(seconds, 95), 3),
            "ms_per_page": round(median * 1000 / pages, 2),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}


def _commit() -> str:
    try:
        return subprocess.run(["git", "describe", "--always", "--dirty"], capture_output=True, text=True,
                              check=True, cwd=os.path.dirname(__file__)).stdout.strip()
    except Exception:
        return "unknown"


def _cpu() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown CPU"


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark PDF rendering on mock data.")
    parser.add_argument("--repeat", type=int, default=20, help="repeats per single PDF (default 20)")
    parser.add_argument("--run-repeat", type=int, default=5, help="repeats per whole run (default 5)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown tables")
    args = parser.parse_args()

    typical = scaled_roster("Clase Primaria", 20, 6, 2)
    largest = scaled_roster("Clase Grande", 89, 32, 14)
    singles = [
        ("Roster, as in mock data (11 active, 2 inactive, 1 worker)",
         lambda p: generate_roster_pdf(mock_roster("Clase Primaria"), "Escuela Dominical", p, CTX,
                                       show_route=True, attendance_summary=True)),
        ("Roster, IBL median (20 active, 6 inactive, 2 workers)",
         lambda p: generate_roster_pdf(typical, "Escuela Dominical", p, CTX, show_route=True,
                                       attendance_summary=True)),
        ("Roster, IBL largest (89 active, 32 inactive, 14 workers)",
         lambda p: generate_roster_pdf(largest, "Escuela Dominical", p, CTX, show_route=True,
                                       attendance_summary=True)),
        ("Roster without Ruta column or summary (20 / 6 / 2)",
         lambda p: generate_roster_pdf(typical, "Ministerio de Autobuses", p, CTX)),
        ("Volunteer sheet (60 volunteers)",
         lambda p: generate_volunteer_pdf(scaled_volunteers(60), "Rutas", p, CTX)),
        ("Instructions bundle (cover + two guides)", lambda p: build_instructions_pdf(p, CTX)),
    ]

    with tempfile.TemporaryDirectory(prefix="render-bench-") as workdir:
        result = {
            "commit": _commit(),
            "machine": f"{_cpu()}, {os.cpu_count()} logical CPUs, {platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "libraries": f"reportlab {reportlab.Version}, pypdf {pypdf.__version__}",
            "single": [time_one(label, fn, args.repeat, workdir) for label, fn in singles],
            "runs": [time_run(scale, args.run_repeat, workdir) for scale in (1, 5)],
        }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(f"commit {result['commit']} · Python {result['python']} · {result['libraries']}")
    print(f"machine: {result['machine']}\n")
    print("| PDF | Pages | Median | p95 | Per page | File size |")
    print("|---|---:|---:|---:|---:|---:|")
    for r in result["single"]:
        print(f"| {r['pdf']} | {r['pages']} | {r['median_ms']} ms | {r['p95_ms']} ms | "
              f"{r['ms_per_page']} ms | {r['bytes'] / 1024:.0f} KB |")
    print("\n| Whole run | Rosters | People rows | Pages | Median | p95 | Per page | Peak memory |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in result["runs"]:
        print(f"| {r['scale']} | {r['rosters']} | {r['people_rows']:,} | {r['pages']} | {r['median_s']} s | "
              f"{r['p95_s']} s | {r['ms_per_page']} ms | {r['peak_rss_mb']} MB |")


if __name__ == "__main__":
    main()
