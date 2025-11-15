# API Reference

## POST /extract
- **Description:** Upload a PDF (multipart/form-data, field `file`).
- **Response:**
```json
{
  "request_id": "uuid",
  "documents": [
    {
      "doc_type": "invoice",
      "fields": {
        "invoice_number": {"value": "INV-10023", "confidence": 0.97, "valid": true},
        "total_amount": {"value": 1299.34, "confidence": 0.93, "valid": true}
      },
      "validation_summary": {
        "failed": [],
        "warnings": []
      }
    }
  ],
  "metrics": {
    "processing_time_ms": 2310
  }
}
```
- **Errors:** 4XX for validation, 5XX for processing failures. JSON body includes `error_code`, `message`, `details`.

## GET /health
Returns `{ "status": "ok", "uptime_s": 123.4 }`.

## GET /metrics
Prometheus plaintext metrics (latency histograms, counters for OCR/layout/validation).
