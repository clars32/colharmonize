You are rewriting metadata column names for a robustness test. Do not use any
tool except Read, and read only the one file named below.

Read `{NAMES_FILE}`. It lists 72 sample-characteristic column names from GEO
gene-expression series, each with an `id`, the `study` accession and the
`column` name. For each, write the name a different author might have used for
the same column.

Rules:
- **Same meaning, same information.** Keep every unit, code legend and
  qualifier ("(years)", "(0, neg; 1, pos)", "-1=unavailable", "log2"), and
  every gene, lesion, assay or score name, in substance. You may rewrite their
  form ("yrs" for "years", "translocation 9;22" for "t(9;22)").
- **Different wording.** Use synonyms, expand or introduce standard
  abbreviations, reorder words, change case and separators (snake_case, dots,
  spaces). Share as few words with the original as the meaning allows.
- **No more specific, no less specific.** Don't resolve an ambiguous name
  ("condition" must not become "disease"; "strain" must not become
  "genotype"), and don't make a specific name generic.
- **Vary repeated names.** When the same name appears in several studies, give
  each study a different paraphrase, as different authors would.
- You see only names, not values. Don't guess what the values are.

Reply with one JSON object and nothing else, in a ```json fenced block,
mapping each `id` to its new name:

```json
{"GSE000000::body weight (kg)": "Weight, kg"}
```
