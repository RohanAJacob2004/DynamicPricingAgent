"""
LangGraph Pipeline: Orchestrates the multi-agent workflow.
Implements Phase 2: Data Fetcher → Parallel Agents → Weight Optimizer → Math Engine → Sync
"""
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from database import get_connection
from agents import InventoryAgent
from math_engine import DeterministicMathEngine
import json


# Shared state schema for the LangGraph
class PricingState:
    """Represents the state flowing through the LangGraph pipeline."""

    def __init__(self):
        self.sku = None
        self.product_data = None
        self.agent_scores = None
        self.system_metrics = None
        self.agent_recommendations = []
        self.runtime_weights = {}
        self.math_result = {}


def create_pricing_pipeline():
    """
    Construct the LangGraph pipeline with all nodes.
    Returns a runnable graph.
    """
    workflow = StateGraph(dict)

    # Define nodes
    workflow.add_node("data_fetcher", node_data_fetcher)
    workflow.add_node("inventory_agent", node_inventory_agent)
    workflow.add_node("weight_optimizer", node_weight_optimizer)
    workflow.add_node("math_engine", node_math_engine)
    workflow.add_node("sync_db", node_sync_db)

    # Define edges: linear pipeline
    workflow.set_entry_point("data_fetcher")
    workflow.add_edge("data_fetcher", "inventory_agent")
    workflow.add_edge("inventory_agent", "weight_optimizer")
    workflow.add_edge("weight_optimizer", "math_engine")
    workflow.add_edge("math_engine", "sync_db")
    workflow.add_edge("sync_db", END)

    return workflow.compile()


def node_data_fetcher(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 2.1: Data Fetcher Node
    Load core system states and agent registry scores.
    """
    sku = state.get('sku')

    if not sku:
        state['error'] = 'SKU not provided'
        return state

    conn = get_connection()
    cursor = conn.cursor()

    # Fetch product data
    cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
    product_row = cursor.fetchone()

    if not product_row:
        conn.close()
        state['error'] = f'Product {sku} not found'
        return state

    product_data = dict(product_row)

    # Fetch agent scores
    cursor.execute("SELECT agent_id, human_trust_score, market_performance_score FROM agent_registry WHERE is_active = 1")
    agent_rows = cursor.fetchall()

    agent_scores = {}
    for agent_row in agent_rows:
        agent_id = agent_row['agent_id']
        agent_scores[agent_id] = {
            'human_trust_score': agent_row['human_trust_score'],
            'market_performance_score': agent_row['market_performance_score']
        }

    conn.close()

    # Build system metrics
    stock_percentage = (product_data['stock_on_hand'] / product_data['optimal_stock_level']) * 100
    system_metrics = {
        'stock_percentage': stock_percentage,
        'critical_stock': stock_percentage < 10,
        'low_stock': stock_percentage < 30,
        'overstocked': stock_percentage > 150
    }

    state['sku'] = sku
    state['product_data'] = product_data
    state['agent_scores'] = agent_scores
    state['system_metrics'] = system_metrics

    return state


def node_inventory_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 2.2: Inventory Agent Node (Parallel Layer)
    Analyzes internal inventory signals.
    """
    if 'error' in state:
        return state

    agent = InventoryAgent(agent_id="inventory_agent_v1")

    try:
        recommendation = agent.analyze(state['product_data'], state['system_metrics'])
        state['agent_recommendations'].append(recommendation.to_dict())
    except Exception as e:
        state['agent_error'] = f"Inventory agent failed: {str(e)}"

    return state


def node_weight_optimizer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 2.3: Weight Optimization Node
    Calculate runtime weights based on agent scores and system state.
    """
    if 'error' in state or not state.get('agent_scores'):
        return state

    runtime_weights = DeterministicMathEngine.calculate_runtime_weights(
        state['agent_scores'],
        state['system_metrics']
    )

    state['runtime_weights'] = runtime_weights

    return state


def node_math_engine(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 2.4: Deterministic Math Engine Node
    Execute weighted formula and guardrails.
    """
    if 'error' in state or not state.get('agent_recommendations'):
        state['error'] = 'No recommendations to process'
        return state

    math_result = DeterministicMathEngine.aggregate_recommendations(
        agent_recommendations=state['agent_recommendations'],
        runtime_weights=state['runtime_weights'],
        base_price=state['product_data']['current_price'],
        cost_price=state['product_data']['cost_price']
    )

    state['math_result'] = math_result

    return state


def node_sync_db(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 2.5: FastAPI/SQLite Sync Node
    Persist recommendation to database awaiting human review.
    """
    if 'error' in state or not state.get('math_result'):
        return state

    conn = get_connection()
    cursor = conn.cursor()

    sku = state['sku']
    agent_recommendations = state['agent_recommendations']
    math_result = state['math_result']

    # Use the first agent's data for now (only inventory agent)
    primary_rec = agent_recommendations[0] if agent_recommendations else {}
    agent_id = primary_rec.get('agent_id', 'unknown')
    rationale = primary_rec.get('rationale', 'No rationale provided')

    # Format breakdown matrix
    breakdown_matrix = DeterministicMathEngine.format_breakdown_matrix(
        math_result.get('breakdown', [])
    )

    try:
        cursor.execute("""
            INSERT INTO recommendations
            (sku, agent_id, suggested_price, suggested_modifier, confidence, justification, breakdown_matrix, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sku,
            agent_id,
            math_result.get('final_price', math_result.get('calculated_price', state['product_data']['current_price'])),
            math_result.get('applied_modifier', 0.0),
            primary_rec.get('confidence', 0.5),
            rationale,
            breakdown_matrix,
            'PENDING'
        ))

        conn.commit()
        rec_id = cursor.lastrowid

        state['recommendation_id'] = rec_id
        state['status'] = 'PENDING'

    except Exception as e:
        state['db_error'] = f"Failed to save recommendation: {str(e)}"
    finally:
        conn.close()

    return state


def run_pricing_pipeline(sku: str) -> Dict[str, Any]:
    """
    Execute the complete pricing pipeline for a single SKU.

    Args:
        sku: The SKU to process

    Returns:
        Final state dict with recommendation_id or error details
    """
    graph = create_pricing_pipeline()

    initial_state = {
        'sku': sku,
        'product_data': None,
        'agent_scores': None,
        'system_metrics': None,
        'agent_recommendations': [],
        'runtime_weights': {},
        'math_result': {}
    }

    final_state = graph.invoke(initial_state)

    return final_state
