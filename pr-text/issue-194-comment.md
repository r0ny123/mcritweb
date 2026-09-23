I measured this against a live mcrit 1.9.0. The largest real 1vN page had 11.6k functions and 677 function matches. I also rendered synthetic reports of up to 349k function matches and 5,000 samples through the app factory. Both halves of the issue are already covered or not repeated work:

- **The function-aggregation rebuild is covered by open PRs.** The repeat comes from the view's `len(getAggregatedFunctionMatches(...))` calls. #145 replaces those, as #185 asks, and with #145 the page builds the aggregation once, in the template. #152 separately builds it once in the view and takes both the count and the page slice from it.
- **The `sample_matches` passes don't repeat anything.** The six passes each compute a different value, once:
  - two ranked lists, with different `malware_only`/`library_only` flags;
  - four counts.

  Together they cost 0.005 to 2 ms, which is at most 0.08% of the page at the largest size. Taking the counts from the list lengths would also change the output, because the lists group by family name and the counts by family_id.

Nothing is left for its own PR beyond #145 and #152. I'd close this once either of them lands.
