from __future__ import annotations

from html import escape


def build_report(evaluation: dict, queue: list[dict], sql_checks: dict, policy: dict) -> str:
    def esc(value):
        return escape(str(value), quote=True)
    def percent(value):
        return "undefined" if value is None else f"{100 * value:.1f}%"
    metrics = evaluation["policy"]
    cards = [("Held-out observations", evaluation["holdout_observations"]),
             ("Mature labels", evaluation["matured_labels"]),
             ("Pending labels", evaluation["pending_label_count"]),
             ("Flag precision", percent(metrics["precision"])),
             ("Flag recall", percent(metrics["recall"])),
             ("Benign false-positive rate", percent(metrics["false_positive_rate"]))]
    card_html = "".join(f'<article><small>{esc(name)}</small><strong>{esc(value)}</strong></article>' for name, value in cards)
    rows = "".join(f"<tr><td>{r['rank']}</td><td>{esc(r['observation_id'])}</td><td>{r['risk_score']}</td>"
                   f"<td>{esc(', '.join(r['reason_codes']))}</td><td>PENDING_REVIEW</td></tr>" for r in queue)
    scenarios = "".join(f"<tr><td>{esc(name)}</td><td>{m['n']}</td><td>{m['false_positive']}</td>"
                        f"<td>{m['false_negative']}</td></tr>" for name, m in evaluation["scenario_metrics"].items())
    baselines = "".join(f"<tr><td>{esc(name)}</td><td>{percent(m['precision'])}</td>"
                        f"<td>{percent(m['recall'])}</td><td>{percent(m['false_positive_rate'])}</td></tr>"
                        for name, m in evaluation["baselines"].items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Ads destination investigation lab</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1f4f7;color:#172c3a;font:15px/1.55 system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:36px 24px}}h1{{font-size:32px;line-height:1.2}}h2{{font-size:22px}}
.scope{{padding:18px;border-left:4px solid #ac6a18;background:#fff5df}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0}}
article{{background:white;border:1px solid #dce4e9;border-radius:8px;padding:18px}}small{{display:block}}strong{{display:block;font-size:25px;margin-top:8px}}
section{{background:white;border-radius:8px;padding:22px;margin:20px 0;overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid #e3e9ed}}th{{background:#edf3f6}}code{{font-size:12px;overflow-wrap:anywhere}}
a{{color:#17608a}}footer{{color:#4d6270}}.pass{{color:#20653e}}
</style></head><body><main>
<p>MAHFUZUR RAHMAN · RISK IS NOT GUILT ENGINEERING</p><h1>Ads destination investigation lab</h1>
<div class="scope">Controlled fixtures only. No real Google Ads traffic or verified policy violations.
Scores prioritize verification. No automatic enforcement or established actor attribution.</div>
<div class="grid">{card_html}</div>
<section><h2>Frozen review policy</h2><p>Available at {esc(policy['available_at'])}. Validation-selected threshold:
{esc(policy['threshold'])}. Capacity: {evaluation['queue']['capacity']}. SQL reconstruction:
<span class="pass">{sql_checks['independent_sql_gates']} checks passed</span>.</p>
<p>Queue recall: {percent(evaluation['queue']['recall'])}; deferred candidates:
{evaluation['queue']['capacity_deferred_candidates']}. Pending outcomes are excluded from metrics and remain pending.</p></section>
<section><h2>Later label-maturity check</h2><p>At {esc(evaluation['label_maturity_follow_up']['evaluation_at'])},
{evaluation['label_maturity_follow_up']['matured_labels']} labels are mature. Original scores, threshold and queue remain unchanged.
Flag recall becomes {percent(evaluation['label_maturity_follow_up']['policy']['recall'])};
queue recall becomes {percent(evaluation['label_maturity_follow_up']['queue']['recall'])}.
Later indicator knowledge is not retroactively inserted into earlier decisions.</p></section>
<section><h2>Comparison baselines</h2><table><thead><tr><th>Baseline</th><th>Precision</th><th>Recall</th><th>Benign false-positive rate</th></tr></thead><tbody>{baselines}</tbody></table></section>
<section><h2>Evidence review queue</h2><table><thead><tr><th>Rank</th><th>Observation</th><th>Score</th><th>Recorded reasons</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>
<p>Full captures, hashes, alternative explanations and verification steps are in
<a href="case_reports.md">case_reports.md</a> and <a href="corpus.json">corpus.json</a>.</p></section>
<section><h2>Failures and benign controls</h2><table><thead><tr><th>Scenario</th><th>Mature labels</th><th>False positives</th><th>False negatives</th></tr></thead><tbody>{scenarios}</tbody></table>
<p>{esc(evaluation['generalization_limit'])}</p><p>Static JavaScript references are inspected without execution.
Language, A/B, consent, SSO and tracking cases constrain interpretation; HTML differences alone do not establish cloaking.</p></section>
<footer>Evaluation cutoff: {esc(evaluation['evaluation_at'])}. Replay and source/artifact hashes are recorded in the run receipt.</footer>
</main></body></html>"""
