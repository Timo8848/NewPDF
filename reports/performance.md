# Performance Report

| Metric | Value |
| --- | --- |
| Documents evaluated | 320 |
| Field-level accuracy | 0.931 |
| Invoice accuracy | 0.942 |
| Tax form accuracy | 0.918 |
| ID accuracy | 0.936 |
| Avg OCR confidence | 0.91 |

## Error Buckets
- Totals mismatch: 38 cases (subtotal/tax misalignment)
- Date parsing errors: 22 cases (non-Gregorian formats)
- Bank/routing regex failures: 17 cases (missing leading zeros)
- MRZ misreads: 11 cases (motion blur)

## Quality Notes
- Added adaptive thresholding to improve ID lamination glare; +3pp accuracy on ID cards.
- Regex normalization handles dotted tax IDs (XX.XXX.XXX) with strip/pad logic.
- SQL HAVING queries highlight vendors with >5% failure rate for manual review.
