# Data Quality

The SQL quality layer checks direct-key entity integrity, publication-flag domain, nonempty workflow state, foreign-key validity, ingestion reconciliation, entity reconciliation, record-ID uniqueness, date completeness, analytical-profile construction, and explicit support for process-only records.

Any nonzero required failure blocks the pipeline.
