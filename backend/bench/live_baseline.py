#!/usr/bin/env python3
# bench/live_baseline.py
#
# Measure one real run of every configured report: `main.py --all --dry-run`
# with timers around the network and the PDF renderer. Nothing is uploaded.
#
#   cd backend && python -m bench.live_baseline --output-dir ../out/baseline
#
# Prints a JSON summary with counts and timings only — no names or contact
# details — for docs/benchmarks.md. The PDFs (real people) land in --output-dir,
# which must stay out of git; the engine's own log goes to run.log beside them.

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import resource
import statistics
import subprocess
import time

from pypdf import PdfReader

from planning_center_reports import legacy, services


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "describe", "--always", "--dirty"], capture_output=True,
                             text=True, check=True, cwd=os.path.dirname(__file__))
        return out.stdout.strip()
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--output-dir", default="../out/baseline")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    render = {"roster": [], "volunteers": [], "instructions": []}
    rosters: list[dict] = []

    def timed(kind, fn):
        def wrapper(*a, **k):
            start = time.perf_counter()
            path = fn(*a, **k)
            seconds = time.perf_counter() - start
            pages = len(PdfReader(path).pages)
            render[kind].append((seconds, pages))
            if kind == "roster":
                r = a[0]
                rosters.append({"active": len(r.active), "inactive": len(r.inactive),
                                "workers": len(r.workers), "pages": pages,
                                "render_ms": round(seconds * 1000, 1)})
            return path
        return wrapper

    services.generate_roster_pdf = timed("roster", services.generate_roster_pdf)
    services.generate_volunteer_pdf = timed("volunteers", services.generate_volunteer_pdf)
    services.build_instructions_pdf = timed("instructions", services.build_instructions_pdf)

    log_path = os.path.join(args.output_dir, "run.log")
    started = time.perf_counter()
    with open(log_path, "w", encoding="utf-8") as log, contextlib.redirect_stdout(log), \
            legacy.run_context(dry_run=True, output_dir=args.output_dir) as ctx:
        ok = services.run_all(ctx)
    total = time.perf_counter() - started

    stats = ctx.pco.stats
    render_s = sum(s for runs in render.values() for s, _ in runs)
    files = [os.path.join(d, f) for d, _, fs in os.walk(args.output_dir) for f in fs if f.endswith(".pdf")]

    def describe(runs):
        if not runs:
            return {"count": 0}
        seconds = [s for s, _ in runs]
        pages = sum(p for _, p in runs)
        return {"count": len(runs), "pages": pages,
                "total_ms": round(sum(seconds) * 1000, 1),
                "median_ms": round(statistics.median(seconds) * 1000, 1),
                "max_ms": round(max(seconds) * 1000, 1),
                "ms_per_page": round(sum(seconds) * 1000 / pages, 2) if pages else None}

    def spread(key):
        values = sorted(r[key] for r in rosters)
        if not values:
            return {}
        return {"min": values[0], "median": statistics.median(values), "max": values[-1],
                "total": sum(values)}

    summary = {
        "ok": ok,
        "commit": _git_commit(),
        "python": platform.python_version(),
        "machine": f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs",
        "total_s": round(total, 2),
        "pco": stats.as_dict(),
        "render_s": round(render_s, 2),
        "other_s": round(total - stats.http_s - stats.throttle_wait_s - stats.backoff_wait_s - render_s, 2),
        "render": {kind: describe(runs) for kind, runs in render.items()},
        "roster_shape": {"rosters": len(rosters), "active": spread("active"),
                         "inactive": spread("inactive"), "workers": spread("workers"),
                         "pages": spread("pages")},
        "files_written": len(files),
        "bytes_written": sum(os.path.getsize(f) for f in files),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "log": log_path,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
