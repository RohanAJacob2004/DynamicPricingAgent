# How to Run the Dynamic Pricing Agent 🚀

## Quick Start (5 minutes)

### Step 1: Navigate to Project
```bash
cd c:\Users\311205\Personal\DynamicPricingAgent
```

### Step 2: Initialize Database (First Time Only)
```bash
python database.py
```

**What it does:**
- Creates `pricing_poc.db` SQLite database
- Sets up 6 tables (products, agents, recommendations, etc.)
- Seeds 3 sample products (SKU001, SKU002, SKU003)
- Registers the inventory agent

**Output:**
```
✅ Database initialized at: pricing_poc.db
```

### Step 3: Run Tests (Optional but Recommended)
```bash
python test_demo.py
```

**What it does:**
- Tests database schema
- Tests all agents
- Tests math engine
- Tests pipeline
- Tests feedback system
- Generates sample recommendations

**Output:**
```
✅ ALL TESTS PASSED
```

### Step 4: Start API Server
```bash
python -m uvicorn app:app --reload --port 8000
```

**What it does:**
- Starts FastAPI server on http://localhost:8000
- Reloads automatically when you edit files

**Output:**
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## Using the System

### Option A: Interactive API Docs (Easiest for UI Testing)

1. **Open browser:**
   ```
   http://localhost:8000/docs
   ```

2. **You'll see all endpoints with "Try It Out" buttons**

3. **Common workflows:**

   **View pending recommendations:**
   - Click: GET `/api/pending`
   - Click: "Try It Out"
   - Click: "Execute"
   - See all pending recommendations

   **Approve a recommendation:**
   - Click: POST `/api/decision`
   - Click: "Try It Out"
   - Enter: `{"id": 1, "action": "APPROVED"}`
   - Click: "Execute"

   **Run pricing pipeline:**
   - Click: POST `/api/run-pipeline`
   - Click: "Try It Out"
   - Enter: `{"sku": "SKU001"}`
   - Click: "Execute"

---

### Option B: Command Line (curl)

**Get pending recommendations:**
```bash
curl http://localhost:8000/api/pending
```

**Run pipeline for SKU001:**
```bash
curl -X POST http://localhost:8000/api/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"sku": "SKU001"}'
```

**Approve recommendation ID 1:**
```bash
curl -X POST http://localhost:8000/api/decision \
  -H "Content-Type: application/json" \
  -d '{"id": 1, "action": "APPROVED"}'
```

**Check agent scores:**
```bash
curl http://localhost:8000/api/agent-scores
```

**See all products:**
```bash
curl http://localhost:8000/api/products
```

---

### Option C: Python Script

```python
from pipeline import run_pricing_pipeline
from feedback import FeedbackSystem

# 1. Run pipeline for a product
result = run_pricing_pipeline('SKU001')
print(f"Recommendation ID: {result['recommendation_id']}")

# 2. Approve the recommendation
decision = FeedbackSystem.process_human_decision(
    recommendation_id=result['recommendation_id'],
    action='APPROVED'
)
print(f"Decision: {decision['status']}")
```

---

## Full Workflow Example

### Step 1: Initialize
```bash
python database.py
```

### Step 2: Start API
```bash
python -m uvicorn app:app --reload --port 8000
```

### Step 3: Run in Another Terminal
```bash
# View products
curl http://localhost:8000/api/products | python -m json.tool

# Run pipeline for SKU001
curl -X POST http://localhost:8000/api/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"sku": "SKU001"}'

# View pending recommendations
curl http://localhost:8000/api/pending | python -m json.tool

# Approve recommendation (replace "id" with actual ID from pending)
curl -X POST http://localhost:8000/api/decision \
  -H "Content-Type: application/json" \
  -d '{"id": 1, "action": "APPROVED"}'

# Check updated agent scores
curl http://localhost:8000/api/agent-scores | python -m json.tool
```

---

## Testing Scenarios

### Scenario 1: Test Low Stock Alert
```bash
# Pipeline runs on SKU003 (only 8 units)
curl -X POST http://localhost:8000/api/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"sku": "SKU003"}'

# View recommendation (will show +8% surge pricing for low stock)
curl http://localhost:8000/api/pending | python -m json.tool
```

### Scenario 2: Test Overstock Discount
```bash
# Pipeline runs on SKU002 (400 units, target 200)
curl -X POST http://localhost:8000/api/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"sku": "SKU002"}'

# View recommendation (will show -10% discount)
curl http://localhost:8000/api/pending | python -m json.tool
```

### Scenario 3: Test Approval Feedback Loop
```bash
# Run pipeline
curl -X POST http://localhost:8000/api/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"sku": "SKU001"}' > /tmp/result.json

# Extract recommendation ID (e.g., 5)

# Approve it
curl -X POST http://localhost:8000/api/decision \
  -H "Content-Type: application/json" \
  -d '{"id": 5, "action": "APPROVED"}'

# Check agent score increased
curl http://localhost:8000/api/agent-scores | python -m json.tool
# human_trust_score should increase by +0.02
```

---

## Database Reset

If you need to start fresh:

```bash
# Delete the database
rm pricing_poc.db

# Recreate it
python database.py

# Verify
python -c "from database import get_connection; conn = get_connection(); print('✅ Database ready')"
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'fastapi'"
**Solution:**
```bash
pip install fastapi uvicorn pydantic
```

### Issue: "Cannot connect to http://localhost:8000"
**Solution:**
- Make sure API server is running in another terminal
- Check port 8000 is not in use
- Try different port: `uvicorn app:app --port 8001`

### Issue: "Database locked" error
**Solution:**
```bash
# Close all connections and restart
python database.py
```

### Issue: Unicode errors in test output
**Solution:**
```bash
python -c "import sys; sys.stdout.reconfigure(encoding='utf-8')" && python test_demo.py
```

---

## What Each Command Does

| Command | Purpose |
|---------|---------|
| `python database.py` | Initialize SQLite database with schema & sample data |
| `python test_demo.py` | Run comprehensive test suite (all components) |
| `python -m uvicorn app:app --reload` | Start FastAPI development server |
| `curl http://localhost:8000/docs` | Open interactive API documentation |
| `curl http://localhost:8000/api/pending` | Get all pending recommendations |
| `curl -X POST .../api/run-pipeline` | Trigger pricing pipeline |
| `curl -X POST .../api/decision` | Approve/reject recommendation |

---

## File Locations

```
c:\Users\311205\Personal\DynamicPricingAgent\
├── pricing_poc.db              # Database (auto-created by database.py)
├── database.py                 # Initialize DB
├── test_demo.py                # Run tests
├── app.py                       # FastAPI server
├── pipeline.py                 # Pricing engine
├── agents/                      # Agent implementations
├── feedback.py                 # Feedback system
└── ... (other files)
```

---

## Quick Reference

```bash
# All-in-one setup
python database.py && python test_demo.py

# Start server
python -m uvicorn app:app --reload

# In another terminal, test:
curl http://localhost:8000/health
curl http://localhost:8000/api/pending
curl -X POST http://localhost:8000/api/run-pipeline -H "Content-Type: application/json" -d '{"sku": "SKU001"}'
```

---

## Next Steps

1. ✅ Run `python database.py` to initialize
2. ✅ Run `python test_demo.py` to verify everything works
3. ✅ Run `python -m uvicorn app:app --reload` to start API
4. ✅ Open http://localhost:8000/docs to see interactive API
5. ✅ Create React dashboard to consume the API

---

**You're ready to go!** 🚀
