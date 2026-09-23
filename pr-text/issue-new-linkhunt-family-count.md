Title: Link hunt answers 500 when a filter is submitted with the family count left empty

On a 1vN job's link hunt page (`/data/linkhunt/<job_id>`), set any filter, leave "Unpenalized family count" empty, and press Filter. The page is a 500:

```
TypeError: '<' not supported between instances of 'int' and 'NoneType'
  mcrit/storage/MatchingResult.py:530, in getLinkHuntResults
```

`linkhunt_for_sample_or_query` (`mcritweb/views/data.py`) parses each field of the form, and an empty field becomes `None`. The two presets, the page's defaults and "clear", both set `filter_unpenalized_family_count` to 2. A filter the user fills in passes whatever the form held, and mcrit compares this count to an int. The other fields can be empty, because the "clear" preset sends `None` for all of them.

Reproduced on master (e4bfa55) against mcrit 1.9.0, with both `filter_link_score=5` and `filter_min_score=70`, each with `filter_unpenalized_family_count=` empty: 500 in both cases.

Fix direction: give an empty count the presets' 2.
