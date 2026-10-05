PRAGMA foreign_keys=ON;
CREATE TABLE entities(entity_alias TEXT PRIMARY KEY CHECK(length(trim(entity_alias))>0));
CREATE TABLE linkage_records(
 record_id TEXT PRIMARY KEY,
 entity_alias TEXT,
 link_basis TEXT NOT NULL CHECK(link_basis IN ('DIRECT_KEY','PROCESS_ONLY')),
 publication_flag INTEGER NOT NULL CHECK(publication_flag IN (0,1)),
 workflow_status TEXT NOT NULL CHECK(length(trim(workflow_status))>0),
 available_date TEXT NOT NULL,
 event_date TEXT NOT NULL,
 FOREIGN KEY(entity_alias) REFERENCES entities(entity_alias)
);
CREATE TABLE ingestion_runs(
 run_id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_file TEXT NOT NULL,
 source_sha256 TEXT NOT NULL,
 input_rows INTEGER NOT NULL,
 loaded_entities INTEGER NOT NULL,
 loaded_records INTEGER NOT NULL
);
CREATE INDEX idx_linkage_basis_entity ON linkage_records(link_basis,entity_alias);
CREATE INDEX idx_linkage_publication_status ON linkage_records(publication_flag,workflow_status);
