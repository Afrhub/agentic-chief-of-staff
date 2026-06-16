import stripe
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class StripeAdapter:
    """Adapter for Stripe API integration.

    Wraps the synchronous Stripe SDK. The official `stripe` library (v7) is
    invoked by setting `stripe.api_key` per call rather than instantiating a
    client object — there is no `stripe.Stripe(...)` constructor.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_revenue_metrics(self, baseline_mrr: float = None, lookback_days: int = 1) -> dict:
        """
        Fetch MRR, churn count, and failed-payment metrics.

        Args:
            baseline_mrr: prior-sync MRR used to compute mrr_change_pct. If None,
                change is reported as 0 (first observation, nothing to compare to).

        Returns:
            {
                "mrr": float,
                "mrr_change_pct": float,   # negative = drop
                "churn_count": int,
                "failed_payments": int,
                "timestamp": datetime,
                "is_stale": bool,
            }
        """
        try:
            stripe.api_key = self.api_key
            start_time = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())

            # Active subscriptions → current MRR
            active = stripe.Subscription.list(status="active", limit=100)
            mrr = 0.0
            for sub in active.auto_paging_iter():
                for item in sub["items"]["data"]:
                    price = item.get("price") or {}
                    unit = price.get("unit_amount") or 0
                    qty = item.get("quantity", 1) or 1
                    mrr += (unit / 100.0) * qty

            # Canceled subscriptions in the window → churn count
            canceled = stripe.Subscription.list(
                status="canceled", limit=100, created={"gte": start_time}
            )
            churn_count = len(canceled.get("data", []))

            # Failed charges in the window
            failed = stripe.Charge.list(limit=100, created={"gte": start_time})
            failed_payment_count = sum(
                1 for c in failed.get("data", []) if c.get("status") == "failed"
            )

            mrr_change_pct = 0.0
            if baseline_mrr and baseline_mrr > 0:
                mrr_change_pct = ((mrr - baseline_mrr) / baseline_mrr) * 100.0

            return {
                "mrr": mrr,
                "mrr_change_pct": mrr_change_pct,
                "churn_count": churn_count,
                "failed_payments": failed_payment_count,
                "timestamp": datetime.utcnow(),
                "is_stale": False,
            }

        except Exception as e:
            logger.error(f"Stripe API error: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow(),
                "is_stale": True,
            }

    def get_high_value_customers(self, mrr_threshold: float = 500) -> list:
        """Fetch list of high-value customers for churn monitoring."""
        try:
            stripe.api_key = self.api_key
            high_value = []

            customers = stripe.Customer.list(limit=100)
            for customer in customers.get("data", []):
                subs = stripe.Subscription.list(customer=customer["id"], limit=1)
                if subs.get("data"):
                    item = subs["data"][0]["items"]["data"][0]
                    amount = (item.get("price", {}).get("unit_amount") or 0) / 100.0
                    if amount >= mrr_threshold:
                        high_value.append({
                            "customer_id": customer["id"],
                            "email": customer.get("email"),
                            "mrr": amount,
                        })

            return high_value

        except Exception as e:
            logger.error(f"Failed to fetch high-value customers: {e}")
            return []
