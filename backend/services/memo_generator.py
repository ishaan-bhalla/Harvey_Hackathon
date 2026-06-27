import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import datetime

def generate_memo(result: dict, output_path: str = "outputs/case_risk_memo.html") -> str:
    os.makedirs("outputs", exist_ok=True)

    readiness = result["trial_readiness"]
    score = result["trial_readiness_score"]

    readiness_color = {
        "STRONG": "#16a34a",
        "MODERATE": "#d97706",
        "VULNERABLE": "#dc2626"
    }.get(readiness, "#6b7280")

    supported = [r for r in result["matrix"] if len(r["supporting"]) > 0]
    gaps = result["gaps"]
    contradictions = result["contradictions"]

    supported_rows = ""
    for row in supported:
        witnesses = ", ".join([s["witness"] for s in row["supporting"]])
        passage = row["supporting"][0].get("relevant_passage", "") or ""
        passage_html = f'<div class="passage">"{passage[:200]}..."</div>' if passage else ""
        supported_rows += f"""
        <div class="allegation-card supported">
            <div class="allegation-header">
                <span class="badge badge-supported">SUPPORTED</span>
                <span class="topic">{row["topic"].replace("_", " ").upper()}</span>
            </div>
            <div class="allegation-text">{row["allegation"]}</div>
            {passage_html}
            <div class="witnesses">Corroborated by: {witnesses}</div>
        </div>"""

    gap_rows = ""
    for row in gaps:
        gap_rows += f"""
        <div class="allegation-card gap">
            <div class="allegation-header">
                <span class="badge badge-gap">EVIDENTIAL GAP</span>
                <span class="topic">{row["topic"].replace("_", " ").upper()}</span>
            </div>
            <div class="allegation-text">{row["allegation"]}</div>
            <div class="action">⚠ Action required: obtain further witness statement or documentary evidence</div>
        </div>"""

    contradiction_rows = ""
    for row in contradictions:
        for c in row["contradicting"]:
            passage = c.get("relevant_passage", "") or ""
            contradiction_rows += f"""
            <div class="allegation-card contradicted">
                <div class="allegation-header">
                    <span class="badge badge-contradicted">CONTRADICTED</span>
                    <span class="topic">{row["topic"].replace("_", " ").upper()}</span>
                </div>
                <div class="allegation-text">{row["allegation"]}</div>
                <div class="witnesses">Contradicted by: {c["witness"]}</div>
                <div class="passage">"{passage[:200]}"</div>
                <div class="action">⚠ Highest litigation risk — requires immediate review</div>
            </div>"""

    if not contradiction_rows:
        contradiction_rows = '<div class="none-found">No contradictions identified in the available evidence.</div>'

    witnesses_list = ", ".join(result["documents_analysed"])
    date = datetime.now().strftime("%B %d, %Y")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Case Risk Assessment — Post Office Horizon IT Inquiry</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Georgia', serif; background: #f8f7f4; color: #1a1a1a; padding: 40px; }}
  .memo {{ max-width: 900px; margin: 0 auto; background: white; padding: 60px; box-shadow: 0 2px 20px rgba(0,0,0,0.08); }}
  .header {{ border-bottom: 3px solid #1a1a1a; padding-bottom: 24px; margin-bottom: 32px; }}
  .firm-name {{ font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #6b7280; margin-bottom: 16px; }}
  h1 {{ font-size: 24px; font-weight: normal; letter-spacing: 0.5px; margin-bottom: 8px; }}
  .meta {{ font-size: 13px; color: #6b7280; line-height: 1.8; }}
  .readiness-banner {{ background: {readiness_color}; color: white; padding: 20px 28px; margin: 32px 0; display: flex; justify-content: space-between; align-items: center; }}
  .readiness-label {{ font-size: 11px; letter-spacing: 2px; text-transform: uppercase; opacity: 0.8; }}
  .readiness-value {{ font-size: 28px; font-weight: bold; letter-spacing: 1px; }}
  .readiness-score {{ font-size: 18px; opacity: 0.9; }}
  .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: #e5e7eb; margin: 32px 0; }}
  .stat {{ background: white; padding: 20px; text-align: center; }}
  .stat-number {{ font-size: 32px; font-weight: bold; color: #1a1a1a; }}
  .stat-label {{ font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: #6b7280; margin-top: 4px; }}
  h2 {{ font-size: 13px; letter-spacing: 2px; text-transform: uppercase; color: #6b7280; margin: 40px 0 16px; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb; }}
  .allegation-card {{ padding: 20px; margin-bottom: 12px; border-left: 4px solid; }}
  .allegation-card.supported {{ background: #f0fdf4; border-color: #16a34a; }}
  .allegation-card.gap {{ background: #fffbeb; border-color: #d97706; }}
  .allegation-card.contradicted {{ background: #fef2f2; border-color: #dc2626; }}
  .allegation-header {{ display: flex; gap: 12px; align-items: center; margin-bottom: 10px; }}
  .badge {{ font-size: 10px; letter-spacing: 1px; text-transform: uppercase; padding: 3px 8px; font-weight: bold; }}
  .badge-supported {{ background: #16a34a; color: white; }}
  .badge-gap {{ background: #d97706; color: white; }}
  .badge-contradicted {{ background: #dc2626; color: white; }}
  .topic {{ font-size: 10px; letter-spacing: 1px; text-transform: uppercase; color: #6b7280; }}
  .allegation-text {{ font-size: 14px; line-height: 1.6; margin-bottom: 8px; }}
  .passage {{ font-size: 13px; color: #4b5563; font-style: italic; margin: 8px 0; padding: 8px 12px; background: rgba(0,0,0,0.03); border-left: 2px solid #d1d5db; }}
  .witnesses {{ font-size: 12px; color: #6b7280; margin-top: 8px; }}
  .action {{ font-size: 12px; color: #92400e; margin-top: 8px; font-weight: bold; }}
  .none-found {{ color: #6b7280; font-style: italic; font-size: 14px; padding: 16px 0; }}
  .footer {{ margin-top: 48px; padding-top: 24px; border-top: 1px solid #e5e7eb; font-size: 11px; color: #9ca3af; line-height: 1.8; }}
</style>
</head>
<body>
<div class="memo">
  <div class="header">
    <div class="firm-name">Pleading-to-Proof AI System</div>
    <h1>Case Risk Assessment<br>Post Office Horizon IT Inquiry</h1>
    <div class="meta">
      Date: {date}<br>
      Witnesses analysed: {witnesses_list}<br>
      Total allegations assessed: {result["total_allegations"]}
    </div>
  </div>

  <div class="readiness-banner">
    <div>
      <div class="readiness-label">Overall Trial Readiness</div>
      <div class="readiness-value">{readiness}</div>
    </div>
    <div class="readiness-score">{score}% of allegations evidenced</div>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-number" style="color:#16a34a">{len(supported)}</div>
      <div class="stat-label">Supported Allegations</div>
    </div>
    <div class="stat">
      <div class="stat-number" style="color:#d97706">{len(gaps)}</div>
      <div class="stat-label">Evidential Gaps</div>
    </div>
    <div class="stat">
      <div class="stat-number" style="color:#dc2626">{len(contradictions)}</div>
      <div class="stat-label">Contradictions</div>
    </div>
  </div>

  <h2>Supported Allegations</h2>
  {supported_rows}

  <h2>Evidential Gaps — Action Required</h2>
  {gap_rows}

  <h2>Contradictions — Highest Litigation Risk</h2>
  {contradiction_rows}

  <div class="footer">
    This assessment was generated by the Pleading-to-Proof AI system using Claude (Anthropic).<br>
    All classifications are AI-assisted and must be verified by a qualified lawyer before reliance.<br>
    Source documents: Post Office Horizon IT Inquiry witness statements.
  </div>
</div>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    print(f"Memo saved to: {output_path}")
    return output_path
