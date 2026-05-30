from app.providers.trends.base import TrendProvider, make_trend_item
from app.schemas.content import TrendItem


class ManualSeedProvider(TrendProvider):
    name = "manual_seed"

    def fetch(self) -> list[TrendItem]:
        seeds = [
            "AI search replacing blue links",
            "The resale economy for everyday electronics",
            "Why old internet aesthetics are back",
            "Private space companies racing for lunar infrastructure",
            "The hidden logistics of same-day delivery",
            "Unexpected tourism spikes in small countries",
        ]
        return [
            make_trend_item(
                source=self.name,
                title=seed,
                source_score=55,
                search_terms=[seed],
                metadata={"fallback": True, "editorial_seed": True},
            )
            for seed in seeds
        ]

