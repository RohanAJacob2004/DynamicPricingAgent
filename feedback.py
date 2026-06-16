"""
Dual-Loop Feedback System: Updates agent scores based on human decisions and market performance.
"""
from datetime import datetime, timedelta
from database import get_connection
from typing import Dict, Any


class FeedbackSystem:
    """Manages both human feedback loop (immediate) and market performance loop (3-day)."""

    # Tuning parameters
    HUMAN_APPROVAL_DELTA = 0.02  # +0.02 for approval
    HUMAN_REJECTION_DELTA = -0.05  # -0.05 for rejection
    MARKET_SUCCESS_DELTA = 0.03  # +0.03 for successful outcome
    MARKET_FAILURE_DELTA = -0.04  # -0.04 for failed outcome

    @staticmethod
    def process_human_decision(recommendation_id: int, action: str) -> Dict[str, Any]:
        """
        Phase 4.1: Process explicit human feedback (Immediate Loop A).

        Args:
            recommendation_id: ID of the recommendation being approved/rejected
            action: 'APPROVED' or 'REJECTED'

        Returns:
            Dict with update status
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Fetch the recommendation
            cursor.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,))
            rec_row = cursor.fetchone()

            if not rec_row:
                return {'error': f'Recommendation {recommendation_id} not found'}

            agent_id = rec_row['agent_id']
            sku = rec_row['sku']
            suggested_price = rec_row['suggested_price']
            suggested_modifier = rec_row['suggested_modifier']

            # Update recommendation status
            cursor.execute(
                "UPDATE recommendations SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
                (action, recommendation_id)
            )

            if action == 'APPROVED':
                # Update product current_price
                cursor.execute(
                    "UPDATE products SET current_price = ? WHERE sku = ?",
                    (suggested_price, sku)
                )

                # Log to pricing_ledger
                cursor.execute("""
                    INSERT INTO pricing_ledger
                    (sku, agent_id, applied_modifier, applied_price)
                    VALUES (?, ?, ?, ?)
                """, (sku, agent_id, suggested_modifier, suggested_price))

                # Increment human_trust_score
                FeedbackSystem._update_agent_score(
                    cursor, agent_id, 'human_trust_score', FeedbackSystem.HUMAN_APPROVAL_DELTA
                )

                conn.commit()
                return {
                    'status': 'APPROVED',
                    'agent_id': agent_id,
                    'trust_delta': FeedbackSystem.HUMAN_APPROVAL_DELTA,
                    'new_price': suggested_price
                }

            elif action == 'REJECTED':
                # Decrement human_trust_score
                FeedbackSystem._update_agent_score(
                    cursor, agent_id, 'human_trust_score', FeedbackSystem.HUMAN_REJECTION_DELTA
                )

                conn.commit()
                return {
                    'status': 'REJECTED',
                    'agent_id': agent_id,
                    'trust_delta': FeedbackSystem.HUMAN_REJECTION_DELTA
                }

            else:
                return {'error': f'Invalid action: {action}'}

        except Exception as e:
            conn.rollback()
            return {'error': f'Failed to process decision: {str(e)}'}
        finally:
            conn.close()

    @staticmethod
    def _update_agent_score(cursor, agent_id: str, score_column: str, delta: float) -> None:
        """Helper to update an agent's score and clamp to [0.0, 1.0]."""
        cursor.execute(
            f"SELECT {score_column} FROM agent_registry WHERE agent_id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()

        if row:
            current_score = row[score_column]
            new_score = max(0.0, min(1.0, current_score + delta))  # Clamp to [0, 1]

            cursor.execute(
                f"UPDATE agent_registry SET {score_column} = ? WHERE agent_id = ?",
                (new_score, agent_id)
            )

    @staticmethod
    def evaluate_3day_performance() -> Dict[str, Any]:
        """
        Phase 4.2: Evaluate market performance for recommendations approved 72 hours ago.

        Returns:
            Dict with evaluation summary and updated scores.
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Find recommendations applied exactly ~72 hours ago
        three_days_ago = datetime.now() - timedelta(days=3)

        try:
            cursor.execute("""
                SELECT pl.id, pl.sku, pl.agent_id, pl.applied_modifier, pl.applied_price,
                       p.sales_velocity_7d, p.stock_on_hand, p.cost_price
                FROM pricing_ledger pl
                JOIN products p ON pl.sku = p.sku
                WHERE pl.evaluated_at IS NULL
                AND pl.applied_at <= ?
                ORDER BY pl.applied_at DESC
            """, (three_days_ago.isoformat(),))

            ledger_rows = cursor.fetchall()

            update_summary = {
                'evaluated_count': len(ledger_rows),
                'successful_outcomes': 0,
                'failed_outcomes': 0,
                'agent_updates': {}
            }

            for ledger_row in ledger_rows:
                ledger_id = ledger_row['id']
                agent_id = ledger_row['agent_id']
                applied_modifier = ledger_row['applied_modifier']
                stock_on_hand = ledger_row['stock_on_hand']
                sales_velocity = ledger_row['sales_velocity_7d']

                # Evaluate outcome based on modifier logic
                success = FeedbackSystem._evaluate_market_outcome(
                    applied_modifier, stock_on_hand, sales_velocity
                )

                if success:
                    FeedbackSystem._update_agent_score(
                        cursor, agent_id, 'market_performance_score', FeedbackSystem.MARKET_SUCCESS_DELTA
                    )
                    update_summary['successful_outcomes'] += 1
                else:
                    FeedbackSystem._update_agent_score(
                        cursor, agent_id, 'market_performance_score', FeedbackSystem.MARKET_FAILURE_DELTA
                    )
                    update_summary['failed_outcomes'] += 1

                # Mark as evaluated
                cursor.execute(
                    "UPDATE pricing_ledger SET evaluated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (ledger_id,)
                )

                if agent_id not in update_summary['agent_updates']:
                    update_summary['agent_updates'][agent_id] = []

                update_summary['agent_updates'][agent_id].append({
                    'ledger_id': ledger_id,
                    'outcome': 'SUCCESS' if success else 'FAILURE'
                })

            conn.commit()
            return update_summary

        except Exception as e:
            conn.rollback()
            return {'error': f'Evaluation failed: {str(e)}'}
        finally:
            conn.close()

    @staticmethod
    def _evaluate_market_outcome(
        applied_modifier: float,
        stock_on_hand: int,
        sales_velocity: float
    ) -> bool:
        """
        Deterministic evaluation of market outcome.

        Logic:
        - If discount applied (-X%), check if sales velocity increased (success = velocity > threshold)
        - If surge applied (+X%), check if margin delta was positive (success = stock held without velocity collapse)
        """
        if applied_modifier < -0.01:  # Discount scenario
            # Success: sales accelerated (simplified: velocity > 2)
            return sales_velocity > 2.0
        elif applied_modifier > 0.01:  # Surge scenario
            # Success: stock level improved or maintained (simplified: stock not critically low)
            return stock_on_hand > 10
        else:
            # Neutral modification; always successful
            return True
