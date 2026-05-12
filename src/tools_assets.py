"""Asset management tools for Google Ads API v21."""

from typing import Any, Dict, List, Optional
import base64
import structlog

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

logger = structlog.get_logger(__name__)


class AssetTools:
    """Asset management tools."""
    
    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler
        
    async def upload_image_asset(
        self,
        customer_id: str,
        image_data: str,
        name: str
    ) -> Dict[str, Any]:
        """Upload an image asset.
        
        Args:
            customer_id: The customer ID
            image_data: Base64 encoded image data or file path
            name: Name for the asset
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            asset_service = client.get_service("AssetService")
            
            # Create asset operation
            asset_operation = client.get_type("AssetOperation")
            asset = asset_operation.create
            
            # Set asset name
            asset.name = name
            
            # Handle image data (assume base64 encoded for now)
            try:
                # If it's a base64 string, decode it
                if image_data.startswith('data:image'):
                    # Remove data URL prefix
                    image_data = image_data.split(',')[1]
                
                image_bytes = base64.b64decode(image_data)
            except Exception:
                # If decoding fails, assume it's a file path and read it
                try:
                    with open(image_data, 'rb') as f:
                        image_bytes = f.read()
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to read image data: {str(e)}",
                        "error_type": "ValidationError"
                    }
            
            # Set image asset data
            asset.image_asset.data = image_bytes
            
            # Set asset type
            asset.type_ = client.enums.AssetTypeEnum.IMAGE
            
            # Create the asset
            response = asset_service.mutate_assets(
                customer_id=customer_id,
                operations=[asset_operation],
            )
            
            # Extract asset ID from response
            asset_resource_name = response.results[0].resource_name
            asset_id = asset_resource_name.split("/")[-1]
            
            logger.info(
                f"Uploaded image asset",
                customer_id=customer_id,
                asset_id=asset_id,
                name=name,
                size_bytes=len(image_bytes)
            )
            
            return {
                "success": True,
                "asset_id": asset_id,
                "asset_resource_name": asset_resource_name,
                "name": name,
                "type": "IMAGE",
                "size_bytes": len(image_bytes)
            }
            
        except GoogleAdsException as e:
            logger.error(f"Failed to upload image asset: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException"
            }
        except Exception as e:
            logger.error(f"Unexpected error uploading image asset: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "UnexpectedError"
            }
    
    async def upload_text_asset(
        self,
        customer_id: str,
        text: str,
        name: str
    ) -> Dict[str, Any]:
        """Create a text asset."""
        try:
            client = self.auth_manager.get_client(customer_id)
            asset_service = client.get_service("AssetService")
            
            # Create asset operation
            asset_operation = client.get_type("AssetOperation")
            asset = asset_operation.create
            
            # Set asset properties
            asset.name = name
            asset.text_asset.text = text
            asset.type_ = client.enums.AssetTypeEnum.TEXT
            
            # Create the asset
            response = asset_service.mutate_assets(
                customer_id=customer_id,
                operations=[asset_operation],
            )
            
            # Extract asset ID from response
            asset_resource_name = response.results[0].resource_name
            asset_id = asset_resource_name.split("/")[-1]
            
            logger.info(
                f"Created text asset",
                customer_id=customer_id,
                asset_id=asset_id,
                name=name,
                text_length=len(text)
            )
            
            return {
                "success": True,
                "asset_id": asset_id,
                "asset_resource_name": asset_resource_name,
                "name": name,
                "type": "TEXT",
                "text": text,
                "text_length": len(text)
            }
            
        except GoogleAdsException as e:
            logger.error(f"Failed to create text asset: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException"
            }
        except Exception as e:
            logger.error(f"Unexpected error creating text asset: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "UnexpectedError"
            }
    
    async def list_assets(
        self,
        customer_id: str,
        asset_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all assets with optional type filter."""
        try:
            client = self.auth_manager.get_client(customer_id)
            googleads_service = client.get_service("GoogleAdsService")
            
            # Build query
            query = """
                SELECT
                    asset.id,
                    asset.name,
                    asset.type,
                    asset.text_asset.text,
                    asset.image_asset.file_size
                FROM asset
            """
            
            # Add type filter if specified
            if asset_type:
                asset_type_upper = asset_type.upper()
                query += f" WHERE asset.type = {asset_type_upper}"
                
            response = googleads_service.search(
                customer_id=customer_id, query=query
            )
            
            assets = []
            for row in response:
                asset_data = {
                    "id": str(row.asset.id),
                    "name": str(row.asset.name) if row.asset.name else "",
                    "type": str(row.asset.type_.name)
                }
                
                # Add type-specific data
                if row.asset.type_.name == "TEXT" and hasattr(row.asset, 'text_asset'):
                    asset_data["text"] = str(row.asset.text_asset.text)
                    asset_data["text_length"] = len(row.asset.text_asset.text)
                elif row.asset.type_.name == "IMAGE" and hasattr(row.asset, 'image_asset'):
                    if hasattr(row.asset.image_asset, 'file_size'):
                        asset_data["file_size_bytes"] = row.asset.image_asset.file_size
                
                assets.append(asset_data)
            
            return {
                "success": True,
                "assets": assets,
                "count": len(assets),
                "filtered_by_type": asset_type is not None
            }
            
        except GoogleAdsException as e:
            logger.error(f"Failed to list assets: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException"
            }
        except Exception as e:
            logger.error(f"Unexpected error listing assets: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "UnexpectedError"
            }

    async def _remove_asset_link(
        self,
        customer_id: str,
        service_name: str,
        operation_type: str,
        resource_name: str,
        mutate_method: str
    ) -> Dict[str, Any]:
        """Internal helper: detach an asset link via a remove mutation."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service(service_name)
            operation = client.get_type(operation_type)
            operation.remove = resource_name

            response = getattr(service, mutate_method)(
                customer_id=customer_id,
                operations=[operation],
            )
            removed_resource = response.results[0].resource_name

            logger.info(
                "Removed asset link",
                customer_id=customer_id,
                service=service_name,
                resource_name=resource_name,
            )

            return {
                "success": True,
                "removed_resource_name": removed_resource,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to remove asset link ({service_name}): {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }
        except Exception as e:
            logger.error(f"Unexpected error removing asset link ({service_name}): {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "UnexpectedError",
            }

    async def remove_customer_asset(
        self,
        customer_id: str,
        asset_id: str,
        field_type: str
    ) -> Dict[str, Any]:
        """Detach an asset from the account level.

        Args:
            customer_id: The customer ID
            asset_id: The asset ID to detach
            field_type: The AssetFieldType (e.g. SITELINK, CALLOUT, DESCRIPTION,
                HEADLINE, CALL, STRUCTURED_SNIPPET, etc.). Required because
                CustomerAsset resource names embed the field type.
        """
        resource_name = (
            f"customers/{customer_id}/customerAssets/"
            f"{asset_id}~{field_type.upper()}"
        )
        return await self._remove_asset_link(
            customer_id=customer_id,
            service_name="CustomerAssetService",
            operation_type="CustomerAssetOperation",
            resource_name=resource_name,
            mutate_method="mutate_customer_assets",
        )

    async def remove_campaign_asset(
        self,
        customer_id: str,
        campaign_id: str,
        asset_id: str,
        field_type: str
    ) -> Dict[str, Any]:
        """Detach an asset from a campaign."""
        resource_name = (
            f"customers/{customer_id}/campaignAssets/"
            f"{campaign_id}~{asset_id}~{field_type.upper()}"
        )
        return await self._remove_asset_link(
            customer_id=customer_id,
            service_name="CampaignAssetService",
            operation_type="CampaignAssetOperation",
            resource_name=resource_name,
            mutate_method="mutate_campaign_assets",
        )

    async def remove_ad_group_asset(
        self,
        customer_id: str,
        ad_group_id: str,
        asset_id: str,
        field_type: str
    ) -> Dict[str, Any]:
        """Detach an asset from an ad group."""
        resource_name = (
            f"customers/{customer_id}/adGroupAssets/"
            f"{ad_group_id}~{asset_id}~{field_type.upper()}"
        )
        return await self._remove_asset_link(
            customer_id=customer_id,
            service_name="AdGroupAssetService",
            operation_type="AdGroupAssetOperation",
            resource_name=resource_name,
            mutate_method="mutate_ad_group_assets",
        )

    async def remove_asset_group_asset(
        self,
        customer_id: str,
        asset_group_id: str,
        asset_id: str,
        field_type: str
    ) -> Dict[str, Any]:
        """Detach an asset from a Performance Max asset group."""
        resource_name = (
            f"customers/{customer_id}/assetGroupAssets/"
            f"{asset_group_id}~{asset_id}~{field_type.upper()}"
        )
        return await self._remove_asset_link(
            customer_id=customer_id,
            service_name="AssetGroupAssetService",
            operation_type="AssetGroupAssetOperation",
            resource_name=resource_name,
            mutate_method="mutate_asset_group_assets",
        )

    async def create_lead_form_asset(
        self,
        customer_id: str,
        business_name: str,
        call_to_action: str,
        headline: str,
        description: str,
        privacy_policy_url: str,
        fields: list,
        post_submit_headline: str = "Merci !",
        post_submit_description: str = "Nous vous recontactons sous 24h.",
    ) -> dict:
        """Create a Lead Form asset.

        fields: list of dicts {'input_type': 'EMAIL'|'PHONE_NUMBER'|'FULL_NAME'|...}
        call_to_action: e.g. 'GET_QUOTE', 'BOOK_NOW', 'CONTACT_US', 'LEARN_MORE',
            'SUBSCRIBE', 'DOWNLOAD', 'APPLY_NOW', 'SIGN_UP', 'GET_OFFER'.
        """
        from google.ads.googleads.errors import GoogleAdsException
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("AssetService")
            op = client.get_type("AssetOperation")
            asset = op.create
            asset.type_ = client.enums.AssetTypeEnum.LEAD_FORM
            lf = asset.lead_form_asset
            lf.business_name = business_name
            lf.call_to_action_type = getattr(
                client.enums.LeadFormCallToActionTypeEnum, call_to_action
            )
            lf.headline = headline
            lf.description = description
            lf.privacy_policy_url = privacy_policy_url
            lf.post_submit_headline = post_submit_headline
            lf.post_submit_description = post_submit_description
            for f in fields:
                field = client.get_type("LeadFormField")
                field.input_type = getattr(
                    client.enums.LeadFormFieldUserInputTypeEnum, f["input_type"]
                )
                lf.fields.append(field)
            response = service.mutate_assets(customer_id=customer_id, operations=[op])
            return {
                "success": True,
                "asset_id": response.results[0].resource_name.split("/")[-1],
                "resource_name": response.results[0].resource_name,
            }
        except GoogleAdsException as e:
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def create_promotion_asset(
        self,
        customer_id: str,
        promotion_target: str,
        discount_modifier: str = "UP_TO",
        percent_off: float = 10.0,
        language_code: str = "fr",
        final_urls: list = None,
    ) -> dict:
        """Create a Promotion extension."""
        from google.ads.googleads.errors import GoogleAdsException
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("AssetService")
            op = client.get_type("AssetOperation")
            asset = op.create
            asset.type_ = client.enums.AssetTypeEnum.PROMOTION
            p = asset.promotion_asset
            p.promotion_target = promotion_target
            p.discount_modifier = getattr(
                client.enums.PromotionExtensionDiscountModifierEnum, discount_modifier
            )
            p.percent_off = int(percent_off * 1_000_000)
            p.language_code = language_code
            if final_urls:
                asset.final_urls.extend(final_urls)
            response = service.mutate_assets(customer_id=customer_id, operations=[op])
            return {
                "success": True,
                "asset_id": response.results[0].resource_name.split("/")[-1],
                "resource_name": response.results[0].resource_name,
            }
        except GoogleAdsException as e:
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def create_price_asset(
        self,
        customer_id: str,
        price_type: str,
        price_qualifier: str,
        language_code: str = "fr",
        offerings: list = None,
    ) -> dict:
        """Create a Price extension.

        price_type: SERVICES, SERVICE_CATEGORIES, BRANDS, PRODUCT_TIERS, ...
        offerings: list of dicts {'header','description','final_url','price_amount','currency_code','unit'}
        """
        from google.ads.googleads.errors import GoogleAdsException
        from .utils import currency_to_micros
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("AssetService")
            op = client.get_type("AssetOperation")
            asset = op.create
            asset.type_ = client.enums.AssetTypeEnum.PRICE
            pr = asset.price_asset
            pr.type_ = getattr(client.enums.PriceExtensionTypeEnum, price_type)
            pr.price_qualifier = getattr(
                client.enums.PriceExtensionPriceQualifierEnum, price_qualifier
            )
            pr.language_code = language_code
            for o in (offerings or []):
                off = client.get_type("PriceOffering")
                off.header = o["header"]
                off.description = o["description"]
                off.final_url = o["final_url"]
                off.price.amount_micros = currency_to_micros(o["price_amount"])
                off.price.currency_code = o.get("currency_code", "CHF")
                off.unit = getattr(
                    client.enums.PriceExtensionPriceUnitEnum, o.get("unit", "PER_MONTH")
                )
                pr.price_offerings.append(off)
            response = service.mutate_assets(customer_id=customer_id, operations=[op])
            return {
                "success": True,
                "asset_id": response.results[0].resource_name.split("/")[-1],
                "resource_name": response.results[0].resource_name,
            }
        except GoogleAdsException as e:
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
