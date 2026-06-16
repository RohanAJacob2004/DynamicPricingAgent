# Architecture & Design Document

## System Overview

The Dynamic Retail Pricing Agent is a **hybrid deterministic/LLM multi-agent system** that combines:

1. **Deterministic Python Logic** - Calculations, guardrails, guardrails
2. **LLM-Powered Reasoning** - Strategic decision-making and human-readable explanations
3. **Human-in-the-Loop** - Manager approval workflow with automatic feedback
4. **Modular Agent Framework** - Seamless extension from 1 agent to N agents

---

## Design Principles

### 1. Separation of Concerns

- **Agents**: Responsible for analysis and recommendation generation
- **Math Engine**: Responsible for calculations and aggregation only
- **Pipeline**: Orchestrates workflow without business logic
- **Feedback System**: Manages agent learning independently

### 2. Deterministic Execution

All calculations must be pure Python—no LLM involvement:
- ✅ Agent modifier calculations
- ✅ Weight optimization
- ✅ Price aggregation formula
- ✅ Guardrail enforcement
- ✅ Market outcome evaluation

LLMs are used only for:
- Generating human-readable explanations
- Few-shot learning from feedback
- Strategic context enrichment (future)

### 3. Modularity

Adding a new agent requires **ZERO changes** to core logic:
1. Create agent class extending `BaseAgent`
2. Register in LangGraph pipeline
3. Add to agent_registry database table
4. Done—all existing systems adapt automatically

### 4. Transparency

Every recommendation includes:
- Justification (human-readable rationale)
- Breakdown matrix (calculation details)
- Confidence score (signal quality)
- Applied guardrails (if any)

---

## Phase-by-Phase Architecture

### Phase 1: Modular Data Layer

**Database Schema** (`database.py`)

Four primary tables:

#### products
Stores base SKU metadata. Updated when a recommendation is approved.
```python
sku (PK)
current_price          # Updated by approval decisions
cost_price             # Base for guardrails
stock_on_hand          # Input for inventory analysis
sales_velocity_7d      # Input for Days of Supply calc
optimal_stock_level    # Target for scarcity assessment
days_to_reorder_arrival # For planning
```

#### agent_registry
Dynamic agent metadata with continuously updating scores.
```python
agent_id (PK)
human_trust_score [0.0-1.0]       # ← Updated by human decisions
market_performance_score [0.0-1.0] # ← Updated by 3-day evaluation
is_active (bool)                   # Toggle agents on/off
agent_type (str)                   # Category: 'inventory', 'external', etc.
```

#### recommendations
Pipeline output queue awaiting human review.
```python
id (PK)
sku, agent_id                # What product, which agent
suggested_price              # Final calculated price
suggested_modifier           # Percentage change (e.g., +0.08)
confidence                   # Signal quality [0.0-1.0]
justification               # Human-readable explanation
breakdown_matrix            # Detailed calculation trail
status: PENDING|APPROVED|REJECTED
timestamp, resolved_at
```

#### pricing_ledger
Historical log of executed recommendations for performance evaluation.
```python
id (PK)
sku, agent_id
applied_modifier            # What modifier was actually applied
applied_price               # Resulting product price
margin_delta_3d            # Calculated after 72 hours
volume_delta_3d            # Calculated after 72 hours
applied_at, evaluated_at
```

---

### Phase 2: Hybrid LangGraph Pipeline

**Core Orchestration** (`pipeline.py`)

```
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph Workflow                         │
└─────────────────────────────────────────────────────────────┘

Entry Point
    │
    ▼
┌──────────────────────────────────────┐
│      [Data Fetcher Node]             │
│  Loads product data & agent scores   │
│  Calculates system metrics           │
└──────────────────┬───────────────────┘
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
┌─────────────────────┐   ┌─────────────────────┐
│ [Inventory Agent]   │   │ [Future Agents]     │
│ (Parallel Layer)    │   │ (Pluggable)         │
│ → Modifier          │   │ → Modifier          │
│ → Confidence        │   │ → Confidence        │
└─────────┬───────────┘   └─────────┬───────────┘
          │                         │
          └──────────────┬──────────┘
                         ▼
        ┌────────────────────────────────┐
        │  [Weight Optimizer Node]       │
        │  Calculates runtime weights    │
        │  Applies edge-case rules       │
        └────────────┬───────────────────┘
                     ▼
        ┌────────────────────────────────┐
        │  [Math Engine Node]            │
        │  Aggregate recommendations     │
        │  Apply guardrails             │
        │  Formula: Price×(1+Σ(M×W×C))   │
        └────────────┬───────────────────┘
                     ▼
        ┌────────────────────────────────┐
        │  [DB Sync Node]                │
        │  Save recommendation as PENDING│
        └────────────┬───────────────────┘
                     ▼
                Exit Point (State)
```

