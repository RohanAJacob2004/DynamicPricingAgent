"""
Modular agent framework package.
Agents are organized by type for scalability and maintainability.
"""

from agents.base import BaseAgent, AgentRecommendation
from agents.inventory import InventoryAgent
from agents.seasonal import SeasonalAgent
from agents.competitor import CompetitorAgent

__all__ = [
    'BaseAgent',
    'AgentRecommendation',
    'InventoryAgent',
    'SeasonalAgent',
    'CompetitorAgent'
]
