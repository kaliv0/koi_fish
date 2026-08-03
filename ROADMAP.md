# `runner.py` review summary

Scan of potential improvements, edge cases, memory concerns, and performance notes. No code changes implied.

## Highest impact

- **Stdout/stderr streaming can deadlock.** The loop always blocks on `stdout.read1()` first and only then reads stderr. A command that writes heavily to stderr (or only to stderr) can fill the stderr pipe and hang while koi waits on stdout. [DONE]
- **`--silent` buffers all output** via `communicate()` — fine for small logs, unbounded memory for noisy/long tasks. [DONE]
- **`post_run` is not a cleanup hook.** Everything is joined with `&&`, so `post_run` runs only if pre/commands succeeded. A failed command skips it.
- **`-f` / `-D` with no `[run]` table** hits `self.data[Table.RUN]` and can raise `KeyError` instead of a clean error.

## Correctness / edge cases

- **Deferred tasks only run when `fail_fast` is set** (`if self.fail_fast and self.deferred_tasks`). Easy to misunderstand.
- **`tomllib.load` is uncaught** — invalid TOML becomes a traceback, not a friendly failure.
- **`.decode("utf-8")` can raise** on binary output.
- **`prepare_description_log`** — `max(data, key=len)` crashes on an empty table.
- **Flow validation is shallow** — checks for the literal `"run"` in a flow list, not nested/cyclic flow refs (if you ever add those).
- **Daemonizing children** that call `setsid()` still escape `killpg`.
- **`shell=True` + string commands** — expected for a task runner, but the config is fully trusted shell input.

## Design / maintainability

- **`task_flow` cached_property mutates `all_tasks`** — side effect on first access; awkward to reason about/test.
- **`skipped_tasks` is also cached** — safe today (only used after the run), fragile if reused earlier.
- **Spinner future result is never checked** — exceptions in the spinner thread are swallowed.
- **`ThreadPoolExecutor(2)` per silent task** — extra churn; a daemon thread or one shared executor would be simpler (not a real leak for short CLI runs).

## Performance (usually minor for a CLI runner)

- **`task in skip_list`** over a `chain`/list is O(n) per task; a `set` would scale better for big flows.
- **Non-silent path**: one-at-a-time `read1` + decode + print is fine for interactivity, not for max throughput.
- No meaningful long-lived memory leak pattern for a one-shot CLI process; the real memory risk is silent-mode buffering and deadlocked pipe fill.

## Not bugs, but worth knowing

- Interrupt handling + process-group teardown is in good shape after the recent fix.
- `failed_tasks` double-counting on build vs execute looks handled correctly via `continue`.
