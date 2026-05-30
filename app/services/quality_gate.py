from app.core.config_loader import load_yaml_config
from app.schemas.content import OpportunityScore, QualityGateResult


def run_quality_gate(topic: str, score: OpportunityScore) -> QualityGateResult:
    thresholds = load_yaml_config("scoring.yaml")["scoring"]["risk_thresholds"]
    notes: list[str] = []

    low_effort = "medium" if score.originality_potential < thresholds["low_effort_ai_review"] else "low"
    unsupported = "medium" if score.curiosity_gap > thresholds["unsupported_claim_review"] else "low"
    misleading = "medium" if score.emotional_pull > 70 else "low"
    policy = "medium" if score.policy_risk >= 45 else "low"
    monetization = "medium" if score.policy_risk >= 40 or score.saturation_risk >= 70 else "low"

    if unsupported == "medium":
        notes.append("Research brief must verify trend cause before scripting claims as fact.")
    if misleading == "medium":
        notes.append("Titles should stay curiosity-led without overstating certainty.")
    if policy == "medium":
        notes.append("Manual review required for sensitive or private-subject framing.")

    if score.policy_risk >= thresholds["policy_risk_reject"]:
        final_status = "rejected"
    elif notes or score.final_score < 74:
        final_status = "needs_review"
    else:
        final_status = "approved"

    return QualityGateResult(
        repetitive_content_risk="low",
        low_effort_ai_content_risk=low_effort,
        unsupported_claim_risk=unsupported,
        misleading_title_risk=misleading,
        copyright_reused_content_risk="low",
        sensitive_topic_risk=policy,
        monetization_risk=monetization,
        ai_disclosure_needed=True,
        final_status=final_status,
        notes=notes or [f"{topic} is suitable for review-first planning with source verification."],
    )
