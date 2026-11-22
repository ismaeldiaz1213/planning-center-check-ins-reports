# Benchmarks

Measured numbers for the engine, recorded as the platform work proceeds
(`docs/advanced-reports-plan.md` §5). Every entry says when, on what commit and machine,
and how it was measured, so it can be repeated. Nothing here is an estimate unless it is
labelled as one.

## Summary so far

| Question | Answer (baseline, 2026-11-14) |
|---|---|
| How long does IBL's weekly run take? | **57.7 s** on a laptop, all three reports, no upload |
| Where does the time go? | **94% waiting for Planning Center responses**, 5% drawing PDFs, 1% everything else |
| How many Planning Center requests? | **134**, no retries, no 429s |
| How long were we paused by the rate limit? | **0 s.** The run never came near 80 requests in 20 s |
| How fast is the renderer? | About **15–19 ms per page**; a whole IBL-sized set (156 pages) in **2.3 s** |
| Peak memory | 141 MB for the live run, 95 MB for rendering alone |

Still missing: durations of the real `roster-weekly` executions on Cloud Run, container
image size, and cold start. See [Not measured yet](#not-measured-yet).

> **Caveat: the laptop's power state was not recorded.** Later the same day the machine
> went onto battery in power-save mode (CPU capped at 2.0 GHz) and every CPU-bound number
> here ran about 2.5× slower (the IBL-sized render set took 5.8 s instead of 2.3 s). The
> figures in sections 1 and 2 were taken in a faster state that was not written down, most
> likely plugged in. Compare numbers only when they were taken in the same power state,
> and record it next time (`cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor`
> and whether the machine is on mains). Network time (94% of the live run) is not affected.

---

## 1. Live run against Planning Center (local baseline)

- **Date:** 2026-11-14 (Saturday), one run.
- **Commit:** `668ce43` (v0.2.0) plus the request counter added on `feat/platform-m1`.
- **Machine:** AMD Ryzen AI 7 PRO 350, 16 logical CPUs, Fedora Linux, home internet.
  Python 3.11.18, reportlab 5.1.0, pypdf 7.1.0.
- **Method:** `cd backend && python -m bench.live_baseline --output-dir ../out/baseline-2026-11-14`.
  This is `main.py --all --dry-run` (IBL's `reports.yaml`: `rutas`, `escuela`, `escuela-c`)
  with timers around `requests.get` and around each PDF function. Nothing was uploaded.
  The request numbers come from the counter in `pco_client.py` (`PcoClient.stats`; at the
  time of this run a module-level `pco_client.stats`), which counts every attempt that
  reaches the network.

| Stage | Time | Share |
|---|---:|---:|
| Waiting for Planning Center responses | 54.16 s | 93.8% |
| Paused for our own rate pacing (80 requests / 20 s) | 0.00 s | 0% |
| Paused after 429s or network errors | 0.00 s | 0% |
| Drawing PDFs | 2.82 s | 4.9% |
| Everything else (roster building, copying files) | 0.74 s | 1.3% |
| **Total** | **57.72 s** | |

| Planning Center traffic | |
|---|---:|
| Requests | 134 |
| Network retries | 0 |
| 429 (rate-limited) responses | 0 |
| Average time per request | 0.40 s |

| Output | Count | Pages | Render time | Per page |
|---|---:|---:|---:|---:|
| `Roster.pdf` | 51 | 136 | 2,537 ms (median 43 ms, slowest 178 ms) | 18.7 ms |
| `Voluntarios.pdf` | 3 | 9 | 160 ms | 17.8 ms |
| `Instrucciones.pdf` (built once, copied to 51 folders) | 1 | 14 | 120 ms | 8.6 ms |

Size of the run: 51 rosters holding 1,242 active people, 419 inactive and 148 workers
(per roster: median 20 active, largest 89). 105 files written, 78.7 MB, of which about
75 MB is 51 identical copies of the 1.5 MB instructions bundle. Peak memory 141 MB.

### What this says

1. **The run is network-bound, and not because of the rate limit.** The plan (§1) says
   the job's time is "dominated by Planning Center's rate limit". For IBL that is not what
   happens: 134 requests spread over 54 seconds is about 2.5 requests per second, well
   under the limit, and the pacing code never paused once. The time goes to making 134
   round trips one after another, each taking about 0.4 s.
2. **Fewer requests is the only large win available.** Rendering is 2.8 s of 57.7 s. A
   renderer that was infinitely fast would shorten today's run by 5%.
3. **This is one run on one network.** Request latency will differ on Cloud Run (a data
   centre is usually closer to Planning Center than a home connection, so the network
   share may shrink), and rendering will be slower on a 1-vCPU container than on this
   laptop. The production numbers below are needed before quoting any of this publicly.

---

## 2. Renderer alone (render baseline)

- **Date:** 2026-11-14. **Commit:** as above. **Machine:** as above.
- **Method:** `cd backend && python -m bench.render_bench`. No network. Rosters are built
  from `mock_data` and scaled to IBL's real shape from section 1 (51 rosters with the same
  totals and the same smallest/median/largest sizes). Single PDFs: one warm-up render, then
  20 timed renders. Whole runs: 5 timed repeats. Times include writing the file to a
  temporary directory.

| PDF | Pages | Median | p95 | Per page | File size |
|---|---:|---:|---:|---:|---:|
| Roster, as in mock data (11 active, 2 inactive, 1 worker) | 2 | 34.33 ms | 57.21 ms | 17.16 ms | 22 KB |
| Roster, IBL median (20 active, 6 inactive, 2 workers) | 2 | 38.75 ms | 39.55 ms | 19.38 ms | 27 KB |
| Roster, IBL largest (89 active, 32 inactive, 14 workers) | 7 | 74.99 ms | 76.30 ms | 10.71 ms | 75 KB |
| Roster without Ruta column or summary (20 / 6 / 2) | 2 | 38.75 ms | 42.44 ms | 19.37 ms | 26 KB |
| Volunteer sheet (60 volunteers) | 3 | 43.76 ms | 44.33 ms | 14.59 ms | 31 KB |
| Instructions bundle (cover + two guides) | 14 | 62.94 ms | 83.00 ms | 4.50 ms | 1,475 KB |

| Whole run | Rosters | People rows | Pages | Median | p95 | Per page | Peak memory |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1× IBL | 51 | 1,804 | 156 | 2.343 s | 2.382 s | 15.02 ms | 95.1 MB |
| 5× IBL | 255 | 9,020 | 724 | 11.532 s | 11.639 s | 15.93 ms | 95.1 MB |

Notes:

- The synthetic 1× run (2.34 s) agrees with the live run's render time (2.82 s for 159
  pages), so the mock shape is a fair stand-in.
