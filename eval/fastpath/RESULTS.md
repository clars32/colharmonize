# Easy-first fast path: results

Handoff task 12, 2026-10-09. Measured from existing candidates and outputs
by `measure.py`, with no new runs. The rule variants were compared on tuning.
The sealed numbers are post hoc. Full table: `out/measure.md`.

## The rule

A column is annotated by code, with predicate exact, the matched term and no
qualifiers, and no subagent sees it, when:
1. its name, with any parenthetical removed, equals the label of exactly one
   property-space term (an exact synonym is not enough), and
2. its values agree with that term:
   - when the values propose categories (decision 5.1), the term is the top
     one
   - when they propose none, the values are numeric, which covers a quantity
     such as `age`

The value check is the guard against iteration 2's `strain` trap:
`strain` holding Control / Down syndrome proposes `disease`, so it goes to
the subagents. `condition` matches `disease` only as a synonym, so it is
never taken.

## Results

| | tuning | sealed (post hoc) |
|---|---|---|
| columns taken by the fast path | 12 of 105 (11%) | 14 of 141 (10%) |
| fast path right, on gold columns taken | 6/6 | 12/14 |
| pipeline right on the same columns | 6/6 | 12/14 |
| annotate batches saved (12 items per batch) | 1 per run (9 → 8) | 1 per run (12 → 11): 2 of the sealed run's 41 subagent runs |

The two sealed misses are ones the pipeline also gets wrong:
- `sample_id` → `sample ID`, where gold says identifiers take `none`
- `n-stage (0, neg; 1, pos)` → exact `N stage`, where gold says broad

Without the value guard (name match alone), accuracy on the columns taken
falls to 82% on tuning and 74% on sealed, against the pipeline's 94% and 89%.
A synonym match adds a few columns and, on tuning, an error.

## Reading

- **The guarded fast path is safe.** On the columns it takes, it matches the
  pipeline exactly on both corpora.
- **It saves little:**
  - about 10% of annotation items
  - one batch per annotate run
  - about 5% of a run's subagent calls

  These are the columns the subagents already get right, so accuracy doesn't
  change either.
- **Not built into the pipeline.** A second annotation path, with its own
  review tier and spot-check mechanics, costs more than 5% of subagent calls
  is worth. Revisit for large corpora, where the share of plain `age`, `sex`
  and `tissue` columns would be higher. GEOMeta's 595k samples are dominated
  by such fields. If it is built, these columns should go to the
  `pre_accepted` tier with a "fast path" reason, so a person spot-checks
  them.
- This is not an annotation confidence signal. These columns are easy, and
  being easy is not the same as being reliably right on hard columns
  (decisions log 15.2).
