Measured, and I'd close this as not worth changing:

- In mcrit 1.9.0, `hasLibraryMatch` and `getFamilyIdsMatchedByFunctionId` are already single dict lookups. 100 rows take 0.026 ms. Building the maps the issue suggests takes 13.9 ms on a synthetic 34k-match report, so the change would make pages slower.
- The per-cell badge test costs about 0.5 ms per 100-row table. Hoisting it would mean threading a flag through the row macros, which AGENTS.md advises against.
- The two `join_hint_strings` calls sit in mutually exclusive branches: one call per row, about 0.2 ms per 100 rows.

Found along the way: `result_compare_function.html` leaves `<i>` tags unclosed in the `is_pichash`, `is_library_match` and `is_unique_match` cells. #209 closes them.
