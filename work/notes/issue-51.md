# Issue #51 — "Proper sort / search for jobs"

**Blocked on the backend.** Also: the issue's own migration note is out of date.

## What the migration note says

> A search feature exists in the interface ("templates/jobs.html:143-146 POSTs a
> `Search` field"), but it remains non-functional. The `data.jobs()` method receives
> the query parameter but "it is never used for filtering".

## What is actually there at `df53db9`

The whole block is inside a Jinja comment. `mcritweb/templates/jobs.html:139-148`:

```jinja
  {#
  {% if query %}
  <p>Results for "{{ query }}"</p>
  {% endif %}
  <form style="width:100%" method="POST" required>
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="text" class="form-control shadow-none" name="Search"id="Search" placeholder="Search" autofocus autocomplete="on">
    <input type='submit' hidden>
  </form>
  #}
```

So there is **no search box on the jobs page at all**. Measured: a POST of
`Search=zzz-nothing-matches` to `/data/jobs` returns 200 and the page contains neither
`Results for` nor any filtering — the form that would produce that POST is commented
out, and `data.jobs()` still opens with

```python
    query = None
    if request.method == 'POST':
        query = request.form['Search']
```

and passes `query` to a template that ignores it.

The sorting half of the issue **is** done, as the note says: `data.jobs()` calls
`client.getQueueData(start=..., limit=..., method=..., state=..., ascending=...)`.

## Why nothing shipped

A working job search needs the backend to filter. `McritClient.getQueueData` takes
`start`, `limit`, `method`, `state` and `ascending` — there is no search or free-text
parameter, so MCRITweb cannot filter server-side, and filtering the 25 rows it happens
to have fetched is the "sort should be done in mcrit and not only consider displayed
elements" the issue explicitly rejects.

That makes this a `mcrit` change first. Nothing in this repository can deliver it.

## Small adjacent bug, noticed and not fixed

`data.jobs()` reads `request.form['Search']` rather than `.get`, so a POST to
`/data/jobs` without that field is a `BadRequestKeyError` → HTTP 400. Unreachable from
the UI while the form is commented out, and it is dead code either way — the honest fix
is to decide whether the POST branch stays at all, which is the same decision as the
issue itself. Left alone rather than patched into a shape that outlives its purpose.

## Suggested comment for the issue

> The migration note has drifted: the search form in `templates/jobs.html` is inside a
> `{# ... #}` comment as of v1.4.8, so there is no search box on the jobs page — the
> dead `request.form['Search']` read in `data.jobs()` is all that is left of it.
> Sorting and pagination are done. The search half needs a filter parameter on
> `getQueueData`, so it is a `mcrit` change before it is a MCRITweb one.
