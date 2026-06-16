"""
FastAPI Application: REST endpoints for pipeline orchestration and human decision handling.
Phase 3: Connected Architecture (FastAPI to React)
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from database import init_db, seed_sample_data, get_connection
from pipeline import run_pricing_pipeline
from feedback import FeedbackSystem
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Dynamic Retail Pricing Agent",
    description="Multi-agent system for adaptive pricing",
    version="1.0.0"
)


# ============================================================================
# Pydantic Models (Request/Response Schemas)
# ============================================================================

class DecisionRequest(BaseModel):
    """Request schema for human decision on a recommendation."""
    id: int
    action: str  # 'APPROVED' or 'REJECTED'


class RecommendationResponse(BaseModel):
    """Response schema for a pending recommendation."""
    id: int
    sku: str
    agent_id: str
    suggested_price: float
    suggested_modifier: float
    confidence: float
    justification: str
    breakdown_matrix: str
    timestamp: str


class PipelineRequest(BaseModel):
    """Request schema to trigger pricing pipeline."""
    sku: str


# ============================================================================
# Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("Initializing database...")
    init_db()
    seed_sample_data()
    logger.info("✅ Database initialized")


# ============================================================================
# Phase 3: API Endpoints
# ============================================================================

@app.get("/api/pending")
async def get_pending_recommendations() -> List[RecommendationResponse]:
    """
    GET /api/pending: Retrieve all pending recommendations awaiting human review.

    Returns:
        List of pending recommendations with full breakdown and justifications.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, sku, agent_id, suggested_price, suggested_modifier, confidence,
                   justification, breakdown_matrix, timestamp
            FROM recommendations
            WHERE status = 'PENDING'
            ORDER BY timestamp DESC
        """)

        rows = cursor.fetchall()

        recommendations = [
            RecommendationResponse(
                id=row['id'],
                sku=row['sku'],
                agent_id=row['agent_id'],
                suggested_price=round(row['suggested_price'], 2),
                suggested_modifier=row['suggested_modifier'],
                confidence=row['confidence'],
                justification=row['justification'],
                breakdown_matrix=row['breakdown_matrix'] or '',
                timestamp=row['timestamp']
            )
            for row in rows
        ]

        return recommendations

    except Exception as e:
        logger.error(f"Error fetching recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recommendations")

    finally:
        conn.close()


@app.post("/api/decision")
async def post_decision(decision: DecisionRequest) -> Dict[str, Any]:
    """
    POST /api/decision: Manager makes a decision on a pending recommendation.

    Request body:
        {
            "id": 1,
            "action": "APPROVED" | "REJECTED"
        }

    Returns:
        Result of the decision processing with agent score updates.
    """
    if decision.action not in ['APPROVED', 'REJECTED']:
        raise HTTPException(
            status_code=400,
            detail="Action must be 'APPROVED' or 'REJECTED'"
        )

    result = FeedbackSystem.process_human_decision(decision.id, decision.action)

    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])

    logger.info(f"Decision processed: {decision.action} on recommendation {decision.id}")
    return result


@app.post("/api/run-pipeline")
async def run_pipeline(request: PipelineRequest) -> Dict[str, Any]:
    """
    POST /api/run-pipeline: Trigger the pricing pipeline for a specific SKU.

    Request body:
        {
            "sku": "SKU001"
        }

    Returns:
        Pipeline execution result including recommendation_id or error details.
    """
    logger.info(f"Running pipeline for SKU: {request.sku}")

    result = run_pricing_pipeline(request.sku)

    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])

    return {
        'sku': request.sku,
        'recommendation_id': result.get('recommendation_id'),
        'status': result.get('status', 'PENDING'),
        'applied_modifier': result.get('math_result', {}).get('applied_modifier'),
        'calculated_price': result.get('math_result', {}).get('calculated_price')
    }


@app.get("/api/agent-scores")
async def get_agent_scores() -> Dict[str, Dict[str, float]]:
    """
    GET /api/agent-scores: Retrieve current agent scores for monitoring/debugging.

    Returns:
        Dict mapping agent_id to human_trust_score and market_performance_score.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT agent_id, human_trust_score, market_performance_score, is_active
            FROM agent_registry
            ORDER BY agent_id
        """)

        rows = cursor.fetchall()

        agents = {}
        for row in rows:
            agents[row['agent_id']] = {
                'human_trust_score': row['human_trust_score'],
                'market_performance_score': row['market_performance_score'],
                'is_active': bool(row['is_active'])
            }

        return agents

    except Exception as e:
        logger.error(f"Error fetching agent scores: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch agent scores")

    finally:
        conn.close()


@app.post("/api/evaluate-performance")
async def evaluate_performance(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    POST /api/evaluate-performance: Manually trigger 3-day market performance evaluation.

    Returns:
        Summary of evaluation results and agent score updates.
    """
    logger.info("Starting 3-day performance evaluation...")

    result = FeedbackSystem.evaluate_3day_performance()

    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])

    logger.info(f"Evaluation complete: {result}")
    return result


@app.get("/api/products")
async def get_products() -> List[Dict[str, Any]]:
    """
    GET /api/products: Retrieve all products for reference.

    Returns:
        List of all products with current metadata.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT sku, product_name, current_price, cost_price, stock_on_hand,
                   sales_velocity_7d, optimal_stock_level
            FROM products
            ORDER BY sku
        """)

        rows = cursor.fetchall()

        products = [
            {
                'sku': row['sku'],
                'product_name': row['product_name'],
                'current_price': round(row['current_price'], 2),
                'cost_price': round(row['cost_price'], 2),
                'stock_on_hand': row['stock_on_hand'],
                'sales_velocity_7d': round(row['sales_velocity_7d'], 2),
                'optimal_stock_level': row['optimal_stock_level']
            }
            for row in rows
        ]

        return products

    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch products")

    finally:
        conn.close()


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy"}


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
