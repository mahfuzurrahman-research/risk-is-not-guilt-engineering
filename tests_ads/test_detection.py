import unittest
from copy import deepcopy

from ads_lab.contracts import validate_labels
from ads_lab.detection import apply_policy, choose_policy, score_record
from ads_lab.evaluation import evaluate
from ads_lab.features import extract_page
from ads_lab.fixtures import generate_corpus
from ads_lab.investigation import build_queue, campaign_links, incident_replay


class TestInvestigationBehavior(unittest.TestCase):
    def setUp(self):
        self.records, self.raw_labels, self.threats = generate_corpus(2)
        self.labels = validate_labels(self.raw_labels, self.records)
        self.scored = [score_record(record, self.threats) for record in self.records]
        self.policy = choose_policy(self.scored, self.labels)
        apply_policy(self.scored, self.policy)

    def scenario(self, name, split="holdout"):
        return [r for r in self.scored if r["split"] == split and self.labels[r["observation_id"]]["scenario"] == name]

    def test_benign_controls_are_not_flagged(self):
        for row in self.scored:
            if not self.labels[row["observation_id"]]["is_abuse"]:
                with self.subTest(case=self.labels[row["observation_id"]]["scenario"]):
                    self.assertFalse(row["review_flag"])

    def test_topic_credential_and_download_changes_are_review_candidates(self):
        for name in ("abuse_topic_cloaking", "abuse_credential_cloaking", "abuse_download_cloaking"):
            with self.subTest(scenario=name):
                self.assertTrue(all(r["review_flag"] for r in self.scenario(name)))

    def test_language_change_is_not_product_change(self):
        row = self.scenario("benign_localization")[0]
        self.assertTrue(row["content_change_baseline"])
        self.assertFalse(row["signals"]["topic_divergence"])

    def test_static_reference_does_not_claim_javascript_execution(self):
        row = self.scenario("abuse_js_reference")[0]
        self.assertTrue(row["signals"]["static_js_external"])
        self.assertFalse(row["review_flag"])
        self.assertTrue(all(p["javascript_executed"] is False for p in row["pages"].values()))

    def test_script_text_is_excluded_from_topic_extraction(self):
        page = extract_page('<h1>Clothing shirts</h1><script>var text="bank finance";</script>', "https://x.test/")
        self.assertEqual(page["topic_tags"], ["clothing"])

    def test_legitimate_sso_external_form_is_not_conclusive(self):
        row = self.scenario("benign_sso")[0]
        self.assertTrue(row["signals"]["external_form"])
        self.assertFalse(row["signals"]["credential_change"])
        self.assertFalse(row["review_flag"])

    def test_stale_and_future_indicators_are_excluded(self):
        for name, reason in (("benign_repaired_stale", "EXPIRED_INDICATOR"), ("abuse_delayed_feed", "NOT_YET_AVAILABLE")):
            row = self.scenario(name)[0]
            self.assertFalse(row["signals"]["known_threat"])
            self.assertEqual(row["threat_lookup"]["status"], "UNKNOWN_NO_CURRENT_MATCH")
            self.assertEqual(row["threat_lookup"]["excluded"][0]["reason"], reason)

    def test_policy_selection_ignores_holdout_outcomes(self):
        changed = deepcopy(self.labels)
        for row in self.scored:
            if row["split"] == "holdout":
                changed[row["observation_id"]]["is_abuse"] = not changed[row["observation_id"]]["is_abuse"]
        self.assertEqual(choose_policy(self.scored, self.labels), choose_policy(self.scored, changed))

    def test_unavailable_validation_labels_block_policy_selection(self):
        labels = deepcopy(self.labels)
        labels[self.scored[0]["observation_id"]]["available_at"] = "2026-02-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "before policy freeze"):
            choose_policy(self.scored, labels)

    def test_unmet_precision_target_disables_flags(self):
        labels = deepcopy(self.labels)
        for row in self.scored:
            if row["split"] == "validation":
                labels[row["observation_id"]]["is_abuse"] = row["risk_score"] == 0
        policy = choose_policy(self.scored, labels)
        self.assertFalse(policy["enabled"])
        self.assertFalse(any(r["review_flag"] for r in apply_policy(self.scored, policy)))
        self.assertEqual(build_queue(self.scored, 10), [])

    def test_queue_is_capacity_bounded_with_stable_ties(self):
        queue = build_queue(self.scored, 5)
        self.assertEqual(len(queue), 5)
        keys = [(-r["risk_score"], r["observation_id"]) for r in queue]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual([r["rank"] for r in queue], list(range(1, 6)))
        self.assertEqual(build_queue(self.scored, 0), [])
        with self.assertRaises(ValueError):
            build_queue(self.scored, True)

    def test_queue_excludes_outcomes_and_enforcement(self):
        for row in build_queue(self.scored, 10):
            self.assertNotIn("is_abuse", row)
            self.assertNotIn("scenario", row)
            self.assertEqual(row["review_status"], "PENDING_REVIEW")
            self.assertEqual(row["actor_attribution"], "UNRESOLVED")
            self.assertFalse(row["automatic_enforcement"])

    def test_shared_resources_do_not_establish_actor_identity(self):
        links = campaign_links(self.scored)
        self.assertTrue(any(r["link_reason"] == "SHARED_FORM_ENDPOINT" for r in links))
        self.assertTrue(any(r["link_reason"] == "SHARED_DOM_SKELETON" for r in links))
        self.assertFalse(any(r["actor_identity_established"] for r in links))
        self.assertTrue(any("identity-test" in r["evidence_value"] for r in links))

    def test_pending_labels_are_not_treated_as_negative(self):
        evaluation = evaluate(self.scored, self.labels, build_queue(self.scored, 6), 6)
        self.assertEqual(evaluation["pending_label_count"], 2)
        self.assertEqual(evaluation["policy"]["n"], evaluation["holdout_observations"] - 2)
        self.assertEqual(evaluation["scenario_metrics"]["abuse_js_reference"]["false_negative"], 2)

    def test_incident_repair_is_replayable_and_explicitly_simulated(self):
        replay = incident_replay(self.records, self.scored, self.threats, self.policy)
        self.assertFalse(replay["real_incident"])
        self.assertGreater(replay["before_score"], replay["after_score"])
        self.assertFalse(replay["after_review_flag"])
        rebuilt = apply_policy([score_record(replay["patched_record"], self.threats)], self.policy)[0]
        self.assertEqual(rebuilt["risk_score"], replay["after_score"])

    def test_no_flags_is_not_a_safe_verdict(self):
        row = self.scenario("benign_static")[0]
        self.assertEqual(row["decision_status"], "INSUFFICIENT_EVIDENCE_FOR_FLAG")
        self.assertFalse(row["probability_calibrated"])

    def test_label_maturity_changes_metrics_without_rescoring(self):
        before = deepcopy(self.scored)
        evaluation = evaluate(self.scored, self.labels, build_queue(self.scored, 6), 6)
        follow_up = evaluation["label_maturity_follow_up"]
        self.assertEqual(follow_up["matured_labels"], evaluation["holdout_observations"])
        self.assertEqual(follow_up["policy"]["false_negative"], 4)
        self.assertLess(follow_up["policy"]["recall"], evaluation["policy"]["recall"])
        self.assertEqual(before, self.scored)
