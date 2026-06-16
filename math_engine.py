"""
Deterministic Math Engine: Pure Python calculations for price recommendations.
Removes all calculation responsibilities from LLMs.
"""
from typing import Dict, List, Any
import json


class DeterministicMathEngine:
    """
    Pure Python calculation engine for price recommendations.
    Executes deterministic weighted average formula and enforces business guardrails.
    """

    @staticmethod
    def aggregate_recommendations(
        agent_recommendations: List[Dict[str, Any]],
        runtime_weights: Dict[str, float],
        base_price: float,
        cost_price: float
    ) -> Dict[str, Any]:
        """
        Aggregate agent recommendations using weighted formula:
        Target Price = Base Price × (1 + Σ(M_i × W_i × C_i) / Σ(W_i × C_i))

        Args:
            agent_recommendations: List of agent output dicts with modifier, confidence
            runtime_weights: Dict mapping agent_id to runtime weight
            base_price: Current product price
            cost_price: Cost basis for guardrails

        Returns:
            Dict with calculated_price, applied_modifier, breakdown details
        """
        if not agent_recommendations:
            return {
                "calculated_price": base_price,
                "applied_modifier": 0.0,
                "breakdown": [],
                "error": "No agent recommendations provided"
            }

        breakdown = []
        numerator_sum = 0.0
        denominator_sum = 0.0

        for rec in agent_recommendations:
            agent_id = rec.get('agent_id', 'unknown')
            modifier = rec.get('recommendation', {}).get('suggested_modifier', 0.0)
            confidence = rec.get('confidence', 0.5)
            weight = runtime_weights.get(agent_id, 0.5)

            # Calculate weighted contribution
            weighted_contrib = modifier * weight * confidence

            numerator_sum += weighted_contrib
            denominator_sum += weight * confidence

            breakdown.append({
                "agent_id": agent_id,
                "modifier": modifier,
                "confidence": confidence,
                "weight": weight,
                "weighted_contribution": weighted_contrib
            })

        # Compute effective modifier
        if denominator_sum > 0:
            effective_modifier = numerator_sum / denominator_sum
        else:
            effective_modifier = 0.0

        # Calculate raw target price
        calculated_price = base_price * (1 + effective_modifier)

        # Apply guardrails
        final_price = DeterministicMathEngine._apply_guardrails(
            calculated_price, cost_price, base_price
        )

        return {
            "calculated_price": calculated_price,
            "final_price": final_price,
            "applied_modifier": effective_modifier,
            "guardrails_applied": calculated_price != final_price,
            "breakdown": breakdown
        }

    @staticmethod
    def _apply_guardrails(calculated_price: float, cost_price: float, base_price: float) -> float:
        """
        Enforce business guardrails:
        1. Never price below cost × 1.05 (5% minimum margin)
        2. Never exceed base price × 1.5 (50% max surge)
        3. Prevent negative prices
        """
        minimum_price = cost_price * 1.05
        maximum_price = base_price * 1.5

        # Apply guardrails sequentially
        if calculated_price < minimum_price:
            return minimum_price
        elif calculated_price > maximum_price:
            return maximum_price
        else:
            return calculated_price

    @staticmethod
    def calculate_runtime_weights(
        agent_scores: Dict[str, Dict[str, float]],
        system_metrics: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate dynamic runtime weights based on agent scores and system conditions.
        Applies rule overrides for edge cases (e.g., critical stock).

        Args:
            agent_scores: Dict[agent_id] -> {human_trust_score, market_performance_score}
            system_metrics: Current system state (e.g., stock levels, velocity)

        Returns:
            Dict[agent_id] -> runtime weight
        """
        weights = {}

        for agent_id, scores in agent_scores.items():
            human_trust = scores.get('human_trust_score', 0.5)
            market_perf = scores.get('market_performance_score', 0.5)

            # Base weight: average of trust and performance
            base_weight = (human_trust + market_perf) / 2.0

            # Apply edge-case rule overrides
            # If stock is critically low, force inventory agent priority
            if agent_id == 'inventory_agent_v1' and system_metrics.get('critical_stock', False):
                base_weight = max(base_weight, 0.9)

            weights[agent_id] = base_weight

        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        else:
            # Default equal weighting if all scores are zero
            num_agents = len(weights)
            weights = {k: 1.0 / num_agents for k in weights.keys()}

        return weights

    @staticmethod
    def format_breakdown_matrix(breakdown: List[Dict[str, Any]]) -> str:
        """Format breakdown details as a readable matrix for UI/logs."""
        lines = ["=== Recommendation Breakdown ==="]
        lines.append(f"{'Agent':<25} {'Modifier':<12} {'Confidence':<12} {'Weight':<10} {'Contribution':<12}")
        lines.append("-" * 75)

        for item in breakdown:
            agent_id = item['agent_id'][:22]
            modifier = f"{item['modifier']:+.2%}"
            confidence = f"{item['confidence']:.2f}"
            weight = f"{item['weight']:.3f}"
            contribution = f"{item['weighted_contribution']:+.4f}"

            lines.append(f"{agent_id:<25} {modifier:<12} {confidence:<12} {weight:<10} {contribution:<12}")

        return "\n".join(lines)
