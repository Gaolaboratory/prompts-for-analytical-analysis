# Differential statistics on an untargeted metabolomics matrix

Write `stats.py`. Run: `python3 stats.py quant_mtbls14397_pos.csv groups.tsv -o stats.tsv`

Python standard library plus numpy, pandas and scipy only. No other third-party packages.

## Input

Both files are in the working directory.

- `quant_mtbls14397_pos.csv` — first column `feature_id`, then 6 sample columns:
  618 feature rows of **raw linear peak areas**. No transform has been applied; the tool
  does the `log2` itself.
- `groups.tsv` — tab-separated. The `pinned_column` column names the sample (matching a
  column of the CSV above); the `group` column is `CTRL` or `EXP`.

## Output

`stats.tsv`, one row per **tested** feature, sorted by ascending `p_value`:

```
feature_id	log2fc	t	df	p_value	q_value	significant
```

One line on stdout: `tested=<n> filtered=<n> significant=<n>`.

## Method

- Keep a feature only if it has **at least 3 valid values in each condition**; otherwise
  it is filtered, not tested.
- Take `log2` of every valid value before testing.
- `scipy.stats.ttest_ind(..., equal_var=False)` (Welch, unequal variances) on the log2
  values.
- `df` is the fractional Welch–Satterthwaite degrees of freedom. With 3 replicates per
  group it comes out fractional (3.03–4.00 on this data): **do not** round it to an
  integer, and do not fall back to Student's (pooled-variance) t-test.
- `log2FC = mean(log2 EXP) − mean(log2 CTRL)`, in that order, so a negative value means
  depleted in EXP.
- Benjamini–Hochberg across the `m` tested features: ranks from 1 (by ascending p),
  q = p · m / rank, then a **monotone sweep from the largest rank down** so each q is the
  minimum of itself and the next-larger-rank's q, capped at 1.
- `significant` is `1` iff **both** `q_value < 0.05` **and** `|log2fc| ≥ 1`, else `0`.

## Acceptance criteria

1. `stats.tsv: header + 618 rows sorted by p_value, columns in order`
2. `stdout reports tested=618 filtered=0 significant=253, and the significant column matches the reference on every row`
3. `t and p_value match the reference within 1e-6 relative on every row`
4. `df within 1e-6 relative and log2fc within 1e-9 relative on every row`
5. `q_value within 1e-6 relative, with the top-8 BH plateau reproduced`
6. `top 10 features by p_value are the reference ten, in order`

This is real data. Do not tune a constant to make a number match; if a criterion fails,
the statistics are wrong.
