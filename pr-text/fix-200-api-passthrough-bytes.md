Title: Forward the backend's bytes through the API passthrough instead of re-encoding them

## Summary
Fixes #200.

The API passthrough parsed every backend answer with `response.json()` and re-serialised it with `json.dumps()`, only to send the same document on. It now forwards the backend's bytes.

## What changed
- `handle_raw_response` (`mcritweb/views/api.py`) forwards `response.content` with the backend's status and the backend's own `Content-Type`. It does this when that content type is `application/json` and the body is not empty. No other backend header is passed on: no cookies, no hop-by-hop headers, no internal headers.
- The backend's JSON error answers (400, 404, 409, 500, …) are now forwarded as well, where before they were reduced to a bare status. The message is written for the client. McritClient ignores error bodies, so it is unaffected.
- A 200 or 202 whose body is not JSON (a proxy's error or login page, an empty answer) now gets a `502` and one warning line in the log. It used to raise `JSONDecodeError` and end as an unhandled 500. A non-JSON error page keeps its status and loses its body, as before.
- New `tests/testApiPassthrough.py`.

## Why
Nothing in the router inspects the body. For job results and function listings, the round trip was a full extra pass over megabytes of JSON on every request.

## Validation
- `tests/testApiPassthrough.py` has 14 cases: 12 fail on master, and all 14 pass on this branch. The two that pass on master pin the error-page behaviour, which is deliberately unchanged. The fake responses in these tests refuse `.json()`, so if the parse ever came back, the tests would fail.
- The full suite passes and `ruff check .` is clean.
- Live against mcrit 1.9.0, I compared 22 `/api` endpoints on master and on this branch: status, samples, families, functions, jobs, 1vsN, cross and unique-blocks results, and missing ids. Every successful response is parsed-equal to master, and in fact byte-identical to both master's output and the backend's own bytes. A missing id now returns the backend's 404 message instead of an empty body.
- The cost of `handle_raw_response` alone, measured in process on real answers:

  | Response | Size | Before | After |
  |---|---|---|---|
  | unique-blocks result | 2.3 MB | 117 ms | 0.004 ms |
  | samples/7/functions | 1.5 MB | 66 ms | ~0 |
  | functions?limit=500 | 1.3 MB | 39 ms | ~0 |

- End to end, `/api/jobs/<unique blocks>/result` went from 126 ms to about 50 ms (median of 15 runs, on a noisy host).
- Against a stub backend, an HTML 200 and an empty 200 now return 502 instead of an unhandled 500. The stub's `Set-Cookie` and internal headers never reach the client.

## Limitations
- `Content-Type` changes from Flask's default `text/html; charset=utf-8` to the backend's `application/json`.
- The body keeps the backend's own formatting. With mcrit's `json_util` that is byte-identical to the old output. A backend that formats differently would no longer be normalised, but the JSON is semantically the same.
- A valid JSON body sent under a non-JSON content type would now be a 502. mcrit always sends `application/json`.
- `/api/functions/<id>` still pays one parse, inside mcrit's `getFunctionById`, which calls `handle_response()` before its raw check. That is upstream.
- Merge coordination with #130: its `backend_unreachable` docstring in `views/api.py` says error answers are body-less "as handle_raw_response already is for every non-200 it forwards". That stops being true once this merges. The two PRs also touch neighbouring import lines (#130 adds `import requests` next to the `import json` removed here). Whichever lands second needs that sentence adjusted.
- Error bodies: mcrit 1.9.0 registers no custom falcon error handler, so an uncaught backend exception still reaches the client only as falcon's generic `{"title": "500 Internal Server Error"}`. The `{"status":"failed","data":{"message":...}}` bodies on routed paths are fixed strings. The callers are token holders who can already read every successful answer.
