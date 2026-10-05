CREATE TABLE quality_results AS
SELECT 'direct_rows_require_entity' AS check_name,COUNT(*) AS violations
FROM linkage_records WHERE link_basis='DIRECT_KEY' AND (entity_alias IS NULL OR trim(entity_alias)='')
UNION ALL SELECT 'publication_flag_domain',COUNT(*) FROM linkage_records WHERE publication_flag NOT IN (0,1)
UNION ALL SELECT 'workflow_status_nonempty',COUNT(*) FROM linkage_records WHERE workflow_status IS NULL OR trim(workflow_status)=''
UNION ALL SELECT 'no_orphan_entity_reference',COUNT(*) FROM linkage_records l LEFT JOIN entities e USING(entity_alias)
 WHERE l.entity_alias IS NOT NULL AND e.entity_alias IS NULL
UNION ALL SELECT 'ingestion_rows_reconcile',COUNT(*) FROM ingestion_runs WHERE input_rows<>loaded_records
UNION ALL SELECT 'entity_count_reconciles',COUNT(*) FROM ingestion_runs WHERE loaded_entities<>(SELECT COUNT(*) FROM entities)
UNION ALL SELECT 'record_ids_unique',COUNT(*)-COUNT(DISTINCT record_id) FROM linkage_records
UNION ALL SELECT 'dates_nonempty',COUNT(*) FROM linkage_records WHERE trim(available_date)='' OR trim(event_date)=''
UNION ALL SELECT 'direct_profile_nonempty',CASE WHEN (SELECT COUNT(*) FROM mart_direct_profile)>0 THEN 0 ELSE 1 END
UNION ALL SELECT 'process_only_branch_supported',CASE WHEN (SELECT COUNT(*) FROM linkage_records WHERE link_basis='PROCESS_ONLY')>0 THEN 0 ELSE 1 END;
