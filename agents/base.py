"""
Base agent framework: Abstract class and standardized output contract.
All agents must extend BaseAgent and return AgentRecommendation.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass, asdict
import json


@dataclass
class AgentRecommendation:
    """Standardized output contract for all agents."""
    agent_id: str
    sku: str
    confidence: float  # Scale 0.0 to 1.0 based on data freshness/completeness
    recommendation: Dict[str, float]  # {"suggested_modifier": float}
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class BaseAgent(ABC):
    """Abstract base class for all pricing agents."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abstractmethod
    def analyze(self, product_data: Dict[str, Any], system_context: Dict[str, Any]) -> AgentRecommendation:
        """
        Analyze product data and system context, returning a standardized recommendation.

        Args:
            product_data: Dictionary with SKU metadata (price, cost, stock, velocity, etc.)
            system_context: Dictionary with external market data, agent scores, etc.

        Returns:
            AgentRecommendation: Standardized output with modifier, confidence, and rationale.
        """
        pass
