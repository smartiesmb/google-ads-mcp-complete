"""Video ads (YouTube) and Demand Gen campaigns."""

from typing import Any, Dict, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

logger = structlog.get_logger(__name__)


class VideoTools:
    """YouTube video ads + Demand Gen campaigns."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def create_video_campaign(
        self,
        customer_id: str,
        name: str,
        budget_resource_name: str,
        sub_type: str = "VIDEO_REACH",
    ) -> Dict[str, Any]:
        """Create a YouTube video campaign in PAUSED state.

        sub_type: VIDEO_REACH, VIDEO_OUTSTREAM, VIDEO_ACTION, VIDEO_NON_SKIPPABLE,
            VIDEO_SEQUENCE, VIDEO_EFFICIENT_REACH, VIDEO_VIEWS.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("CampaignService")

            op = client.get_type("CampaignOperation")
            c = op.create
            c.name = name
            c.status = client.enums.CampaignStatusEnum.PAUSED
            c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.VIDEO
            c.advertising_channel_sub_type = getattr(
                client.enums.AdvertisingChannelSubTypeEnum, sub_type
            )
            c.campaign_budget = budget_resource_name

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
            logger.error(f"Failed to create video campaign: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def create_demand_gen_campaign(
        self,
        customer_id: str,
        name: str,
        budget_resource_name: str,
    ) -> Dict[str, Any]:
        """Create a Demand Gen campaign (PAUSED)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("CampaignService")

            op = client.get_type("CampaignOperation")
            c = op.create
            c.name = name
            c.status = client.enums.CampaignStatusEnum.PAUSED
            c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.DEMAND_GEN
            c.campaign_budget = budget_resource_name

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
            logger.error(f"Failed to create demand gen: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def upload_youtube_video_asset(
        self, customer_id: str, youtube_video_id: str, name: str
    ) -> Dict[str, Any]:
        """Register a YouTube video as an asset for use in video/PMax campaigns."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("AssetService")

            op = client.get_type("AssetOperation")
            asset = op.create
            asset.name = name
            asset.type_ = client.enums.AssetTypeEnum.YOUTUBE_VIDEO
            asset.youtube_video_asset.youtube_video_id = youtube_video_id
            asset.youtube_video_asset.youtube_video_title = name

            response = service.mutate_assets(customer_id=customer_id, operations=[op])
            return {
                "success": True,
                "asset_id": response.results[0].resource_name.split("/")[-1],
                "resource_name": response.results[0].resource_name,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to upload video asset: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
