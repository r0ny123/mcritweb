The function aggregation part is covered by two PRs:

- The two `len(getAggregatedFunctionMatches(...))` calls and their `unfiltered=True` twins are #185's. #145 replaces them with counts.
- The template aggregating the whole filtered report just to slice out one page is #224's. It now aggregates only the page. On the 11.6k-function sample's 1vN page, the render went from 174 ms to 130 ms. 45 result pages render byte-identical to master, the past-the-end page included.

The sample-match passes were measured and left alone on purpose. Each of them computes a different value, once: two ranked lists with different filters, and four counts over filtered and original data. Together they take about 0.005 ms on the live 1vsN report, and they can't be merged without changing what they compute.

So once #145 and #224 are merged, I'd close this.
