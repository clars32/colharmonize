This is a memory probe. Answer only from what you remember from training.

Do not use any tools. Do not read files, list directories, search the web,
fetch pages or run commands. An answer produced with any tool is discarded.

For each NCBI GEO series accession below, write what you remember about it:

- `title`: the series title, or null if you don't remember it.
- `characteristics`: the sample characteristics recorded in the series'
  `!Sample_characteristics_ch1` lines. For each one give the `key` as written
  in GEO, and `values`: the distinct values as written in GEO for a
  categorical key, or an empty list for a numeric one (set `numeric` true).
- `confidence`: "none", "low", "medium" or "high".

If you don't remember a series, give `title` null, an empty
`characteristics` list and confidence "none". An empty answer is a valid
answer. If you remember something, give it even if unsure, and mark the
confidence low.

Accessions:
{ACCESSIONS}

Reply with one JSON object and nothing else, in a ```json fenced block, keyed
by accession:

```json
{
  "GSE000000": {
    "title": "...",
    "confidence": "low",
    "characteristics": [
      {"key": "...", "numeric": false, "values": ["...", "..."]}
    ]
  }
}
```
