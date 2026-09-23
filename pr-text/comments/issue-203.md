I checked this, and it isn't a bug. The cached diagram doesn't depend on the filters:

- `MatchingResult.applyFilterValues` (mcrit 1.9.0) only rewrites the `filtered_*` attributes.
- `MatchReportRenderer` draws from the unfiltered `function_matches` and `library_matches` (`mcritweb/views/MatchReportRenderer.py:93`, `:117` and `:122` at e4bfa55).
- The `famid` / `samid` / `funid` variants are already part of the file name.

Live on e4bfa55, with the 1vsN job for sample 7:
- I cleared `instance/cache/diagrams` and rendered all four variants (plain, `famid=1`, `samid=8`, `funid=1016`) under six filters: `filter_function_min_score=90`, `filter_exclude_library`, `filter_exclude_pic`, `filter_unique_only`, `filter_direct_min_score=50` and `filter_exclude_own_family`.
- I cleared it again, and rendered them with no filters.
- The md5 of each PNG matched.

#145's `render_missing_match_diagram` relies on the same property. I'd close this.
