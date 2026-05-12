"""Asset performance tools (RSA headline/description performance labels)."""

from typing import Any, Dict, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

from .utils import micros_to_currency

logger = structlog.get_logger(__name__)


class AssetPerformanceTools:
    """Per-asset performance for RSA headlines & descriptions."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def get_asset_performance_report(
        self,
        customer_id: str,
        ad_group_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Get performance label (BEST/GOOD/LOW/PENDING) for each RSA asset."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    ad_group_ad_asset_view.field_type,
                    ad_group_ad_asset_view.performance_label,
                    ad_group_ad_asset_view.policy_summary.approval_status,
                    asset.text_asset.text,
                    asset.id,
                    ad_group_ad.ad.id,
                    ad_group.id,
                    ad_group.name,
                    campaign.id,
                    campaign.name,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions
                FROM ad_group_ad_asset_view
                WHERE segments.date DURING {date_range}
            """
            conditions = []
            if ad_group_id:
                conditions.append(f"ad_group.id = {ad_group_id}")
            if campaign_id:
                conditions.append(f"campaign.id = {campaign_id}")
            if conditions:
                query += " AND " + " AND ".join(conditions)

            response = service.search(customer_id=customer_id, query=query)

            assets = []
            label_counts: Dict[str, int] = {}
            for row in response:
                label = str(row.ad_group_ad_asset_view.performance_label.name)
                label_counts[label] = label_counts.get(label, 0) + 1
                assets.append({
                    "asset_id": str(row.asset.id),
                    "ad_id": str(row.ad_group_ad.ad.id),
                    "ad_group_id": str(row.ad_group.id),
                    "ad_group_name": str(row.ad_group.name),
                    "campaign_id": str(row.campaign.id),
                    "field_type": str(row.ad_group_ad_asset_view.field_type.name),
                    "performance_label": label,
                    "approval_status": str(
                        row.ad_group_ad_asset_view.policy_summary.approval_status.name
                    ),
                    "text": str(row.asset.text_asset.text),
                    "impressions": int(row.metrics.impressions),
                    "clicks": int(row.metrics.clicks),
                    "cost": round(micros_to_currency(row.metrics.cost_micros), 2),
                    "conversions": round(float(row.metrics.conversions), 2),
                })

            insights = [f"📊 {len(assets)} assets analysés"]
            for lbl, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
                insights.append(f"  • {lbl}: {cnt}")
            low_assets = [a for a in assets if a["performance_label"] == "LOW"]
            if low_assets:
                insights.append(
                    f"🚨 {len(low_assets)} asset(s) en LOW — candidats au remplacement"
                )

            return {
                "success": True,
                "date_range": date_range,
                "total_assets": len(assets),
                "label_breakdown": label_counts,
                "assets": assets,
                "insights": insights,
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to get asset performance: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }
