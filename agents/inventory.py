"""
Inventory Agent: Internal signal focus.
Analyzes Days of Supply and scarcity/liquidation scenarios.
Uses deterministic Python calculations for pricing decisions.
"""
from typing import Dict, Any
from agents.base import BaseAgent, AgentRecommendation


class InventoryAgent(BaseAgent):
    """
    Inventory Agent: Internal signal focus.
    Analyzes Days of Supply and scarcity/liquidation scenarios.
    Uses deterministic Python calculations + LLM for human-readable rationale.
    """

    def __init__(self, agent_id: str = "inventory_agent_v1", llm=None):
        super().__init__(agent_id)
        self.llm = llm  # Optional LLM for generating rationale

    def _calculate_days_of_supply(self, stock_on_hand: int, sales_velocity_7d: float) -> float:
        """
        Calculate Days of Supply: how many days the current stock will last.
        Deterministic Python calculation (no LLM).
        """
        if sales_velocity_7d <= 0:
            return float('inf')
        return (stock_on_hand / sales_velocity_7d) * 7

    def _calculate_scarcity_flag(self, days_of_supply: float, optimal_stock_level: int, stock_on_hand: int) -> str:
        """
        Deterministic flag calculation for scarcity/liquidation scenarios.
        Returns one of: 'CRITICAL_STOCK', 'LOW_STOCK', 'OVERSTOCKED', 'OPTIMAL'
        """
        stock_percentage = (stock_on_hand / optimal_stock_level) * 100

        if stock_percentage < 10:
            return 'CRITICAL_STOCK'
        elif stock_percentage < 30:
            return 'LOW_STOCK'
        elif stock_percentage > 150:
            return 'OVERSTOCKED'
        else:
            return 'OPTIMAL'

    def analyze(self, product_data: Dict[str, Any], system_context: Dict[str, Any]) -> AgentRecommendation:
        """
        Inventory-focused pricing recommendation.
        """
        sku = product_data['sku']
        stock_on_hand = product_data['stock_on_hand']
        sales_velocity_7d = product_data['sales_velocity_7d']
        optimal_stock_level = product_data['optimal_stock_level']
        cost_price = product_data['cost_price']

        # Phase 1: Deterministic Python calculations
        days_of_supply = self._calculate_days_of_supply(stock_on_hand, sales_velocity_7d)
        scarcity_flag = self._calculate_scarcity_flag(days_of_supply, optimal_stock_level, stock_on_hand)

        # Phase 2: Compute modifier based on scarcity signal
        suggested_modifier = self._compute_modifier(scarcity_flag, days_of_supply)
        confidence = self._compute_confidence(scarcity_flag, days_of_supply)

        # Phase 3: Generate human-readable rationale
        rationale = self._generate_rationale(
            scarcity_flag, days_of_supply, stock_on_hand, optimal_stock_level
        )

        return AgentRecommendation(
            agent_id=self.agent_id,
            sku=sku,
            confidence=confidence,
            recommendation={
                "suggested_modifier": suggested_modifier
            },
            rationale=rationale
        )

    def _compute_modifier(self, scarcity_flag: str, days_of_supply: float) -> float:
        """
        Deterministic formula to compute suggested modifier based on inventory state.
        """
        if scarcity_flag == 'CRITICAL_STOCK':
            # Premium surge: +15% for critical scarcity
            return 0.15
        elif scarcity_flag == 'LOW_STOCK':
            # Moderate premium: +8% for low stock
            return 0.08
        elif scarcity_flag == 'OVERSTOCKED':
            # Discount to liquidate: -10%
            return -0.10
        else:
            # Neutral: 0% modifier
            return 0.0

    def _compute_confidence(self, scarcity_flag: str, days_of_supply: float) -> float:
        """
        Confidence score reflects signal quality.
        Extreme scarcity = high confidence; optimal stock = moderate confidence.
        """
        if scarcity_flag == 'CRITICAL_STOCK':
            return 0.95
        elif scarcity_flag == 'LOW_STOCK':
            return 0.85
        elif scarcity_flag == 'OVERSTOCKED':
            return 0.90
        else:
            return 0.60

    def _generate_rationale(
        self,
        scarcity_flag: str,
        days_of_supply: float,
        stock_on_hand: int,
        optimal_stock_level: int
    ) -> str:
        """
        Human-readable explanation of the recommendation (no currency).
        """
        if scarcity_flag == 'CRITICAL_STOCK':
            return (
                f"CRITICAL STOCK ALERT: Only {stock_on_hand} units in hand (target: {optimal_stock_level}). "
                f"At current sales velocity, stock lasts {days_of_supply:.1f} days. "
                f"Recommend surge pricing (+15%) to reduce demand and preserve margin until reorder arrives."
            )
        elif scarcity_flag == 'LOW_STOCK':
            return (
                f"Low inventory: {stock_on_hand} units (target: {optimal_stock_level}). "
                f"Days of supply: {days_of_supply:.1f}. "
                f"Recommend modest premium (+8%) to help manage demand until inventory replenishes."
            )
        elif scarcity_flag == 'OVERSTOCKED':
            return (
                f"High inventory: {stock_on_hand} units (target: {optimal_stock_level}). "
                f"Recommend discount (-10%) to accelerate sales and reduce carrying costs."
            )
        else:
            return (
                f"Inventory at optimal level ({stock_on_hand} units). "
                f"Recommend maintaining current price; no modification needed."
            )
