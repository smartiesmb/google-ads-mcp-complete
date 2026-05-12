"""Segmentation tools: device, demographic, distance, click-level breakdowns."""

from typing import Any, Dict, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

from .utils import micros_to_currency

logger = structlog.get_logger(__name__)


class SegmentTools:
    """Device, demographic, distance, and click-level breakdowns."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def get_device_performance(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Performance broken down by device (MOBILE/DESKTOP/TABLET/CONNECTED_TV)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    segments.device,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value,
                    metrics.ctr,
                    metrics.average_cpc
                FROM campaign
                WHERE segments.date DURING {date_range}
            """
            if campaign_id:
                query += f" AND campaign.id = {campaign_id}"

            response = service.search(customer_id=customer_id, query=query)

            buckets: Dict[str, Dict[str, float]] = {}
            for row in response:
                device = str(row.segments.device.name)
                b = buckets.setdefault(
                    device,
                    {"clicks": 0, "impressions": 0, "cost": 0.0, "conversions": 0.0, "conv_value": 0.0},
                )
                b["clicks"] += int(row.metrics.clicks)
                b["impressions"] += int(row.metrics.impressions)
                b["cost"] += micros_to_currency(row.metrics.cost_micros)
                b["conversions"] += float(row.metrics.conversions)
                b["conv_value"] += float(row.metrics.conversions_value)

            devices = []
            for device, b in sorted(buckets.items(), key=lambda x: -x[1]["cost"]):
                devices.append({
                    "device": device,
                    "clicks": int(b["clicks"]),
                    "impressions": int(b["impressions"]),
                    "cost": round(b["cost"], 2),
                    "conversions": round(b["conversions"], 2),
                    "conversion_value": round(b["conv_value"], 2),
                    "ctr": f"{(b['clicks'] / b['impressions'] * 100):.2f}%" if b["impressions"] else "0.00%",
                    "cpa": round(b["cost"] / b["conversions"], 2) if b["conversions"] > 0 else None,
                })

            insights = []
            if devices:
                converters = [d for d in devices if d["conversions"] > 0]
                if converters:
                    best = max(converters, key=lambda d: d["conversions"])
                    insights.append(f"📱 Meilleur device: {best['device']} ({best['conversions']} conv, CPA {best['cpa']})")
                drains = [d for d in devices if d["cost"] >= 20 and d["conversions"] == 0]
                if drains:
                    insights.append(f"🚨 Devices qui consomment sans conv: {', '.join(d['device'] for d in drains)}")

            return {
                "success": True,
                "date_range": date_range,
                "devices": devices,
                "insights": insights,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to get device performance: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def get_demographic_performance(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Age + gender breakdown."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")

            age_query = f"""
                SELECT
                    age_range_view.resource_name,
                    ad_group_criterion.age_range.type,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions
                FROM age_range_view
                WHERE segments.date DURING {date_range}
            """
            gender_query = f"""
                SELECT
                    gender_view.resource_name,
                    ad_group_criterion.gender.type,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions
                FROM gender_view
                WHERE segments.date DURING {date_range}
            """
            if campaign_id:
                age_query += f" AND campaign.id = {campaign_id}"
                gender_query += f" AND campaign.id = {campaign_id}"

            def collect(query: str, label_attr: str) -> list:
                resp = service.search(customer_id=customer_id, query=query)
                out = []
                for r in resp:
                    crit_obj = getattr(r.ad_group_criterion, label_attr.split(".")[0])
                    out.append({
                        "label": str(getattr(crit_obj, label_attr.split(".")[1]).name),
                        "impressions": int(r.metrics.impressions),
                        "clicks": int(r.metrics.clicks),
                        "cost": round(micros_to_currency(r.metrics.cost_micros), 2),
                        "conversions": round(float(r.metrics.conversions), 2),
                    })
                return out

            ages = collect(age_query, "age_range.type")
            genders = collect(gender_query, "gender.type")

            insights = []
            converters_age = [a for a in ages if a["conversions"] > 0]
            if converters_age:
                best_age = max(converters_age, key=lambda a: a["conversions"])
                insights.append(f"👤 Top tranche d'âge: {best_age['label']} ({best_age['conversions']} conv)")
            converters_gender = [g for g in genders if g["conversions"] > 0]
            if converters_gender:
                best_gender = max(converters_gender, key=lambda g: g["conversions"])
                insights.append(f"⚧ Top genre: {best_gender['label']} ({best_gender['conversions']} conv)")

            return {
                "success": True,
                "date_range": date_range,
                "age_ranges": ages,
                "genders": genders,
                "insights": insights,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to get demographic performance: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def get_distance_performance(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Performance by user distance from business location."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    distance_view.distance_bucket,
                    distance_view.metric_system,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions
                FROM distance_view
                WHERE segments.date DURING {date_range}
            """
            if campaign_id:
                query += f" AND campaign.id = {campaign_id}"

            response = service.search(customer_id=customer_id, query=query)
            distances = []
            for row in response:
                distances.append({
                    "distance_bucket": str(row.distance_view.distance_bucket.name),
                    "metric_system": str(row.distance_view.metric_system.name),
                    "impressions": int(row.metrics.impressions),
                    "clicks": int(row.metrics.clicks),
                    "cost": round(micros_to_currency(row.metrics.cost_micros), 2),
                    "conversions": round(float(row.metrics.conversions), 2),
                })

            return {"success": True, "date_range": date_range, "distances": distances}
        except GoogleAdsException as e:
            logger.error(f"Failed to get distance performance: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def get_click_view(
        self,
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Click-level data (gclid, device, location, ad). Max 90 days back, 1 day at a time."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    click_view.gclid,
                    click_view.ad_group_ad,
                    click_view.area_of_interest.country,
                    click_view.location_of_presence.country,
                    segments.device,
                    segments.date,
                    campaign.id,
                    ad_group.id,
                    metrics.clicks
                FROM click_view
                WHERE segments.date DURING {date_range}
                LIMIT {limit}
            """
            response = service.search(customer_id=customer_id, query=query)
            clicks = []
            for row in response:
                clicks.append({
                    "gclid": str(row.click_view.gclid),
                    "date": str(row.segments.date),
                    "device": str(row.segments.device.name),
                    "campaign_id": str(row.campaign.id),
                    "ad_group_id": str(row.ad_group.id),
                    "country_interest": str(row.click_view.area_of_interest.country),
                    "country_presence": str(row.click_view.location_of_presence.country),
                })
            return {"success": True, "date_range": date_range, "clicks": clicks, "count": len(clicks)}
        except GoogleAdsException as e:
            logger.error(f"Failed to get click view: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
