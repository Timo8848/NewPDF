# Performance Report

> Numbers in this file are produced by `scripts/eval.py`. Do not hand-edit.
> The `reports/eval_results.md` file is regenerated on every run; this file
> records methodology and historical context.

## Methodology

1. `tests/fixtures/synthetic.py` generates a deterministic dataset:
   - 20 synthetic invoices (random invoice numbers, dates, amounts, tax IDs,
     routing/account numbers).
   - 10 synthetic ID cards (random ID number, birth date, expiry, MRZ).
2. Each sample is rendered to a PNG with a monospace TrueType font.
3. The production pipeline (Tesseract → `HeuristicExtractor` → validators)
   runs on every sample.
4. Predictions are compared to the ground-truth dict character-for-character
   (after lowercasing and stripping commas). Per-field precision, recall,
   and F1 are aggregated.

## Latest run

See [`eval_results.md`](eval_results.md) for the auto-generated table.

The most recent run on 30 samples reported:

| Metric          | Value  |
| --------------- | ------ |
| Micro precision | 0.955  |
| Micro recall    | 1.000  |
| Micro F1        | 0.977  |

## Known limitations

- **Synthetic OCR is too easy.** The fixtures are clean, perfectly aligned,
  and rendered with a single high-contrast monospace font. Real scans
  introduce skew, glare, glyph confusions, and wildly varying layouts that
  this benchmark does not exercise. Treat the numbers above as an upper
  bound on the regex layer's correctness, not as a real-world accuracy
  estimate.
- **No layout signal.** The extractor uses OCR full text and ignores the
  bounding boxes that Tesseract emits. Multi-column invoices and tables
  with adjacent labels are likely to confuse the anchor regexes.
- **MRZ parsing is detection-only.** The MRZ regex returns the raw line; it
  does not parse out name / nationality / check digits, and the synthetic
  ground truth currently does not include MRZ values, so the field shows
  up as "spurious" in the per-field table.
- **English only.** Tesseract is configured with `eng`; other language
  packs are not installed in CI or the Docker image.

## Error buckets to chase next

1. Add a small real-world labeled corpus (10–30 invoices) and report
   numbers separately from the synthetic eval.
2. Fold OCR token bounding boxes into the extractor so labels and values
   on the same row are linked even when the regex anchor fails.
3. Extend ground truth to include MRZ lines so detection contributes
   honestly to the F1 score.
