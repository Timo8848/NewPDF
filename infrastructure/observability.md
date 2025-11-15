# Observability

## Logging
- Structured JSON logs via structlog (`idp.utils.logging`).
- Trace context includes `trace_id`, `span`, elapsed ms.
- PII redaction hook ready to plug into `structlog.processors` if needed.

## Metrics
- Prometheus counters/histograms defined in `idp.services.metrics`.
- `/metrics` endpoint exposes scrape-ready output.
- Key metrics: `idp_extraction_latency_ms`, `idp_documents_processed_total`, `idp_validation_failures_total{field}`.

## Tracing
- `idp.utils.logging.traced` context manager emits start/end events with durations.
- For OpenTelemetry, wrap `traced` to emit spans to OTLP exporter.

## Analytics
- DuckDB table `extractions` holds field-level info for SQL GROUP BY/HAVING anomaly detection.
- `reports/performance.md` summarizes periodic evaluation.
