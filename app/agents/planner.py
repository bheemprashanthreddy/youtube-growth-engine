from app.providers.base import LLMProvider
from app.schemas.content import ContentPlan, OpportunityScore
from app.services.quality_gate import run_quality_gate


class ContentPlanner:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def build_plan(self, topic: dict[str, object], score: OpportunityScore) -> ContentPlan:
        name = str(topic["topic"])
        pillar = str(topic["pillar"])
        trigger = str(topic["curiosity_trigger"])
        trend_reason = str(topic["trend_reason"])
        target_viewer = str(topic["target_viewer"])
        quality_gate = run_quality_gate(name, score)

        return ContentPlan(
            topic=name,
            pillar=pillar,
            trend_reason=trend_reason,
            viewer_curiosity_trigger=trigger,
            target_viewer=target_viewer,
            short_video_angle=f"Explain the one surprising reason {name.lower()} is suddenly everywhere.",
            long_video_angle=f"Map the hidden system behind {name.lower()}, why it accelerated now, and what changes next.",
            research_brief=self._research_brief(name, pillar, trend_reason),
            hook_options=[
                f"{name} looks random, but there is a reason it is suddenly spiking.",
                f"Most people noticed {name.lower()}. Fewer noticed what changed behind it.",
                f"The surprising part of {name.lower()} is not the trend. It is the timing.",
            ],
            shorts_script=self._shorts_script(name, trigger, trend_reason),
            long_form_outline=self._long_form_outline(name),
            title_options=[
                f"Why {name} Is Suddenly Everywhere",
                f"The Hidden Reason Behind {name}",
                f"What Everyone Is Missing About {name}",
                f"{name}: The Trend That Changed Faster Than Expected",
                f"The System Behind {name}, Explained",
            ],
            description=(
                f"CuriousSignal breaks down {name}: why people are searching for it, "
                "what changed recently, and what viewers should verify before accepting the hype."
            ),
            hashtags=["#CuriousSignal", "#Trends", "#Explained", "#InternetCulture", "#Technology"],
            thumbnail_text_ideas=["WHY NOW?", "HIDDEN SIGNAL", "SUDDEN SPIKE"],
            pinned_comment_idea="What trend should CuriousSignal investigate next?",
            ai_disclosure_recommendation=(
                "Disclose AI assistance if synthetic narration, generated visuals, or materially altered media are used later."
            ),
            score=score,
            quality_gate=quality_gate,
        )

    def _research_brief(self, name: str, pillar: str, trend_reason: str) -> str:
        prompt = f"Create a source-first research brief for {name} in pillar {pillar}: {trend_reason}"
        draft = self.provider.generate_text(prompt, purpose="research_brief")
        return (
            f"Research objective: verify why {name} is gaining attention and separate signal from hype. "
            f"Start with primary data, credible news coverage, search interest, and counterexamples. "
            f"Draft guidance: {draft}"
        )

    def _shorts_script(self, name: str, trigger: str, trend_reason: str) -> str:
        return (
            f"Hook: {name} did not become a trend by accident.\n"
            f"Context: People are searching because {trend_reason.lower()}\n"
            f"Turn: The real curiosity trigger is {trigger.lower()}.\n"
            "Proof path: Compare the search spike with product launches, platform behavior, news events, and creator coverage.\n"
            "Payoff: The useful question is not whether the trend is big. It is what changed right before everyone noticed.\n"
            "Close: CuriousSignal tracks the hidden signals behind sudden trends."
        )

    def _long_form_outline(self, name: str) -> list[str]:
        return [
            "Cold open: the sudden search spike and why it feels confusing",
            "What changed: timeline of the visible trigger",
            "Hidden system: incentives, platforms, money, or science underneath",
            "Why now: the acceleration point that made the topic mainstream",
            "What people get wrong: common misleading interpretation",
            "Evidence check: claims that need primary-source verification",
            "Future consequence: what could happen if the pattern continues",
            "Closing: what this trend reveals about internet behavior",
        ]
