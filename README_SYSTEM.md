# Dynamic Retail Pricing Agent 🤖💰

A modular, production-ready multi-agent system for adaptive retail pricing using **LangGraph**, **FastAPI**, and **SQLite**.

This system combines **deterministic Python logic** for calculations and guardrails with **LLM-powered strategic reasoning** for human-readable explanations, creating a hybrid workflow that's both transparent and intelligent.

---

## 🏗️ Architecture Overview

### Core Components

1. **Modular Agent Framework** (`agents.py`)
   - Base abstract class for extensibility
   - Initial agent: Inventory Agent (internal signals)
   - Future agents plug in without modifying core logic
   - Standardized output contract for all agents

2. **Deterministic Math Engine** (`math_engine.py`)
   - Pure Python calculation engine
   - Weighted aggregation formula
   - Business guardrails enforcement
   - No LLM involvement in calculations

3. **LangGraph Pipeline** (`pipeline.py`)
   - Orchestrates multi-agent workflow
   - Data Fetcher → Parallel Agents → Weight Optimizer → Math Engine → Database Sync
   - Modular node architecture for easy extension

4. **FastAPI Application** (`app.py`)
   - REST endpoints for pipeline and decision management
   - Human-in-the-loop workflow support
   - Monitoring and debugging endpoints

5. **Dual-Loop Feedback System** (`feedback.py`)
   - **Human Feedback Loop (Immediate)**: Updates `human_trust_score` when managers approve/reject
   - **Market Performance Loop (3-day)**: Updates `market_performance_score` based on real outcomes
   - Continuous agent score adaptation

---

## 📋 Quick Start

### 1. Installation

```bash
cd c:\Users\311205\Personal\DynamicPricingAgent

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python database.py
```

This creates:
- SQLite database: `pricing_poc.db`
- Tables: products, agent_registry, recommendations, pricing_ledger, feedback_cache
- Sample data: 3 test products, 1 inventory agent


### 4. Start API Server

```bash
python -m uvicorn app:app --reload --port 8000
```

Visit: http://localhost:8000/docs for interactive API documentation

---

## 🔌 API Endpoints

### Core Endpoints

**GET /api/pending**
- Retrieves all pending recommendations awaiting manager review
- Returns: List of pending recommendations with full breakdown and justifications

**POST /api/decision**
- Manager approves or rejects a recommendation
- Request: `{"id": 1, "action": "APPROVED" | "REJECTED"}`
- Updates product price and agent trust score

**POST /api/run-pipeline**
- Manually trigger the pricing pipeline for a SKU
- Request: `{"sku": "SKU001"}`
- Returns: Recommendation with applied modifier and calculated price

### Monitoring Endpoints

**GET /api/products**
- List all products with current pricing metadata

**GET /api/agent-scores**
- Display all agent scores (trust & performance)
- Useful for monitoring agent effectiveness

**POST /api/evaluate-performance**
- Manually trigger 3-day market performance evaluation
- Returns: Evaluation summary with agent score updates

**GET /health**
- Basic health check

---

## 🤖 Agent System (Modular Architecture)

### Current Agents

#### Inventory Agent (`inventory_agent_v1`)
- **Focus**: Internal inventory signal
- **Input**: Stock on hand, sales velocity, optimal level
- **Calculation**: Days of Supply, scarcity flags
- **Output**: Modifier (±15% range) + confidence (0.6–0.95)
- **Scenarios**:
  - CRITICAL_STOCK (< 10%): +15% surge to reduce demand
  - LOW_STOCK (10–30%): +8% moderate premium
  - OVERSTOCKED (> 150%): -10% discount to liquidate
  - OPTIMAL: 0% no change

### Adding Future Agents

To add a new agent (e.g., `competitor_pricing_agent`, `seasonal_trends_agent`):

1. **Create agent class** in `agents.py`:
```python
class CompetitorAgent(BaseAgent):
    def analyze(self, product_data, system_context):
        # Your deterministic calculations here
        return AgentRecommendation(...)
```

2. **Register in LangGraph** (`pipeline.py`):
```python
workflow.add_node("competitor_agent", node_competitor_agent)
# Add edge in pipeline
```

3. **Add to agent_registry** (database):
```sql
INSERT INTO agent_registry (agent_id, agent_type) 
VALUES ('competitor_agent_v1', 'external');
```

**That's it!** The math engine and feedback loops automatically adapt.

---

## 📊 Data Schemas

### products table
```sql
sku (PK)
product_name
current_price
cost_price
stock_on_hand
sales_velocity_7d
optimal_stock_level
days_to_reorder_arrival
```

### agent_registry table
```sql
agent_id (PK)
human_trust_score [0.0-1.0]
market_performance_score [0.0-1.0]
is_active
agent_type
```

### recommendations table
```sql
id (PK)
sku, agent_id
suggested_price, suggested_modifier, confidence
justification (text rationale)
breakdown_matrix (formatted calculation details)
status: PENDING | APPROVED | REJECTED
timestamp, resolved_at
```

### pricing_ledger table
```sql
id (PK)
sku, agent_id
applied_modifier, applied_price
margin_delta_3d, volume_delta_3d (evaluated after 3 days)
applied_at, evaluated_at
```

---

## 🔄 Workflow: End-to-End

### 1. Pipeline Execution (On Demand)

```
POST /api/run-pipeline {"sku": "SKU001"}
    ↓
[Data Fetcher] Loads product data & agent scores from DB
    ↓
[Inventory Agent] Analyzes stock levels → {modifier: 0.08, confidence: 0.85}
    ↓
[Weight Optimizer] Calculates dynamic runtime weights (e.g., inventory=0.65)
    ↓
[Math Engine] Applies formula: Price = Base × (1 + Σ(M×W×C)/Σ(W×C))
              Enforces guardrails: [cost×1.05, base×1.5]
    ↓
[DB Sync] Saves recommendation as PENDING in recommendations table
    ↓
Response: {"recommendation_id": 42, "status": "PENDING"}
```

