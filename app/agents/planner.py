from app.providers.base import LLMProvider
from app.providers.factory import safe_generate_text
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
            short_video_angle=f"Show the visible change, the hidden system underneath, and the concrete consequence behind {name.lower()}.",
            long_video_angle=f"Map the incentives, timeline, winners, losers, and verification gaps behind {name.lower()}.",
            research_brief=self._research_brief(name, pillar, trend_reason),
            hook_options=[
                f"{name} is not just a trend. It is a signal that something underneath changed.",
                f"People noticed {name.lower()}, but the important part is who benefits from the shift.",
                f"The strange part of {name.lower()} is the timing, not the headline.",
            ],
            shorts_script=self._shorts_script(name, trigger, trend_reason),
            long_form_outline=self._long_form_outline(name),
            title_options=[
                self._clean_title(name),
                f"The Hidden Reason Behind {name}",
                f"What Everyone Is Missing About {name}",
                f"{name}: The Shift Happening Underneath",
                f"The System Behind {name}, Explained",
            ],
            description=(
                f"CuriousSignal breaks down {name}: why people are searching for it, "
                "what changed recently, and what viewers should verify before accepting the hype."
            ),
            hashtags=["#CuriousSignal", "#Trends", "#Explained", "#InternetCulture", "#Technology"],
            thumbnail_text_ideas=self._thumbnail_ideas(name),
            pinned_comment_idea="What trend should CuriousSignal investigate next?",
            ai_disclosure_recommendation=(
                "Disclose AI assistance if synthetic narration, generated visuals, or materially altered media are used later."
            ),
            score=score,
            quality_gate=quality_gate,
        )

    def _research_brief(self, name: str, pillar: str, trend_reason: str) -> str:
        prompt = (
            f"Create a source-first research brief for a CuriousSignal explainer.\n"
            f"Topic: {name}\nPillar: {pillar}\nTrend reason: {trend_reason}\n"
            "Include: what must be verified, likely primary sources, counterarguments, concrete examples, "
            "and claims to avoid unless sourced. Keep it concise and editorially cautious."
        )
        fallback = (
            f"Verify why {name} is gaining attention, what changed recently, who benefits, and which claims need primary-source support. "
            "Check search interest, platform behavior, product releases, credible reporting, and counterexamples before scripting."
        )
        draft = safe_generate_text(self.provider, prompt, purpose="research_brief", fallback=fallback)
        return (
            f"Research objective: verify why {name} is gaining attention and separate signal from hype. "
            f"Start with primary data, credible news coverage, search interest, and counterexamples. "
            f"Draft guidance: {draft}"
        )

    def _shorts_script(self, name: str, trigger: str, trend_reason: str) -> str:
        fallback = (
            f"0-3 sec hook: {name} is not just getting attention. It points to a bigger shift.\n"
            f"3-8 sec curiosity gap: People are searching because {trend_reason.lower()}, but the visible trend is only the surface.\n"
            "Concrete example: Watch where the old habit gets replaced by a faster shortcut, a new platform default, or a changed incentive.\n"
            f"Hidden system insight: The real signal is {trigger.lower()}, because it changes who gets attention, money, or trust.\n"
            "Payoff: When a trend spikes this fast, the useful question is what changed right before everyone noticed.\n"
            "Soft CTA: CuriousSignal tracks the hidden systems behind sudden searches."
        )
        prompt = (
            f"Write a 45-60 second CuriousSignal Shorts script for: {name}\n"
            f"Curiosity trigger: {trigger}\nTrend reason: {trend_reason}\n"
            "Use this structure exactly: 0-3 sec hook, 3-8 sec curiosity gap, concrete example, hidden system insight, payoff, soft CTA. "
            "Avoid generic hype, unsupported facts, and vague lines. Make each beat visual and specific."
        )
        return safe_generate_text(self.provider, prompt, purpose="shorts_script", fallback=fallback)

    def _long_form_outline(self, name: str) -> list[str]:
        return [
            "Cold open: the visible behavior shift and the question it raises",
            "Timeline: what changed before the search spike",
            "The hidden system: incentives, platforms, money, or science underneath",
            "Concrete example: one everyday moment where the change becomes obvious",
            "Who benefits: the companies, creators, users, or institutions gaining leverage",
            "Who loses: the old habit, old gatekeeper, or old business model under pressure",
            "What people get wrong: the tempting but incomplete explanation",
            "Evidence check: claims that need primary-source verification",
            "Future consequence: what changes if the pattern continues",
            "Closing: what this trend reveals about how attention moves",
        ]

    def _clean_title(self, name: str) -> str:
        lowered = name.lower()
        if lowered.startswith(("why ", "how ", "what ", "the ")):
            return name
        return f"Why {name} Is Changing Faster Than People Realize"

    def _thumbnail_ideas(self, name: str) -> list[str]:
        text = name.lower()
        if "ai" in text and "search" in text:
            return ["SEARCH JUST SHIFTED", "LINKS ARE DISAPPEARING", "AI ANSWERS WON"]
        if "gold" in text:
            return ["WHY GOLD SPIKED", "MONEY GOT NERVOUS", "SAFE HAVEN SIGNAL"]
        if "delivery" in text:
            return ["SAME DAY MACHINE", "DELIVERY GOT FASTER", "HIDDEN LOGISTICS"]
        return ["WHAT CHANGED?", "THE HIDDEN SHIFT", "FOLLOW THE SIGNAL"]