### Node Details

#### Data Fetcher
**Responsibility**: Load all inputs required for decision-making

```python
def node_data_fetcher(state):
    # Fetch product data from database
    # Fetch agent scores (human_trust, market_performance)
    # Calculate system metrics (stock %, critical flags)
    return enriched_state
```

**State Added**:
- `product_data`: Full product row
- `agent_scores`: All active agents with scores
- `system_metrics`: Derived flags (critical_stock, low_stock, overstocked)

#### Inventory Agent (Current)
**Responsibility**: Analyze internal inventory signals

```python
def node_inventory_agent(state):
    agent = InventoryAgent()
    
    # Phase 1: Deterministic calculations
    days_of_supply = calc_dos(stock, velocity)  # Python
    scarcity_flag = calc_flag(dos, optimal)     # Python
    modifier = compute_modifier(flag)            # Python
    confidence = compute_confidence(flag)        # Python
    
    # Phase 2: LLM-powered explanation (future)
    # rationale = llm.generate_rationale(...)
    
    # Phase 3: Return standardized output
    return AgentRecommendation(
        agent_id="inventory_agent_v1",
        sku=sku,
        recommendation={
            "suggested_modifier": modifier,
            "confidence": confidence
        },
        rationale=rationale
    )
```

**Decisions Made**:
- CRITICAL_STOCK (< 10%): +15% surge premium
- LOW_STOCK (10–30%): +8% moderate premium
- OVERSTOCKED (> 150%): -10% liquidation discount
- OPTIMAL: 0% no change

#### Weight Optimizer
**Responsibility**: Calculate dynamic agent weights based on scores and system state

```python
def node_weight_optimizer(state):
    weights = {}
    
    for agent_id, scores in agent_scores.items():
        # Base weight: average trust + performance
        base_weight = (scores['human_trust'] + scores['market_perf']) / 2
        
        # Rule override: Force inventory agent if critical stock
        if agent_id == 'inventory_agent' and system_metrics['critical_stock']:
            base_weight = max(base_weight, 0.9)
        
        weights[agent_id] = base_weight
    
    # Normalize to sum to 1.0
    total = sum(weights.values())
    weights = {k: v/total for k,v in weights.items()}
    
    return weights
```

**Edge Cases**:
- If stock < 10%, inventory agent weight forced to ≥ 0.9
- Future: Add seasonal or external pricing overrides

#### Math Engine (Pure Python)
**Responsibility**: Execute formula and enforce guardrails

```python
def node_math_engine(state):
    # Aggregate all agent recommendations
    numerator = sum(M_i * W_i * C_i for each agent)
    denominator = sum(W_i * C_i for each agent)
    
    effective_modifier = numerator / denominator
    
    # Calculate target price
    target_price = base_price * (1 + effective_modifier)
    
    # Apply guardrails
    final_price = clamp(
        target_price,
        min=cost_price * 1.05,     # Never < 5% margin
        max=base_price * 1.5        # Never surge > 50%
    )
    
    return {
        'calculated_price': target_price,
        'final_price': final_price,
        'applied_modifier': effective_modifier,
        'breakdown': [...breakdown details...]
    }
```

#### DB Sync
**Responsibility**: Persist recommendation for human review

```python
def node_sync_db(state):
    # Insert into recommendations table with status='PENDING'
    INSERT recommendations VALUES (
        sku, agent_id, suggested_price, modifier,
        confidence, justification, breakdown_matrix, 'PENDING'
    )
    # Store recommendation_id for later tracking
    return recommendation_id
```

---

### Phase 3: FastAPI Connected Architecture

**REST API Layer** (`app.py`)

Endpoints expose pipeline and feedback functionality to external systems (React UI, scripts, etc.).

#### Core Endpoints

**POST /api/run-pipeline**
- Trigger pipeline execution for a specific SKU
- Returns: Recommendation with all details
- Called by: Scheduled jobs, manual triggers, UI "Recalculate" button

**GET /api/pending**
- Retrieve all PENDING recommendations
- Returns: List with justifications and breakdown matrices
- Called by: Manager review dashboard

**POST /api/decision**
- Manager submits approval/rejection decision
- Actions: Updates pricing, logs to ledger, adjusts agent scores
- Called by: React dashboard, approval workflow

#### Monitoring Endpoints

**GET /api/agent-scores**
- Display current agent scores for transparency

**POST /api/evaluate-performance**
- Manually trigger 3-day market performance evaluation
- Normally runs on schedule (nightly background job)

**GET /api/products**
- List all products with current metadata

---

### Phase 4: Dual-Loop Feedback System

**Adaptive Learning** (`feedback.py`)

Two independent feedback mechanisms continuously adjust agent scores:

#### Loop A: Human Feedback (Immediate)

