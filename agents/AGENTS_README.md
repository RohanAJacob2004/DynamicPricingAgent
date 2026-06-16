"""
Agents Package Documentation

This folder contains all pricing agents used by the Dynamic Retail Pricing system.
Agents are organized by type for scalability and maintainability.

## Folder Structure

```
agents/
├── __init__.py                  # Package initialization & exports
├── base.py                      # Abstract BaseAgent class & AgentRecommendation contract
├── inventory.py                 # Inventory Agent (internal signal)
├── seasonal.py                  # Seasonal Agent (example external signal)
├── competitor.py                # Competitor Agent (example external signal)
└── AGENTS_README.md             # This file
```

## Agent Types

### Internal Signal Agents
Analyze internal business metrics (inventory, sales, margins)

- **inventory.py**: `InventoryAgent`
  - Analyzes stock levels and Days of Supply
  - Signals: CRITICAL_STOCK, LOW_STOCK, OVERSTOCKED, OPTIMAL
  - Modifiers: -10% to +15% based on scarcity

### External Signal Agents
Analyze external market data (competitors, seasonality, trends)

- **seasonal.py**: `SeasonalAgent` (example)
  - Analyzes seasonal demand patterns
  - Implements seasonal pricing adjustments
  
- **competitor.py**: `CompetitorAgent` (example)
  - Analyzes competitor pricing
  - Recommends competitive positioning

## Adding a New Agent

### 1. Create Agent File
Create a new Python file in the `agents/` folder:

```python
# agents/my_agent.py
from agents.base import BaseAgent, AgentRecommendation
from typing import Dict, Any

class MyAgent(BaseAgent):
    def __init__(self, agent_id: str = "my_agent_v1"):
        super().__init__(agent_id)
    
    def analyze(self, product_data: Dict[str, Any], system_context: Dict[str, Any]) -> AgentRecommendation:
        # Your logic here
        modifier = 0.05
        confidence = 0.80
        rationale = "Your explanation"
        
        return AgentRecommendation(
            agent_id=self.agent_id,
            sku=product_data['sku'],
            recommendation={"suggested_modifier": modifier, "confidence": confidence},
            rationale=rationale
        )
```

### 2. Update `__init__.py`
Add the agent to the package exports:

```python
# agents/__init__.py
from agents.base import BaseAgent, AgentRecommendation
from agents.inventory import InventoryAgent
from agents.my_agent import MyAgent  # Add this line

__all__ = [
    'BaseAgent',
    'AgentRecommendation',
    'InventoryAgent',
    'MyAgent'  # Add this line
]
```

### 3. Register in Database
Add the agent to the `agent_registry` table:

```sql
INSERT INTO agent_registry (agent_id, human_trust_score, market_performance_score, is_active, agent_type)
VALUES ('my_agent_v1', 0.5, 0.5, 1, 'custom');
```

### 4. Register in Pipeline (pipeline.py)
Add the agent node to the LangGraph pipeline:

```python
# In pipeline.py

def node_my_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    if 'error' in state:
        return state
    
    agent = MyAgent(agent_id="my_agent_v1")
    try:
        recommendation = agent.analyze(state['product_data'], state['system_metrics'])
        state['agent_recommendations'].append(recommendation.to_dict())
    except Exception as e:
        state['my_agent_error'] = f"My agent failed: {str(e)}"
    
    return state

def create_pricing_pipeline():
    workflow = StateGraph(dict)
    
    # ... existing nodes ...
    workflow.add_node("my_agent", node_my_agent)
    
    # Add edges
    workflow.add_edge("data_fetcher", "my_agent")
    workflow.add_edge("my_agent", "weight_optimizer")
    
    # ... rest of pipeline ...
```

**That's it!** The system automatically adapts:
- Math engine includes your agent's recommendation
- Feedback loops track your agent's performance
- Weights adjust based on your agent's scores
- No changes to core logic needed

## Agent Base Class (BaseAgent)

All agents must extend `BaseAgent` and implement the `analyze()` method.

```python
class BaseAgent(ABC):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
    
    @abstractmethod
    def analyze(self, product_data: Dict[str, Any], system_context: Dict[str, Any]) -> AgentRecommendation:
        pass
```

### Input: product_data
```python
{
    'sku': 'SKU001',
    'product_name': 'Premium Widget',
    'current_price': 29.99,
    'cost_price': 12.00,
    'stock_on_hand': 150,
    'sales_velocity_7d': 45.0,
    'optimal_stock_level': 100,
    'days_to_reorder_arrival': 7
}
```

### Input: system_context
```python
{
    'stock_percentage': 150.0,
    'critical_stock': False,
    'low_stock': False,
    'overstocked': False,
    'current_month': 6,
    'competitor_prices': {'SKU001': 28.99}
}
```

### Output: AgentRecommendation
```python
AgentRecommendation(
    agent_id='my_agent_v1',
    sku='SKU001',
    recommendation={
        'suggested_modifier': 0.05,  # +5% suggested price change
        'confidence': 0.80           # 80% confidence in this recommendation
    },
    rationale="Clear, human-readable explanation (no currency values)"
)
```

## Best Practices

### 1. Deterministic Logic First
Keep calculations in pure Python. LLMs are used only for explanations:

```python
# ✅ Good: Deterministic calculation
def _compute_modifier(self, data):
    if data['stock'] < 10:
        return 0.15
    return 0.0

# ❌ Avoid: LLM in calculation
def _compute_modifier(self, data):
    modifier = llm.predict(f"Stock is {data['stock']}")  # Don't do this
    return modifier
```

### 2. Confidence Scoring
Reflect signal quality in confidence (0.0-1.0):

```python
# Strong signal: high confidence
if critical_condition:
    return 0.95

# Weak signal: low confidence  
if ambiguous_condition:
    return 0.50
```

### 3. Modifier Ranges
Keep modifiers reasonable (typically -0.30 to +0.30):

```python
# ✅ Reasonable
modifier = -0.10  # -10% discount

# ❌ Too extreme (will be clamped by guardrails anyway)
modifier = -0.80  # -80% (unreasonable)
```

### 4. Clear Rationale
Explain recommendations in non-technical terms:

```python
# ✅ Good: Clear, actionable, no currency
rationale = "Stock is 12 units (target 50). Recommend surge pricing to manage demand."

# ❌ Poor: Too technical, includes currency
rationale = "Based on ML model analysis, optimal price point is $34.99"
```

### 5. Error Handling
Always handle exceptions gracefully:

```python
def analyze(self, product_data, system_context):
    try:
        # Your logic
        return recommendation
    except Exception as e:
        # Return neutral recommendation on error
        return AgentRecommendation(
            agent_id=self.agent_id,
            sku=product_data['sku'],
            recommendation={"suggested_modifier": 0.0, "confidence": 0.0},
            rationale=f"Error during analysis: {str(e)}"
        )
```

## Testing Your Agent

```python
from agents import MyAgent

# Create agent instance
agent = MyAgent()

# Create test data
product_data = {
    'sku': 'SKU001',
    'product_name': 'Test Product',
    'current_price': 29.99,
    'cost_price': 12.00,
    'stock_on_hand': 150,
    'sales_velocity_7d': 45.0,
    'optimal_stock_level': 100,
    'days_to_reorder_arrival': 7
}

system_context = {
    'stock_percentage': 150.0,
    'current_month': 6
}

# Run analysis
recommendation = agent.analyze(product_data, system_context)

# Inspect output
print(f"Modifier: {recommendation.recommendation['suggested_modifier']:+.1%}")
print(f"Confidence: {recommendation.recommendation['confidence']:.2f}")
print(f"Rationale: {recommendation.rationale}")
```

## Future Agents to Implement

Ideas for extending the system:

1. **Demand Forecasting Agent** - ML-based demand prediction
2. **Promotion Agent** - Recommendation when to run promotions
3. **Cost Volatility Agent** - React to input cost changes
4. **Customer Segment Agent** - Different pricing for segments
5. **Inventory Age Agent** - Price based on how old inventory is
6. **Margin Optimization Agent** - Maximize total margin
7. **Market Share Agent** - Protect market share vs. profit

---

**Agent-based architecture enables continuous expansion without complexity!**
