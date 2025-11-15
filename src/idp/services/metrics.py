from __future__ import annotations

from prometheus_client import Counter, Histogram

EXTRACTION_LATENCY = Histogram(
    "idp_extraction_latency_ms",
    "Latency for end-to-end extraction",
    buckets=(100, 250, 500, 1000, 2000, 3000, 5000, 10000),
)

VALIDATION_FAILURES = Counter(
    "idp_validation_failures_total",
    "Number of validation failures",
    labelnames=("field",),
)

DOCUMENT_PROCESSED = Counter(
    "idp_documents_processed_total",
    "Documents processed",
    labelnames=("doc_type",),
)