**Trigger**: Manager approves or rejects a recommendation

**Process**:
1. Get recommendation details (agent_id, sku, suggested_price)
2. If APPROVED:
   - Update `products.current_price` to suggested price
   - Move recommendation to APPROVED status
   - Log to `pricing_ledger`
   - Increment agent `human_trust_score` by +0.02
3. If REJECTED:
   - Keep recommendation as REJECTED
   - Decrement agent `human_trust_score` by -0.05
   - (Caching: High-confidence rejections added to few-shot examples)

**Result**: Human feedback directly adjusts how much an agent's recommendations are trusted.

#### Loop B: Market Performance (3-Day Delayed)

**Trigger**: Nightly evaluation of recommendations applied ~72 hours prior

**Process**:
1. Query `pricing_ledger` for entries not yet evaluated (evaluated_at IS NULL)
2. For each entry, evaluate actual market outcome:
   ```python
   if applied_modifier < 0:      # Discount applied
       success = sales_velocity > threshold  # Did volume increase?
   elif applied_modifier > 0:    # Surge applied
       success = stock_level > critical     # Did margin hold?
   else:                         # No change
       success = True            # Always good
   ```
3. Based on outcome:
   - Success: agent `market_performance_score` += 0.03
   - Failure: agent `market_performance_score` -= 0.04
4. Mark entry as evaluated (evaluated_at = NOW)

**Result**: Agent scores reflect real-world pricing effectiveness, not just manager opinion.

---

## Modular Extension: Adding a New Agent

**Example: Competitor Pricing Agent**

### Step 1: Define Agent Class

```python
# In agents.py

class CompetitorAgent(BaseAgent):
    def analyze(self, product_data, system_context):
        # Phase 1: Deterministic analysis
        sku = product_data['sku']
        our_price = product_data['current_price']
        
        # Mock external data (replace with API call)
        competitor_prices = system_context.get('competitor_prices', {})
        comp_avg = competitor_prices.get(sku, our_price)
        
        # Calculate price gap
        gap_percent = (our_price - comp_avg) / comp_avg
        
        # Determine modifier based on gap
        if gap_percent > 0.15:  # We're >15% higher
            modifier = -0.10    # Recommend 10% discount
            confidence = 0.85
        elif gap_percent < -0.10:  # We're >10% lower
            modifier = 0.08     # Recommend 8% increase
            confidence = 0.80
        else:
            modifier = 0.0
            confidence = 0.60
        
        # Phase 2: Rationale
        rationale = f"Competitor average: ${comp_avg:.2f}, Gap: {gap_percent:+.1%}. " \
                   f"Recommend {modifier:+.1%} adjustment to maintain competitiveness."
        
        return AgentRecommendation(
            agent_id="competitor_agent_v1",
            sku=sku,
            recommendation={"suggested_modifier": modifier, "confidence": confidence},
            rationale=rationale
        )
```

### Step 2: Register in Pipeline

```python
# In pipeline.py

def create_pricing_pipeline():
    workflow = StateGraph(dict)
    
    # ... existing nodes ...
    workflow.add_node("competitor_agent", node_competitor_agent)
    
    # Add edges
    workflow.add_edge("data_fetcher", "inventory_agent")
    workflow.add_edge("data_fetcher", "competitor_agent")
    workflow.add_edge("inventory_agent", "weight_optimizer")
    workflow.add_edge("competitor_agent", "weight_optimizer")
    # ... rest of pipeline ...
    
    return workflow.compile()

def node_competitor_agent(state):
    agent = CompetitorAgent()
    try:
        recommendation = agent.analyze(state['product_data'], state.get('competitor_data', {}))
        state['agent_recommendations'].append(recommendation.to_dict())
    except Exception as e:
        state['competitor_error'] = f"Competitor agent failed: {str(e)}"
    return state
```

### Step 3: Register in Database

```python
# In database.py or via API

INSERT INTO agent_registry (agent_id, human_trust_score, market_performance_score, is_active, agent_type)
VALUES ('competitor_agent_v1', 0.5, 0.5, 1, 'external');
```

### Done! ✅

The system now:
- Runs competitor agent in parallel with inventory agent
- Automatically weights both recommendations based on scores
- Applies math engine aggregation
- Feedback loops update both agents independently
- No changes to core logic required

---

## Data Flow Diagram

