Title: A cross compare's job row leaves out the samples of the unnamed family

On the jobs page, a cross compare's row says how many samples it compared and then lists them, grouped by family. Samples of family 0 are not listed at all, although the count includes them. Family 0 is the unnamed family every mcrit storage keeps, and a sample submitted without a family lands in it.

`job_description` in `mcritweb/templates/table/job_row.html` groups the samples with `{% if sample_entry.family_id %}`, which is false for family 0. Every other description in that template shows family 0 as "Unnamed", through `format_family_name`.

Found while reading that template for #198, and reproduced on master (e4bfa55) against mcrit 1.9.0. A sample submitted without a family went into family 0 as sample 66. Its cross compare with sample 16 shows on the jobs page as "CrossCompare | 2 samples", followed by `fastlist | 16` alone.

Fix direction: skip only a sample whose `family_id` is None.
