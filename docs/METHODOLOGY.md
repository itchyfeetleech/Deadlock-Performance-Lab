# Methodology

## Capture

Live capture uses MangoHud with `log_interval=0`: one row per rendered frame. MangoHud's `elapsed` field is nanoseconds since the logger started ([source](https://github.com/flightlessmango/MangoHud/blob/master/src/logging.cpp)). The CSV header is detected dynamically, including versioned logs and optional telemetry columns.

For each capture the runner launches a fresh game process, waits for a run-specific CSV and the engine's completed demo-signon message, warms the replay, seeks back to the requested tick, pauses to settle the camera, records the latest logger timestamp and resumes. The analysis window is `[start_elapsed_s, start_elapsed_s + sample_s)`. The game is then closed so the file is complete before it's hashed and parsed. Loading and warm-up fall outside the window. Command and logger timing aren't tick-exact, so this is not a deterministic engine timedemo.

New plans use readiness protocol `source2-demo-signon-v3`: the temporary startup config opens the replay and the runner seeks as soon as signon completes. A per-launch marker lets early signon output be recovered from `console.log` without accepting stale output. Older frozen plans keep their console-started replay and load guard.

Cvars are read back in one batch followed by an echo acknowledgement. For single-cvar sweeps and console-cvar profiles, a missing or different reply blocks the verdict, because that cvar is what's being tested. A config is measured as a whole file: every `gameinfo.gi` setting that differs from your installed file is read back, and the report says how many are hidden and which read back differently, without blocking the verdict. The run-wide FPS limit is read back the same way. If the game rewrites `video.txt` during a capture, the changed values are reported and the original file is still restored. A missing acknowledgement fails the capture.

Any positive finite frame time is kept, however large. Nonpositive, NaN, infinite and malformed rows are counted and reported, and block a verdict. Missing logs, too few samples, backwards timestamps, per-frame coverage outside 80–120% of elapsed time and incomplete windows fail the capture.

## Metrics

Frame times are milliseconds. Quantiles linearly interpolate the sorted data at `(N - 1) × percentile`.

| Metric | Definition |
|---|---|
| Average FPS | `1000 / mean(frame_ms)` |
| 1% low FPS | `1000 / mean(slowest ceil(0.01 × N) frame_ms)` |
| 0.1% low FPS | Same with `0.001`; only with at least 1,000 per-frame samples |
| Inverse P99 FPS | `1000 / P99(frame_ms)` |
| P95 / P99 | Frame-time percentiles |
| Maximum frame | Largest frame time, unclipped |
| Budget misses | Share of frames longer than `1000 / budget_fps` |
| Stalls | Frames over 50 ms and over 100 ms |
| Telemetry | MangoHud CPU/GPU load, temperature, clocks, memory and power, where available |

Telemetry is sampled on MangoHud's own cadence and may repeat between frames. CPU load is system-wide, not per process, and zero can mean the sensor isn't supported.

The report's frame-time traces group frames into up to 360 time slices, each with its min, mean and max; statistics always use every frame in the window. Each capture also stores its frame-time percentiles from 0% to 99.99%, spaced evenly in "nines" (90%, 99%, 99.9%) as in HdrHistogram plots. A config's percentile curve is the mean of its captures' curves, and stops where a capture has too few frames for the percentile (99.9% needs 1,000). Results recorded before percentiles were stored get them from their raw capture when the report is built, if its hash still matches.

Interval-sampled imports keep sampled FPS and percentiles but have no 1% or 0.1% lows and no verdict, and can't be mixed with per-frame captures.

## Rounds and verdicts

A **round** is an opening baseline, each config once in a seeded shuffled order, and a closing baseline. For config `T` in a round:

```text
control = mean(opening baseline FPS, closing baseline FPS)
round change = 100 × (T FPS / control - 1)
```

The reported change is the mean round change. Its 95% interval is a deterministic percentile bootstrap over complete rounds (4,000 resamples; needs 3 rounds). The 1% low change and its interval are computed the same way and never decide a verdict. Intervals are not corrected for comparing many configs.

A verdict (average FPS only) needs all of:

- at least 5 complete rounds, and every planned round complete;
- baseline CV and opening-to-closing drift both within the threshold (default 3%);
- matching capture conditions and profile fingerprints, verified raw hashes, and no unchecked or failed capture checks;
- a replay scenario (bot matches never get one).

Then an interval wholly above +threshold is *improved*, wholly below −threshold is *regressed*, and wholly inside is *within threshold*. Anything else is *inconclusive*. Made-up demo data is always *demo*.

The app can't see the screen, so live captures carry checks (camera, replay progress, config applied) that you clear with **Mark as checked** or `dpl review`. A review is bound to the result's hash and can't clear data errors or missing conditions.
