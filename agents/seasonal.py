"""
Seasonal Trends Agent: External signal.
Recommends pricing based on seasonal demand patterns.
Example agent for folder-based organization.
"""
from typing import Dict, Any
from agents.base import BaseAgent, AgentRecommendation


class SeasonalAgent(BaseAgent):
    """
    Seasonal Trends Agent: External signal focus.
    Recommends pricing adjustments based on seasonal demand patterns.
    Uses deterministic Python calculations.
    """

    def __init__(self, agent_id: str = "seasonal_agent_v1"):
        super().__init__(agent_id)

    def analyze(self, product_data: Dict[str, Any], system_context: Dict[str, Any]) -> AgentRecommendation:
        """
        Seasonal-focused pricing recommendation.
        """
        sku = product_data['sku']
        current_sales_velocity = product_data['sales_velocity_7d']

        # Seasonal multiplier (could come from external data, historical averages, calendar)
        month = system_context.get('current_month', 6)  # 1-12

        # Example: Q4 (months 10-12) has +40% seasonal boost
        seasonal_boost = 1.0
        if month >= 10:
            seasonal_boost = 1.4
        elif month == 12:
            seasonal_boost = 1.6  # Extra boost for holidays

        # Calculate expected demand
        baseline_velocity = 50.0  # Your historical baseline
        expected_velocity = baseline_velocity * seasonal_boost

        # If actual velocity is behind seasonal expectation, boost sales with discount
        if current_sales_velocity < expected_velocity * 0.8:
            modifier = -0.12  # Discount to stimulate demand
            confidence = 0.88
        else:
            modifier = 0.0
            confidence = 0.65

        rationale = (
            f"Seasonal adjustment for month {month}: expected velocity is {expected_velocity:.1f}. "
            f"Current velocity is {current_sales_velocity:.1f}. "
            f"Recommend {modifier:+.1%} adjustment."
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
