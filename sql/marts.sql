CREATE VIEW mart_direct_profile AS
SELECT entity_alias,
 MAX(publication_flag) AS has_published,
 MAX(CASE WHEN publication_flag=0 THEN 1 ELSE 0 END) AS has_non_published,
 COUNT(*) AS direct_rows
FROM linkage_records WHERE link_basis='DIRECT_KEY' GROUP BY entity_alias;

CREATE VIEW mart_linkage_summary AS
SELECT
 (SELECT COUNT(*) FROM linkage_records) AS total_rows,
 (SELECT COUNT(*) FROM linkage_records WHERE link_basis='DIRECT_KEY') AS direct_rows,
 (SELECT COUNT(*) FROM linkage_records WHERE link_basis='PROCESS_ONLY') AS process_only_rows,
 (SELECT COUNT(*) FROM entities) AS unique_direct_entities,
 (SELECT COUNT(*) FROM mart_direct_profile WHERE has_published=1) AS any_published_entities,
 (SELECT COUNT(*) FROM mart_direct_profile WHERE has_published=1 AND has_non_published=0) AS all_published_entities,
 (SELECT COUNT(*) FROM mart_direct_profile WHERE has_published=1 AND has_non_published=1) AS mixed_publication_entities;

CREATE VIEW mart_ingestion_health AS
SELECT source_file,input_rows,loaded_records,loaded_entities,
 CASE WHEN input_rows=loaded_records THEN 'PASS' ELSE 'FAIL' END AS row_reconciliation
FROM ingestion_runs;
