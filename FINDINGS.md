# Findings: real gaps found building a production-shaped app on Hayavega

Built 2026-11-12 against Hayavega `main` (commit `35e03cc`). Every number
below is measured directly on this machine, not estimated -- the methodology
for each is included so it can be re-run.

## 1. CRITICAL -- the rate limiter's default security layer has a severe, quantified O(n) scaling bug

`hayavega.hardening.RateLimiter.allow()` calls `self._prune(now)` on
**every single call**, which iterates **every currently-tracked client
key** (up to `max_clients`, default 10,000) to evict idle ones -- all
while holding the limiter's one global lock. This runs on every HTTP
request by default: `hayavega.management.commands._launch` always
builds a `HardeningOptions` instance (never `None`), so `Hardening` is
active for every project launched via `manage.py launch` unless a
project explicitly disables it.

**Measured directly** (`hayavega.hardening.RateLimiter`, isolated, no
HTTP involved):

| Tracked distinct clients | `allow()` cost | Calls/sec (process-wide ceiling) |
|---|---:|---:|
| 1 | 1.0 µs | ~955,000 |
| 10,000 (the framework's own default `max_clients`) | 2,757.8 µs | **~363** |

A **~2,700x** slowdown. At 10,000 tracked clients -- which any
real-traffic deployment reaches within hours, not a contrived edge case
-- every request serializes through one lock doing a full linear scan,
capping **total process throughput at roughly 363 req/s**, regardless
of CPU core count, worker thread count, or `processes=` multi-process
scaling (PR #13 earlier this session). This is in the hot path of
*every* request to *every* Hayavega app using default hardening, not
specific to this HRMS app.

**Root cause**: `_prune()` is unconditionally global instead of scoped
to the one key `allow()` was actually called for. The per-key pruning
that *is* correctly scoped already exists a few lines later (`while
entries and entries[0] <= now - self.window_seconds: entries.popleft()`)
-- the global `_prune()` call is the redundant, expensive step: it's
solving "evict globally idle clients so `max_clients` doesn't grow
forever," but it's solving it the most expensive possible way. A
real-world HRMS behind a corporate network, serving even a modest
number of distinct employee IPs over a day, would hit this directly.

**Reproduce**: see this repo's commit history / ask for the one-file
microbenchmark script used above (populate `RateLimiter` with N clients
via `allow()`, then time `allow()` for one already-tracked key).

**Recommendation**: fix in Hayavega directly before this is called
"secure by default" without qualification -- the security feature
itself becomes the throughput ceiling at realistic scale.

## 2. HIGH -- no named/typed path-parameter routing at all

Hayavega has no `/employees/<id:int>`-style routing. The *only* dynamic
URL mechanism is a single trailing `/<path>` wildcard suffix, documented
in Hayavega's own `docs/topics/routing.md`: "A path ending in `/<path>`
matches any suffix, handed to the view via the request's path info."
There is no way to express a path *parameter* (named, typed, or
otherwise) -- a view wanting `/employees/42`'s `42` must parse
`request.path` itself, exactly the technique `hayavega.static`'s
`static_routes()` uses internally for serving files.

This is Django/Flask/FastAPI/Express's most basic routing primitive.
Every REST detail/update/delete endpoint in a conventional app needs
it. Workable (see `hrms/employees/views.py::employee_detail`), but a
real gap against "industry standard" framework expectations.

## 3. HIGH -- registering two routes with the same pattern silently shadows the first, with zero error

`hayavega.runtime.create_application` collapses the route list into a
dict keyed by pattern (`routes = {route.pattern: route for route in
route_list}`) with **no duplicate-pattern check at all**. A developer
coming from Flask/Django naturally writes one view function per HTTP
method on the same path (`list_employees` for GET, `create_employee`
for POST, both at `/api/employees`) -- registering both silently drops
the first one with no warning, no error, no log line. The one it
actually keeps depends on dict-insertion order, which is easy to get
backwards.

Hayavega's own internal convention (confirmed in `hayavega.admin`'s own
routes) is one view per path, branching on `request.method` --
undocumented as a *requirement*, discovered only by reading the
framework's own source. `hrms/employees/views.py::employees_collection`
follows it, but only because this was caught during development, not
because anything told us to.

**Recommendation**: raise a clear `RouteConflictError` at
`create_application()` time when two routes share a pattern, rather
than silently shadowing.

## 4. MEDIUM -- the ORM has no secondary-index support at all

`hayavega.models.Column`/`Entity` support `PRIMARY KEY` and `UNIQUE`
only. There is no way to declare "index this column" on a model, and
`hayavega.migrations.generate()` (the migration auto-generator) has no
concept of an index operation -- it only ever emits `CREATE TABLE`/`ADD
COLUMN`. For this app's two most common real queries ("employees in
department X", "employees reporting to manager Y"), that would mean a
full table scan at any real scale without manual intervention.

**Worked around**, not fixed: `hrms/employees/migrations/0001_initial.py`
hand-writes `CREATE INDEX` statements after the generated `CREATE
TABLE` ones -- migrations are just one-SQL-statement-per-operation, so
this is possible, just not generated or declared anywhere near the
model.

## 5. MEDIUM -- no bulk-insert API; `Collection.append()` is one row, one connection, at a time

`hayavega.models.Collection.append()` opens a connection, inserts one
row, commits, and closes -- every single call. There is no
`bulk_create`/`insert_many` equivalent. Seeding (or importing from a
real HRIS migration, a realistic HRMS need) hundreds of thousands of
rows through this API would be impractically slow.

**Worked around**: `hrms/seed.py` bypasses the ORM entirely for bulk
writes, reaching into `Connection.raw` (the underlying DB-API
connection) to use `executemany()` directly, batched into transactions.
Real result: 100,000 rows seeded in 3.4s (~29,600 rows/s) this way,
vs. an impractical rate through `append()` one row at a time.

## 6. LOW -- a `path()` view returning a `dict` is `str()`'d into the body, not JSON-encoded

Only `api_route()`'s wrapper converts a `dict`/`list` return value to
`json_response()`. A `path()` view returning a dict silently gets
`Response(str(result))` -- Python's `str()` of a dict, not valid JSON.
An easy, silent mistake for anyone assuming the two are interchangeable
except for OpenAPI generation (which is the only difference the docs
describe).

## Not a bug, but a real operational lesson: the default rate limit needs tuning for this app's actual traffic shape

`rate_limit = 120` requests/60s **per client IP** is Hayavega's
documented, intentional hardened-by-default value -- correct for a
single end user, and not contradicted by any "opt-in" claim in the
docs (checked directly). But a real HRMS likely sits behind a corporate
network/VPN where many real employees can share one apparent IP; left
at the default, legitimate concurrent HR-app usage from one office
would get `429`'d. `hrms/config/settings.py` tunes this explicitly
(`rate_limit = 6000`) rather than leaving the default unexamined.

## Disclosed, not root-caused: local single-IP load test instability

A direct `oha -c 30` load test against `GET /api/employees` (Rust
runtime, 100,000-row dataset, on this Windows dev machine) showed a
sharp, reproducible cliff: 100% success at `-c 5`/`-c 10`, dropping to
36% success at `-c 30`, with `oha` reporting `os error 10048` ("only one
usage of each socket address... normally permitted" -- Windows
ephemeral-port exhaustion) and some requests aborting on deadline.
Finding #1 above does **not** explain this specific result (the test
used a single source IP, so the rate limiter's per-key tracking never
exceeded 1 entry, keeping its own cost negligible here). The real cause
was not isolated before this writeup was done -- candidates not ruled
out: lock contention elsewhere in the hardening/request pipeline under
high concurrent throughput, a Windows-loopback-specific `oha` artifact,
or something specific to this view's two sequential SQLite round trips
per request (a `COUNT(*)` for pagination's `total()`, then the actual
`SELECT`). Reported honestly as unresolved rather than attributed to a
guessed cause.