```
User Request (POST /api/run-pipeline {"sku": "SKU001"})
    │
    ▼
[FastAPI Endpoint] → run_pricing_pipeline(sku)
    │
    ▼
[LangGraph Pipeline Invoked]
    │
    ├→ Data Fetcher: Query DB for product, agent scores
    │
    ├→ Agent Layer (Parallel):
    │  ├→ Inventory Agent: Analyze stock (Python deterministic)
    │  ├→ [Future] Competitor Agent: Compare prices (Python deterministic)
    │  ├→ [Future] Seasonal Agent: Check seasonality (Python deterministic)
    │  └→ All → Generate AgentRecommendation (standardized contract)
    │
    ├→ Weight Optimizer: Calculate W_i for each agent (Pure Python)
    │
    ├→ Math Engine: 
    │  ├→ Apply formula: Price = Base × (1 + Σ(M×W×C))
    │  ├→ Enforce guardrails
    │  └→ Generate breakdown matrix
    │
    └→ DB Sync: INSERT into recommendations table (status='PENDING')
    │
    ▼
Response: {"recommendation_id": 42, ...}
    │
    ▼
[Manager Views Dashboard]
    ├→ GET /api/pending retrieves all PENDING recommendations
    ├→ Displays: Price, modifier %, confidence, justification, breakdown
    │
    └→ Manager clicks "APPROVE"
        │
        ▼
    [Human Decision Flow]
        │
        ├→ POST /api/decision {"id": 42, "action": "APPROVED"}
        │
        ├→ [Feedback Loop A]:
        │  ├→ UPDATE products SET current_price = ...
        │  ├→ INSERT INTO pricing_ledger
        │  └→ UPDATE agent_registry SET human_trust_score += 0.02
        │
        └→ Response: {"status": "APPROVED", ...}

[Later, 3-day evaluation cron job]
    │
    ├→ POST /api/evaluate-performance
    │
    ├→ [Feedback Loop B]:
    │  ├→ Query pricing_ledger for 72-hour-old entries
    │  ├→ Evaluate market outcomes (volume, margin)
    │  ├→ UPDATE agent_registry SET market_performance_score ± delta
    │  └→ Mark pricing_ledger entries as evaluated_at=NOW
    │
    └→ Response: {"evaluated_count": 3, "successful": 2, "failed": 1}
```

---

## Error Handling & Guardrails

### Business Guardrails (Math Engine)

```python
minimum_price = cost_price * 1.05      # Never sell below 5% margin
maximum_price = base_price * 1.5       # Never surge more than 50%

final_price = clamp(calculated_price, minimum_price, maximum_price)
```

### Graceful Degradation

- **Missing agent data**: System continues with available agents
- **Agent failure**: Error logged, other agents continue
- **Database error**: Recommendation not saved; error reported to user
- **Invalid inputs**: HTTPException with clear error message

### Audit Trail

Every decision is logged:
- recommendations table: What was proposed and human decision
- pricing_ledger: What was actually applied and outcomes
- agent_registry: Score history (consider adding timestamp logging)

---

## Performance Considerations

### Database Indexing

```sql
CREATE INDEX idx_recommendations_status ON recommendations(status);
CREATE INDEX idx_recommendations_timestamp ON recommendations(timestamp);
CREATE INDEX idx_pricing_ledger_applied_at ON pricing_ledger(applied_at);
CREATE INDEX idx_products_sku ON products(sku);
```

### Pipeline Execution

- Data Fetcher: 1 DB query
- Agent Layer: Parallel execution (N agents simultaneous)
- Weight Optimizer: Pure Python (negligible time)
- Math Engine: Pure Python (negligible time)
- DB Sync: 1 INSERT

**Total**: ~10–50ms for full pipeline with 1 agent

### Scaling

- Supports 100+ products/SKUs
- Supports N agents (no architectural limit)
- Agents can fetch external data asynchronously
- Consider async database queries for high volume

---

## Testing Strategy

### Unit Tests
- Agent analysis logic
- Math engine calculations
- Feedback score updates

### Integration Tests
- Full pipeline execution
- Database persistence
- API endpoints

### Scenario Tests (from test_demo.py)
1. Critical stock scenario
2. Optimal stock scenario
3. Overstocked scenario
4. Human approval/rejection
5. 3-day performance evaluation

---

## Security & Compliance

### Input Validation
- SKU exists in database
- Action in ['APPROVED', 'REJECTED']
- Price within guardrail range

### Access Control
- Consider adding authentication to /api/decision
- Audit logging for all price changes
- Role-based restrictions (e.g., only managers can approve)

### Data Protection
- Encrypt sensitive data (cost_price, margins)
- Backup database regularly
- Versioning for pricing_ledger entries

---

## Future Roadmap

1. **LLM Integration**: Use GPT-4 for sophisticated rationale generation
2. **Seasonal Agent**: Holiday demand prediction
3. **Competitor Agent**: Real-time market pricing sync
4. **React Dashboard**: Beautiful UI for managers
5. **Advanced Scheduling**: Automated daily/hourly pipeline runs
6. **A/B Testing**: Compare agent recommendations in shadow mode
7. **Analytics**: Historical trending, performance dashboards
8. **Mobile App**: Quick approval/rejection on the go

---

**End of Architecture Document**
