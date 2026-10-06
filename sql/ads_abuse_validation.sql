PRAGMA foreign_keys = ON;

CREATE TABLE observation_base (
    observation_id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('validation','holdout')),
    decision_at TEXT NOT NULL, ad_topics TEXT NOT NULL
);
CREATE TABLE captures (
    observation_id TEXT REFERENCES observation_base(observation_id), context TEXT NOT NULL CHECK (context IN ('reviewer','desktop','mobile')),
    final_url TEXT NOT NULL, final_host TEXT NOT NULL, topic_tags TEXT NOT NULL,
    password_input INTEGER NOT NULL CHECK (password_input IN (0,1)),
    external_form INTEGER NOT NULL CHECK (external_form IN (0,1)),
    download_count INTEGER NOT NULL, static_js_external INTEGER NOT NULL,
    hop_count INTEGER NOT NULL, body_sha256 TEXT NOT NULL, template_sha256 TEXT NOT NULL,
    PRIMARY KEY (observation_id, context)
);
CREATE TABLE candidate_urls (
    observation_id TEXT REFERENCES observation_base(observation_id), url TEXT NOT NULL,
    PRIMARY KEY (observation_id, url)
);
CREATE TABLE threat_indicators (
    url TEXT PRIMARY KEY, available_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE reported_scores (
    observation_id TEXT PRIMARY KEY REFERENCES observation_base(observation_id),
    signals TEXT NOT NULL, risk_score INTEGER NOT NULL, review_flag INTEGER NOT NULL,
    content_change_baseline INTEGER NOT NULL
);
CREATE TABLE labels (
    observation_id TEXT PRIMARY KEY REFERENCES observation_base(observation_id),
    is_abuse INTEGER NOT NULL CHECK (is_abuse IN (0,1)), available_at TEXT NOT NULL
);
CREATE TABLE reported_queue (
    rank INTEGER PRIMARY KEY, observation_id TEXT UNIQUE REFERENCES observation_base(observation_id),
    risk_score INTEGER NOT NULL, status TEXT NOT NULL, automatic_enforcement INTEGER NOT NULL
);
CREATE TABLE policy (enabled INTEGER NOT NULL, threshold INTEGER, available_at TEXT NOT NULL, capacity INTEGER NOT NULL);
CREATE TABLE eval_cutoff (evaluation_at TEXT NOT NULL);

-- Derive every signal from capture primitives and dated indicators, without
-- consuming the Python signal values, scores, flags or retrospective labels.
CREATE VIEW independently_derived_signals AS
SELECT b.observation_id, b.campaign_id, b.split, b.decision_at,
  MAX(CASE WHEN json_array_length(rv.topic_tags)>0 AND json_array_length(u.topic_tags)>0
    AND NOT EXISTS (SELECT 1 FROM json_each(rv.topic_tags) a JOIN json_each(u.topic_tags) c ON a.value=c.value)
    THEN 1 ELSE 0 END) AS topic_divergence,
  MAX(CASE WHEN json_array_length(b.ad_topics)>0 AND json_array_length(u.topic_tags)>0
    AND NOT EXISTS (SELECT 1 FROM json_each(b.ad_topics) a JOIN json_each(u.topic_tags) c ON a.value=c.value)
    THEN 1 ELSE 0 END) AS ad_topic_mismatch,
  MAX(CASE WHEN u.password_input=1 AND u.external_form=1 AND rv.password_input=0 THEN 1 ELSE 0 END) AS credential_change,
  MAX(CASE WHEN u.download_count>0 AND rv.download_count=0 THEN 1 ELSE 0 END) AS download_change,
  EXISTS (SELECT 1 FROM candidate_urls cu JOIN threat_indicators t ON cu.url=t.url
    WHERE cu.observation_id=b.observation_id AND t.available_at<=b.decision_at AND b.decision_at<t.expires_at) AS known_threat,
  MAX(CASE WHEN u.final_host<>rv.final_host THEN 1 ELSE 0 END) AS destination_change,
  MAX(CASE WHEN u.hop_count>2 THEN 1 ELSE 0 END) AS long_redirect,
  MAX(u.static_js_external) AS static_js_external,
  MAX(u.external_form) AS external_form,
  MAX(CASE WHEN u.body_sha256<>rv.body_sha256 OR u.final_url<>rv.final_url THEN 1 ELSE 0 END) AS content_change_baseline
FROM observation_base b
JOIN captures rv ON rv.observation_id=b.observation_id AND rv.context='reviewer'
JOIN captures u ON u.observation_id=b.observation_id AND u.context IN ('desktop','mobile')
GROUP BY b.observation_id;

CREATE VIEW independently_derived_scores AS
SELECT s.*,
  4*topic_divergence + 3*ad_topic_mismatch + 3*credential_change + 3*download_change +
  6*known_threat + destination_change + long_redirect + static_js_external + external_form AS risk_score
FROM independently_derived_signals s;

CREATE VIEW independently_derived_flags AS
SELECT s.*, CASE WHEN p.enabled=1 AND s.risk_score>=p.threshold THEN 1 ELSE 0 END AS review_flag
FROM independently_derived_scores s CROSS JOIN policy p;

CREATE VIEW independently_derived_queue AS
SELECT ROW_NUMBER() OVER (ORDER BY risk_score DESC, observation_id) AS rank, observation_id, risk_score
FROM independently_derived_flags WHERE split='holdout' AND review_flag=1
ORDER BY risk_score DESC, observation_id LIMIT (SELECT capacity FROM policy);

CREATE VIEW matured_holdout AS
SELECT f.*, l.is_abuse FROM independently_derived_flags f JOIN labels l USING (observation_id)
CROSS JOIN eval_cutoff e WHERE f.split='holdout' AND f.decision_at<=e.evaluation_at AND l.available_at<=e.evaluation_at;

CREATE VIEW independent_confusion AS
SELECT COUNT(*) AS n,
  SUM(CASE WHEN is_abuse=1 AND review_flag=1 THEN 1 ELSE 0 END) AS true_positive,
  SUM(CASE WHEN is_abuse=0 AND review_flag=1 THEN 1 ELSE 0 END) AS false_positive,
  SUM(CASE WHEN is_abuse=0 AND review_flag=0 THEN 1 ELSE 0 END) AS true_negative,
  SUM(CASE WHEN is_abuse=1 AND review_flag=0 THEN 1 ELSE 0 END) AS false_negative
FROM matured_holdout;