- Rendering scales linearly with pages and memory stays flat: 5× the church costs 5× the
  time and no extra memory.
- A two-page roster costs about 35–39 ms however few people are on it, so a large part of
  each PDF is a fixed cost (header, logo, QR code, summary), not rows.
- "5× IBL" here means five times as many rosters of the same sizes. Peak memory is read
  once per process, so the 1× and 5× figures are the same reading.

### For the Rust gate (plan §5.3)

The gate asks for per-page rendering at least 5× faster than reportlab on the same input.
The number to beat is **about 15 ms per page** for a whole run, or **19 ms per page** for
the median roster, on this machine. The inputs to reproduce are the six single-PDF shapes
above; the text each must produce is pinned by the golden tests
(`backend/tests/golden/snapshots/render/`).

What a pass would be worth today: 5× faster rendering saves about 2.3 s of a 57.7 s run.
That changes only if the synced data store (Milestone 2) removes most of the network
time, which is the measurement that has to come first.

### Engine refactor: before and after (2026-11-14)

Milestone 1 step 3 rewrote the engine's plumbing (explicit church settings, text
catalogs, a client object) without changing output. To check it costs nothing, the old
code (`git archive` of `668ce43`) and the refactored working tree were run one after the
other on the same machine in the same power state (battery, power-save):

| | Old engine | Refactored engine |
|---|---:|---:|
| Median roster (20 / 6 / 2), median of 20 renders | 98 ms | 98 ms |

The absolute figure is slower than the table above only because of the power state (see
the caveat at the top). This was one comparison of the renderer; the refactored engine has
not yet been timed against live Planning Center.

---

## 3. Requests against the fake Planning Center (regression number, not a benchmark)

The golden pipeline tests count requests against a small fake church
(`backend/tests/golden/fake_pco.py`): **84 requests** for IBL's three reports, 46 for the
example config. These are not performance figures (the fake returns deliberately small
pages to exercise pagination). They exist so a refactor that starts making extra requests
fails a test.

---

## Not measured yet

| Item | Why not | What is needed |
|---|---|---|
| Real `roster-weekly` execution times on Cloud Run | `gcloud` on the development machine was logged out | The owner re-authenticates; then read-only `gcloud run jobs executions list/describe` and log reads in `ibl-planning-center-check-ins` |
| Request latency from Cloud Run | Same | Comes with the above, from the job's logs once the request summary line is deployed (the legacy job is not being redeployed, so this may only exist for the new runner) |
| Container image size, cold start | Not built in this session | `docker images`; time from execution start to first log line |
| Firestore reads/writes per run | The platform does not exist yet | Counter in `TenantRepo` (Milestone 1 step 4) |
| After-sync-store numbers | Milestone 2 | Re-run sections 1 and 2 and add a before/after table |

## How to repeat

```bash
cd backend
python -m bench.render_bench                 # no credentials needed
python -m bench.render_bench --json          # same, machine-readable
python -m bench.live_baseline --output-dir ../out/baseline-$(date +%F)   # needs .env; read-only, no upload
python main.py --all --dry-run               # prints the request summary line at the end
```

`bench.live_baseline` writes real rosters into the output folder. Keep it under `out/`,
which git ignores.
