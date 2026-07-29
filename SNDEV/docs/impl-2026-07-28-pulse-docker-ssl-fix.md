# Title: fix-pulse-docker-ssl
# Date: 2026-07-28T12:00:00Z
# Author: Seth Nenninger (tencent/hy3 Agent)
# Contribution Type: Implementation
# Ticket/Context: Docker build failure at stage-3 `pip install` (REMAINING_WORK R1 - real PyPulse image)
# Summary: Align the Pulse runtime base image to Debian bullseye so Python's _ssl
#          module loads, allowing pip to reach PyPI over HTTPS.
#=============================================================================

## 1. Task Reference
Docker build of `middleware/Dockerfile.pulse` fails at stage-3:
```
#20 [stage-3  9/11] RUN pip install --no-cache-dir -r /app/requirements.txt
WARNING: pip is configured with locations that require TLS/SSL, however the ssl module in Python is not available.
...
ERROR: Could not find a version that satisfies the requirement fastapi==0.110.0 (from versions: none)
ERROR: failed to solve: process "/bin/sh -c pip install --no-cache-dir -r /app/requirements.txt" did not complete successfully: exit code: 1
```

## 2. Specification Summary
The middleware requires a reproducible runtime that (a) can `pip install` its
`requirements.txt` from PyPI and (b) can load the compiled PyPulse engine
bindings + superbuild shared libs (protobuf/boost/abseil) copied from the
`pulse-builder` stage via `COPY --from=pulse-builder /usr/local/lib ...`.

## 3. Implementation Notes
Files changed:
  - `middleware/Dockerfile.pulse`
      * Line 115: `FROM python:3.11-slim`  ->  `FROM python:3.11-slim-bullseye`
      * Line 120-122: added `zlib1g` and `libcurl4` to the runtime apt install
        (superbuild shared libs link against these; libstdc++6 retained).

Root cause:
  - The `pulse-builder` stages use `python:3.11-bullseye`, so the copied
    `/usr/local/lib` content (Python `_ssl.so` + protobuf/boost/abseil `.so`
    files) is linked against bullseye's `libssl1.1`.
  - The runtime previously used the un-pinned `python:3.11-slim`, whose default
    Debian base (bookworm/newer) only provides `libssl3` (`libssl.so.3`).
  - Result: `import ssl` fails in the runtime image ("ssl module is not
    available"), so `pip` cannot connect to PyPI over HTTPS, and every package
    resolution fails.

Fix rationale:
  - Pinning the runtime to `python:3.11-slim-bullseye` makes its libssl ABI
    match the builder's copied `/usr/local/lib` exactly, restoring `_ssl` and
    pip/HTTPS, while keeping the image slim.
  - `zlib1g`/`libcurl4` are installed defensively because the superbuild
    libraries copied from the builder are likely linked against them.

Verification:
  - Empirical ABI proof (run on this host, Docker 25.0.3):
      * OLD base `python:3.11-slim` (unpinned) now resolves to OpenSSL **3.5.6**
        (libssl3, Python 3.11.15) -> only `libssl.so.3` present.
      * NEW base `python:3.11-slim-bullseye` -> OpenSSL **1.1.1w**
        (libssl1.1, Python 3.11.13) -> `libssl.so.1.1` present, `import ssl`
        succeeds. This matches the builder stage's libssl ABI, so the copied
        `/usr/local/lib` (_ssl.so + protobuf/boost/abseil) loads and pip can
        reach PyPI over HTTPS.
  - `docker build --check` is unavailable in this Docker version, so full
    syntax validation is deferred to the real build.
  - Full image build + IQ-4 gate must be run by the user via
    `SNDEV/scripts/build-pulse.sh` (compiles Pulse from source; requires the
    vendored `.pulse/` source for VARIANT=local or network for VARIANT=git).

## Addendum: stage-11 IndentationError (IQ-4 build gate)
After the SSL fix, the build reached the final stage (stage-3 11/11) but failed
with:
```
IndentationError: unexpected indent
  File "<string>", line 1
    import Pulse; from Pulse import Engine; ...
```
Root cause: the gate used `RUN python -c " \` with a SPACE immediately after the
opening quote, so the program string Python received began with a leading space
(`" import Pulse; ...`). Python parsed that leading space as indentation on the
first line -> `IndentationError`.

Fix: replaced the `python -c " \` continuation form with a BuildKit heredoc
(`RUN python - <<'PY' ... PY`) so the program text has no leading whitespace and
requires no shell line-continuation escaping. The single-quoted delimiter (`'PY'`)
prevents shell interpolation of the assert message's single quotes.

Verification:
  - Heredoc form is valid under BuildKit (already in use; the build progressed
    through all prior stages). The user must re-run `SNDEV/scripts/build-pulse.sh`
    to confirm the IQ-4 gate now prints `ENGINE INIT OK`.