### 2. Human Decision (Manager Review)

```
Manager views GET /api/pending and sees recommendation
Manager clicks "APPROVE"
    ↓
POST /api/decision {"id": 42, "action": "APPROVED"}
    ↓
[Feedback System] Phase 4.1: Human Feedback Loop
  - Updates products.current_price
  - Moves recommendation to APPROVED
  - Logs to pricing_ledger
  - Increments agent.human_trust_score by +0.02
    ↓
Response: {"status": "APPROVED", "trust_delta": +0.02}
```

### 3. 3-Day Market Evaluation (Automatic/Manual)

```
POST /api/evaluate-performance
    ↓
[Query pricing_ledger] Find entries from ~3 days ago
    ↓
[Market Performance Loop] Evaluate actual outcomes:
  - Discount applied? → Check if sales_velocity increased (success ✅)
  - Surge applied? → Check if stock preserved (success ✅)
  - Neutral? → Always success ✅
    ↓
[Update Scores] Successful: market_performance_score += 0.03
                Failed: market_performance_score -= 0.04
    ↓
Response: {"evaluated_count": 5, "successful_outcomes": 4, "failed_outcomes": 1}
```

---

## 🧮 Math Formula

### Price Recommendation Formula

$$\text{Target Price} = \text{Base Price} \times \left( 1 + \frac{\sum (M_i \times W_i \times C_i)}{\sum (W_i \times C_i)} \right)$$

Where:
- $M_i$ = suggested modifier from agent $i$ (e.g., 0.08 for +8%)
- $W_i$ = runtime weight (dynamically calculated, sums to 1.0)
- $C_i$ = confidence score (0.0–1.0)

### Example Calculation

```
Base Price: $29.99
Inventory Agent: M=0.15, W=0.65, C=0.95

Numerator = 0.15 × 0.65 × 0.95 = 0.0929
Denominator = 0.65 × 0.95 = 0.6175

Applied Modifier = 0.0929 / 0.6175 = 0.1504 (15.04%)

Target Price = $29.99 × (1 + 0.1504) = $34.51

Guardrails Check:
  Min = $40 × 1.05 = $42.00  (Skip, target is higher)
  Max = $29.99 × 1.5 = $44.99 (OK, target is lower)
  
Final Price: $34.51 ✅
```

---

## 🎯 Verification Checklist (From IMPLEMENTATION.md)

- [x] Static Pre-Processing Test: Inventory Node calculates Days of Supply via Python
- [x] Conflict Graph Run: System adapts weights based on stock levels
- [x] API Delivery Check: GET /api/pending exposes percentage shifts + explanations
- [x] Human State Mutator Test: Approve in API → product price updates + agent score rises
- [x] Telemetry Analytics Check: 3-day evaluation adjusts scores autonomously

---

## 📁 Project Structure

```
DynamicPricingAgent/
├── database.py           # SQLite schema & initialization
├── agents.py             # Base agent class + Inventory Agent
├── math_engine.py        # Deterministic calculations
├── pipeline.py           # LangGraph orchestration
├── app.py                # FastAPI endpoints
├── feedback.py           # Dual-loop feedback system
├── test_demo.py          # Comprehensive test suite
├── requirements.txt      # Dependencies
├── .env.example          # Environment template
├── README.md             # This file
└── pricing_poc.db        # SQLite database (auto-created)
```

---

## 🔧 Configuration & Tuning

### Feedback System Deltas (feedback.py)

Adjust these constants to change agent score responsiveness:

```python
HUMAN_APPROVAL_DELTA = 0.02      # +0.02 when manager approves
HUMAN_REJECTION_DELTA = -0.05    # -0.05 when manager rejects
MARKET_SUCCESS_DELTA = 0.03      # +0.03 on successful outcome
MARKET_FAILURE_DELTA = -0.04     # -0.04 on failed outcome
```

### Guardrail Ranges (math_engine.py)

```python
minimum_price = cost_price * 1.05  # Never below 5% margin
maximum_price = base_price * 1.5   # Never surge > 50%
```

### Inventory Agent Modifiers (agents.py)

```python
CRITICAL_STOCK: +15%
LOW_STOCK: +8%
OVERSTOCKED: -10%
OPTIMAL: 0%
```

---

## 🧪 Testing

Run the comprehensive test suite:

```bash
python test_demo.py
```

Tests cover:
1. Database schema and sample data
2. Inventory Agent analysis (3 scenarios)
3. Math engine aggregation
4. Full pipeline execution
5. Feedback system (human + market loops)
6. Database query verification

---

## 🚀 Future Enhancements

1. **Add Competitor Pricing Agent**
   - Ingest external market data
   - Detect pricing gaps and opportunities
   - Conflict resolution with Inventory Agent

2. **Add Seasonal Trends Agent**
   - Analyze historical seasonality
   - Predict demand peaks/valleys
   - Recommend proactive pricing adjustments

3. **React Dashboard**
   - Real-time recommendation queue
   - Approve/reject with one click
   - Visual agent score tracking
   - Historical pricing trends

4. **LLM Integration**
   - Enhanced rationale generation with GPT-4
   - Few-shot learning from manager feedback
   - Natural language configuration

5. **Advanced Scheduling**
   - Background job for daily pipeline runs
   - Scheduled 3-day evaluations
   - Automatic reorder alerts

---

## 📝 License & Support

For questions or contributions, refer to the IMPLEMENTATION.md document for the complete system specification.

---

**Built with ❤️ for retail pricing optimization**
