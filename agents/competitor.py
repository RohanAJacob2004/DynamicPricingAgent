"""
Competitor Pricing Agent: External signal.
Recommends pricing based on competitor prices.
Example agent for folder-based organization.
"""
from typing import Dict, Any
from agents.base import BaseAgent, AgentRecommendation


class CompetitorAgent(BaseAgent):
    """
    Competitor Pricing Agent: External signal focus.
    Recommends pricing based on competitor market data.
    Uses deterministic Python calculations.
    """

    def __init__(self, agent_id: str = "competitor_agent_v1"):
        super().__init__(agent_id)

    def analyze(self, product_data: Dict[str, Any], system_context: Dict[str, Any]) -> AgentRecommendation:
        """
        Competitor pricing focused recommendation.
        """
        sku = product_data['sku']
        our_price = product_data['current_price']

        # In real implementation, fetch from API or cache
        competitor_data = system_context.get('competitor_prices', {})
        competitor_avg = competitor_data.get(sku, our_price)

        if competitor_avg == 0:
            # No competitor data available
            return AgentRecommendation(
                agent_id=self.agent_id,
                sku=sku,
                confidence=0.3,
                recommendation={"suggested_modifier": 0.0},
                rationale="Insufficient competitor pricing data."
            )

        # Calculate gap
        gap_percent = (our_price - competitor_avg) / competitor_avg

        # Pricing logic
        if gap_percent > 0.20:  # We're 20%+ higher
            modifier = -0.15
            confidence = 0.90
        elif gap_percent > 0.10:  # We're 10-20% higher
            modifier = -0.08
            confidence = 0.85
        elif gap_percent < -0.15:  # We're 15%+ lower
            modifier = 0.10
            confidence = 0.85
        else:
            modifier = 0.0
            confidence = 0.60

        rationale = (
            f"Competitor average: ${competitor_avg:.2f}, our price: ${our_price:.2f}, "
            f"gap: {gap_percent:+.1%}. Recommend {modifier:+.1%} to maintain competitiveness."
        )

        return AgentRecommendation(
            agent_id=self.agent_id,
            sku=sku,
            confidence=confidence,
            recommendation={
                "suggested_modifier": modifier
            },
            rationale=rationale
        )
