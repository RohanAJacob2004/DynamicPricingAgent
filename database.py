"""
Database layer: SQLite schema initialization and connection management.
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime

DB_PATH = "pricing_poc.db"


def get_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # products: Base SKU metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            current_price REAL NOT NULL,
            cost_price REAL NOT NULL,
            stock_on_hand INTEGER NOT NULL,
            sales_velocity_7d REAL NOT NULL,
            optimal_stock_level INTEGER NOT NULL,
            days_to_reorder_arrival INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # agent_registry: Agent metadata and dynamic scores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_registry (
            agent_id TEXT PRIMARY KEY,
            human_trust_score REAL DEFAULT 0.5,
            market_performance_score REAL DEFAULT 0.5,
            is_active BOOLEAN DEFAULT 1,
            agent_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # recommendations: Pipeline execution runs awaiting human review
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            suggested_price REAL NOT NULL,
            suggested_modifier REAL NOT NULL,
            confidence REAL NOT NULL,
            justification TEXT NOT NULL,
            breakdown_matrix TEXT,
            status TEXT DEFAULT 'PENDING',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (sku) REFERENCES products(sku),
            FOREIGN KEY (agent_id) REFERENCES agent_registry(agent_id)
        )
    """)

    # pricing_ledger: Historical approved modifications
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pricing_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            applied_modifier REAL NOT NULL,
            applied_price REAL NOT NULL,
            margin_delta_3d REAL,
            volume_delta_3d REAL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            evaluated_at TIMESTAMP,
            FOREIGN KEY (sku) REFERENCES products(sku),
            FOREIGN KEY (agent_id) REFERENCES agent_registry(agent_id)
        )
    """)

    # feedback_cache: Stores negative examples for LLM prompt enhancement
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            context TEXT NOT NULL,
            negative_example TEXT NOT NULL,
            rejection_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agent_registry(agent_id)
        )
    """)

    conn.commit()
    conn.close()


def seed_sample_data():
    """Populate sample products and agents for testing."""
    conn = get_connection()
    cursor = conn.cursor()

    # Insert sample products
    sample_products = [
        ("SKU001", "Premium Widget", 29.99, 12.00, 150, 45.0, 100, 7),
        ("SKU002", "Standard Gadget", 19.99, 8.00, 50, 120.0, 200, 5),
        ("SKU003", "Deluxe Tool", 99.99, 40.00, 8, 2.0, 50, 10),
    ]

    for product in sample_products:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO products 
                (sku, product_name, current_price, cost_price, stock_on_hand, sales_velocity_7d, optimal_stock_level, days_to_reorder_arrival)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, product)
        except sqlite3.IntegrityError:
            pass

    # Insert sample agents
    sample_agents = [
        ("inventory_agent_v1", 0.5, 0.5, 1, "inventory"),
    ]

    for agent in sample_agents:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO agent_registry
                (agent_id, human_trust_score, market_performance_score, is_active, agent_type)
                VALUES (?, ?, ?, ?, ?)
            """, agent)
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_sample_data()
    print("✅ Database initialized at:", DB_PATH)
