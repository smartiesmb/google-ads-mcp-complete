"""Performance Max campaign & asset group management."""

from typing import Any, Dict, List, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

from .utils import micros_to_currency, currency_to_micros

logger = structlog.get_logger(__name__)


class PerformanceMaxTools:
    """Performance Max campaign + asset groups + signals + listing groups."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def create_pmax_campaign(
        self,
        customer_id: str,
        name: str,
        budget_resource_name: str,
        target_roas: Optional[float] = None,
        target_cpa_micros: Optional[int] = None,
        brand_guidelines_enabled: bool = False,
    ) -> Dict[str, Any]:
        """Create a Performance Max campaign in PAUSED status. Use either tROAS or tCPA, not both."""
        try:
            client = self.auth_manager.get_client(customer_id)
            campaign_service = client.get_service("CampaignService")

            op = client.get_type("CampaignOperation")
            c = op.create
            c.name = name
            c.status = client.enums.CampaignStatusEnum.PAUSED
            c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
            c.campaign_budget = budget_resource_name
            c.brand_guidelines_enabled = brand_guidelines_enabled
            c.contains_eu_political_advertising = (
                client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
            )

            if target_roas is not None:
                c.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSION_VALUE
                c.maximize_conversion_value.target_roas = target_roas
            elif target_cpa_micros is not None:
                c.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSIONS
                c.maximize_conversions.target_cpa_micros = target_cpa_micros
            else:
                c.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSIONS

            response = campaign_service.mutate_campaigns(
                customer_id=customer_id, operations=[op]
            )
            resource = response.results[0].resource_name
            return {
                "success": True,
                "campaign_id": resource.split("/")[-1],
                "resource_name": resource,
                "status": "PAUSED",
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to create PMax: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def create_asset_group(
        self,
        customer_id: str,
        campaign_id: str,
        name: str,
        final_urls: List[str],
        final_mobile_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create an asset group (the unit of organization in PMax)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("AssetGroupService")

            op = client.get_type("AssetGroupOperation")
            ag = op.create
            ag.name = name
            ag.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
            ag.status = client.enums.AssetGroupStatusEnum.PAUSED
            ag.final_urls.extend(final_urls)
            if final_mobile_urls:
                ag.final_mobile_urls.extend(final_mobile_urls)

            response = service.mutate_asset_groups(
                customer_id=customer_id, operations=[op]
            )
            resource = response.results[0].resource_name
            return {
                "success": True,
                "asset_group_id": resource.split("/")[-1],
                "resource_name": resource,
                "status": "PAUSED",
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to create asset group: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def add_asset_group_signal(
        self,
        customer_id: str,
        asset_group_id: str,
        signal_type: str,
        signal_value: str,
    ) -> Dict[str, Any]:
        """Add a search theme or audience signal to an asset group.

        signal_type: 'SEARCH_THEME' or 'AUDIENCE'
        signal_value: keyword text (for SEARCH_THEME) or audience resource name (for AUDIENCE)
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("AssetGroupSignalService")

            op = client.get_type("AssetGroupSignalOperation")
            s = op.create
            s.asset_group = f"customers/{customer_id}/assetGroups/{asset_group_id}"

            if signal_type == "SEARCH_THEME":
                s.search_theme.text = signal_value
            elif signal_type == "AUDIENCE":
                s.audience.audience = signal_value
            else:
                return {"success": False, "error": f"Unknown signal_type: {signal_type}"}

            response = service.mutate_asset_group_signals(
                customer_id=customer_id, operations=[op]
            )
            return {
                "success": True,
                "resource_name": response.results[0].resource_name,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to add asset group signal: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def link_asset_to_asset_group(
        self,
        customer_id: str,
        asset_group_id: str,
        asset_id: str,
        field_type: str,
    ) -> Dict[str, Any]:
        """Link an existing asset to an asset group with a field type.

        field_type values: HEADLINE, LONG_HEADLINE, DESCRIPTION, MARKETING_IMAGE,
            SQUARE_MARKETING_IMAGE, PORTRAIT_MARKETING_IMAGE, LOGO, LANDSCAPE_LOGO,
            YOUTUBE_VIDEO, BUSINESS_NAME, CALL_TO_ACTION_SELECTION.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("AssetGroupAssetService")
            op = client.get_type("AssetGroupAssetOperation")
            link = op.create
            link.asset_group = f"customers/{customer_id}/assetGroups/{asset_group_id}"
            link.asset = f"customers/{customer_id}/assets/{asset_id}"
            link.field_type = getattr(client.enums.AssetFieldTypeEnum, field_type)
            response = service.mutate_asset_group_assets(
                customer_id=customer_id, operations=[op]
            )
            return {"success": True, "resource_name": response.results[0].resource_name}
        except GoogleAdsException as e:
            logger.error(f"Failed to link asset to asset group: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def list_asset_groups(
        self, customer_id: str, campaign_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all asset groups (optionally filtered by campaign)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")
            query = """
                SELECT
                    asset_group.resource_name,
                    asset_group.id,
                    asset_group.name,
                    asset_group.status,
                    asset_group.final_urls,
                    asset_group.primary_status,
                    campaign.id,
                    campaign.name
                FROM asset_group
            """
            if campaign_id:
                query += f" WHERE campaign.id = {campaign_id}"
            response = service.search(customer_id=customer_id, query=query)
            groups = []
            for row in response:
                ag = row.asset_group
                groups.append({
                    "id": str(ag.id),
                    "name": str(ag.name),
                    "status": str(ag.status.name),
                    "primary_status": str(ag.primary_status.name),
                    "final_urls": list(ag.final_urls),
                    "campaign_id": str(row.campaign.id),
                    "campaign_name": str(row.campaign.name),
                    "resource_name": str(ag.resource_name),
                })
            return {"success": True, "asset_groups": groups, "count": len(groups)}
        except GoogleAdsException as e:
            logger.error(f"Failed to list asset groups: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
