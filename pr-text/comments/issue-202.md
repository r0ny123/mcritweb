Where the three parts stand:

- **The atomic write** is in #145: `write_atomically`, and an unreadable cache file is skipped instead of failing the page.
- **Size.** #229 bounds the result cache and writes cached reports and downloads as compact JSON. The cache is about 35% smaller, downloads parse to the same data, and a bound of 3 files holds and refetches. It has to merge after #145, or together with it.
- **Exports.** #F202PR passes an export on as the backend's bytes, instead of parsing it into a dict and serialising it again, so a whole-corpus export is held once in MCRITweb instead of twice. That takes a client that honours `raw_responses` for `getExportData`. mcrit 1.9.0's client ignores it and parses, and with it the export routes behave exactly as before. danielplohmann/mcrit#183 (open) makes the client honour it, in 608a364. With that client, the whole-corpus export's allocation peak went from 91.1 MiB to 61.0 MiB, and the file is the same export.

With #145, #229 and #F202PR in, this is done.
