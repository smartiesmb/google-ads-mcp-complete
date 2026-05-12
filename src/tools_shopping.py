"""Shopping campaigns + Merchant Center linking + product partitioning."""

from typing import Any, Dict, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

from .utils import micros_to_currency

logger = structlog.get_logger(__name__)


class ShoppingTools:
    """Shopping campaigns + Merchant Center."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def list_merchant_center_links(self, customer_id: str) -> Dict[str, Any]:
        """List Merchant Center accounts linked to this Google Ads customer."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("MerchantCenterLinkService")
            response = service.list_merchant_center_links(customer_id=customer_id)
            links = []
            for link in response.merchant_center_links:
                links.append({
                    "id": str(link.id),
                    "merchant_center_account_id": str(link.id),
                    "status": str(link.status.name),
                    "merchant_center_account_name": str(link.merchant_center_account_name),
                    "resource_name": str(link.resource_name),
                })
            return {"success": True, "links": links, "count": len(links)}
        except GoogleAdsException as e:
            logger.error(f"Failed to list merchant center links: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def create_shopping_campaign(
        self,
        customer_id: str,
        name: str,
        budget_resource_name: str,
        merchant_id: int,
        country_code: str = "CH",
        is_standard: bool = False,
    ) -> Dict[str, Any]:
        """Create a Shopping campaign (Standard or Smart). Smart Shopping is being deprecated; prefer PMax."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("CampaignService")

            op = client.get_type("CampaignOperation")
            c = op.create
            c.name = name
            c.status = client.enums.CampaignStatusEnum.PAUSED
            c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SHOPPING
            if not is_standard:
                c.advertising_channel_sub_type = (
                    client.enums.AdvertisingChannelSubTypeEnum.SHOPPING_SMART_ADS
                )
            c.campaign_budget = budget_resource_name
            c.shopping_setting.merchant_id = merchant_id
            c.shopping_setting.sales_country = country_code

            response = service.mutate_campaigns(
                customer_id=customer_id, operations=[op]
            )
            resource = response.results[0].resource_name
            return {
                "success": True,
                "campaign_id": resource.split("/")[-1],
                "resource_name": resource,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to create shopping campaign: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def get_product_performance(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Per-product performance (shopping_performance_view)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    segments.product_item_id,
                    segments.product_title,
                    segments.product_brand,
                    segments.product_category_level1,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM shopping_performance_view
                WHERE segments.date DURING {date_range}
            """
            if campaign_id:
                query += f" AND campaign.id = {campaign_id}"
            response = service.search(customer_id=customer_id, query=query)
            products = []
            for row in response:
                products.append({
                    "product_id": str(row.segments.product_item_id),
                    "title": str(row.segments.product_title),
                    "brand": str(row.segments.product_brand),
                    "category": str(row.segments.product_category_level1),
                    "impressions": int(row.metrics.impressions),
                    "clicks": int(row.metrics.clicks),
                    "cost": round(micros_to_currency(row.metrics.cost_micros), 2),
                    "conversions": round(float(row.metrics.conversions), 2),
                    "conversions_value": round(float(row.metrics.conversions_value), 2),
                })
            return {"success": True, "products": products, "count": len(products)}
        except GoogleAdsException as e:
            logger.error(f"Failed to get product performance: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
