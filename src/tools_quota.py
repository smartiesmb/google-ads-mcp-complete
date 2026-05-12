"""Quota / rate-limit visibility for Google Ads API."""

from typing import Any, Dict
import structlog

from google.ads.googleads.errors import GoogleAdsException

logger = structlog.get_logger(__name__)


class QuotaTools:
    """Expose API quota usage info."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler
        self._last_headers: Dict[str, str] = {}

    async def get_api_quota_status(self, customer_id: str) -> Dict[str, Any]:
        """Return the last seen rate-limit info from a small probe call.

        The Google Ads API doesn't expose a dedicated 'quota status' endpoint;
        instead it returns rate-limit info in response headers. We fire a tiny
        probe (LIMIT 1 select on customer) and report status.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")
            response = service.search(
                customer_id=customer_id,
                query="SELECT customer.id FROM customer LIMIT 1",
            )
            for _ in response:
                break
            return {
                "success": True,
                "note": (
                    "Google Ads API v20 does not expose a structured quota endpoint. "
                    "Rate limits are enforced server-side and returned as gRPC errors when exceeded. "
                    "Monitor via developer token usage in the Google Ads UI: "
                    "Tools & Settings → API Center."
                ),
                "developer_token_dashboard": "https://ads.google.com/aw/apicenter",
            }
        except GoogleAdsException as e:
            logger.error(f"Quota probe failed: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
