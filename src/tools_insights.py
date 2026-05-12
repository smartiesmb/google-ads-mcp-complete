"""Insights tools for Google Ads API v20.

Maps to the "Insights & rapports" section of the Google Ads UI:
- Auction Insights (competitive landscape)
- Recommendations (optimization score) + apply/dismiss
- Landing Page Report
- Search Term Clusters
- Hourly / Day-of-week performance
- Change History
"""

from typing import Any, Dict, List, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

from .utils import micros_to_currency

logger = structlog.get_logger(__name__)


class InsightsTools:
    """Insights and competitive intelligence tools."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    # ------------------------------------------------------------------
    # AUCTION INSIGHTS
    # ------------------------------------------------------------------
    async def get_auction_insights(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        ad_group_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Get auction/impression-share insights for a campaign or ad group.

        IMPORTANT: Google Ads API v20 does NOT expose per-competitor domain
        breakdown via the search service (it remains UI-only). This tool returns
        the next-best thing: your own impression share metrics + a precise
        diagnosis of WHY you lose impressions (rank vs budget, top vs anywhere).

        Returns:
            search_impression_share, search_rank_lost_impression_share,
            search_budget_lost_impression_share, plus the top/absolute_top
            variants — and an actionable diagnosis.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            googleads_service = client.get_service("GoogleAdsService")

            resource = "ad_group" if ad_group_id else "campaign"
            query = f"""
                SELECT
                    {resource}.id,
                    {resource}.name,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.search_impression_share,
                    metrics.search_top_impression_share,
                    metrics.search_absolute_top_impression_share,
                    metrics.search_rank_lost_impression_share,
                    metrics.search_rank_lost_top_impression_share,
                    metrics.search_rank_lost_absolute_top_impression_share,
                    metrics.search_budget_lost_impression_share,
                    metrics.search_budget_lost_top_impression_share,
                    metrics.search_budget_lost_absolute_top_impression_share
                FROM {resource}
                WHERE segments.date DURING {date_range}
            """

            if ad_group_id:
                query += f" AND ad_group.id = {ad_group_id}"
            elif campaign_id:
                query += f" AND campaign.id = {campaign_id}"

            response = googleads_service.search(
                customer_id=customer_id, query=query
            )

            rows = []
            for row in response:
                obj = getattr(row, resource)

                def pct(v):
                    try:
                        return round(float(v or 0) * 100, 2)
                    except Exception:
                        return 0.0

                entry = {
                    "id": str(obj.id),
                    "name": str(obj.name),
                    "impressions": int(row.metrics.impressions),
                    "clicks": int(row.metrics.clicks),
                    "cost": round(micros_to_currency(row.metrics.cost_micros), 2),
                    "share": {
                        "impression_share": pct(row.metrics.search_impression_share),
                        "top_impression_share": pct(row.metrics.search_top_impression_share),
                        "absolute_top_impression_share": pct(
                            row.metrics.search_absolute_top_impression_share
                        ),
                    },
                    "lost_to_rank": {
                        "any": pct(row.metrics.search_rank_lost_impression_share),
                        "top": pct(row.metrics.search_rank_lost_top_impression_share),
                        "absolute_top": pct(
                            row.metrics.search_rank_lost_absolute_top_impression_share
                        ),
                    },
                    "lost_to_budget": {
                        "any": pct(row.metrics.search_budget_lost_impression_share),
                        "top": pct(row.metrics.search_budget_lost_top_impression_share),
                        "absolute_top": pct(
                            row.metrics.search_budget_lost_absolute_top_impression_share
                        ),
                    },
                }
                rows.append(entry)

            # Diagnostic
            insights = []
            if rows:
                # Sum / average across rows (works for single campaign/ad_group too)
                imp_share = sum(r["share"]["impression_share"] for r in rows) / len(rows)
                lost_rank = sum(r["lost_to_rank"]["any"] for r in rows) / len(rows)
                lost_budget = sum(r["lost_to_budget"]["any"] for r in rows) / len(rows)

                insights.append(
                    f"📊 Part d'impressions: {imp_share:.1f}% (max théorique 100%)"
                )
                insights.append(
                    f"📉 Perdues par rang Ad Rank: {lost_rank:.1f}%  •  "
                    f"Perdues par budget: {lost_budget:.1f}%"
                )

                if lost_rank > lost_budget * 2 and lost_rank > 20:
                    insights.append(
                        "🚨 Diagnostic: vous perdez beaucoup plus d'impressions à cause du **rang** que du budget. "
                        "Leviers prioritaires: Quality Score (CTR + Landing Page Exp + Ad Relevance), "
                        "ou enchères plus agressives."
                    )
                elif lost_budget > lost_rank * 2 and lost_budget > 20:
                    insights.append(
                        "🚨 Diagnostic: vous perdez par **budget**. Levier: augmenter le budget journalier."
                    )
                elif lost_rank > 30 and lost_budget > 30:
                    insights.append(
                        "⚠️ Diagnostic: pertes mixtes rang + budget — agir sur les deux fronts."
                    )
                elif imp_share > 80:
                    insights.append(
                        "✅ Couverture impression share élevée — peu de place pour scale en volume."
                    )

                insights.append(
                    "ℹ️ Note: la liste des domaines concurrents (UI 'Insights sur les enchères') "
                    "n'est PAS disponible via l'API Google Ads v20 — UI uniquement."
                )

            return {
                "success": True,
                "date_range": date_range,
                "scope": {
                    "campaign_id": campaign_id,
                    "ad_group_id": ad_group_id,
                    "level": resource,
                },
                "rows": rows,
                "insights": insights,
                "api_limitation": (
                    "Per-competitor domain breakdown is UI-only in Google Ads API v20. "
                    "This endpoint returns your own impression share + loss diagnosis."
                ),
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to get auction insights: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }

    # ------------------------------------------------------------------
    # RECOMMENDATIONS
    # ------------------------------------------------------------------
    async def get_recommendations(
        self,
        customer_id: str,
        recommendation_types: Optional[List[str]] = None,
        include_dismissed: bool = False,
    ) -> Dict[str, Any]:
        """Get all active recommendations for the account.

        Same data as the "Recommandations" panel (score d'optimisation).
        Each recommendation includes its type, impact, and resource_name to
        feed into apply_recommendation / dismiss_recommendation.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            googleads_service = client.get_service("GoogleAdsService")

            query = """
                SELECT
                    recommendation.resource_name,
                    recommendation.type,
                    recommendation.dismissed,
                    recommendation.impact.base_metrics.impressions,
                    recommendation.impact.base_metrics.clicks,
                    recommendation.impact.base_metrics.cost_micros,
                    recommendation.impact.base_metrics.conversions,
                    recommendation.impact.potential_metrics.impressions,
                    recommendation.impact.potential_metrics.clicks,
                    recommendation.impact.potential_metrics.cost_micros,
                    recommendation.impact.potential_metrics.conversions,
                    recommendation.campaign,
                    recommendation.ad_group
                FROM recommendation
            """

            conditions = []
            if not include_dismissed:
                conditions.append("recommendation.dismissed = FALSE")
            if recommendation_types:
                type_list = ", ".join(f"'{t}'" for t in recommendation_types)
                conditions.append(f"recommendation.type IN ({type_list})")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            response = googleads_service.search(
                customer_id=customer_id, query=query
            )

            recommendations = []
            type_counts: Dict[str, int] = {}

            for row in response:
                rec_type = str(row.recommendation.type.name)
                type_counts[rec_type] = type_counts.get(rec_type, 0) + 1

                base = row.recommendation.impact.base_metrics
                potential = row.recommendation.impact.potential_metrics

                # Compute deltas where data is present
                delta_clicks = int(potential.clicks - base.clicks)
                delta_conversions = float(potential.conversions - base.conversions)
                delta_cost = micros_to_currency(potential.cost_micros - base.cost_micros)

                recommendations.append(
                    {
                        "resource_name": str(row.recommendation.resource_name),
                        "recommendation_id": str(row.recommendation.resource_name).split("/")[-1],
                        "type": rec_type,
                        "dismissed": bool(row.recommendation.dismissed),
                        "campaign": str(row.recommendation.campaign) or None,
                        "ad_group": str(row.recommendation.ad_group) or None,
                        "impact": {
                            "delta_clicks": delta_clicks,
                            "delta_conversions": round(delta_conversions, 2),
                            "delta_cost": round(delta_cost, 2),
                        },
                    }
                )

            insights = [
                f"📋 {len(recommendations)} recommandation(s) active(s)",
            ]
            for rec_type, count in sorted(
                type_counts.items(), key=lambda x: -x[1]
            )[:5]:
                insights.append(f"  • {rec_type}: {count}")

            return {
                "success": True,
                "total": len(recommendations),
                "type_breakdown": type_counts,
                "recommendations": recommendations,
                "insights": insights,
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to get recommendations: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }

    async def apply_recommendation(
        self,
        customer_id: str,
        recommendation_resource_name: str,
    ) -> Dict[str, Any]:
        """Apply a recommendation by its full resource name.

        Example resource_name: 'customers/1234567890/recommendations/ABC123'
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            recommendation_service = client.get_service("RecommendationService")

            operation = client.get_type("ApplyRecommendationOperation")
            operation.resource_name = recommendation_resource_name

            response = recommendation_service.apply_recommendation(
                customer_id=customer_id,
                operations=[operation],
            )

            applied = [str(r.resource_name) for r in response.results]

            return {
                "success": True,
                "applied_recommendations": applied,
                "count": len(applied),
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to apply recommendation: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }

    async def dismiss_recommendation(
        self,
        customer_id: str,
        recommendation_resource_name: str,
    ) -> Dict[str, Any]:
        """Dismiss a recommendation (hide it from the optimization score)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            recommendation_service = client.get_service("RecommendationService")

            operation = client.get_type("DismissRecommendationOperation")
            operation.resource_name = recommendation_resource_name

            response = recommendation_service.dismiss_recommendation(
                customer_id=customer_id,
                operations=[operation],
            )

            dismissed = [str(r.resource_name) for r in response.results]

            return {
                "success": True,
                "dismissed_recommendations": dismissed,
                "count": len(dismissed),
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to dismiss recommendation: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }

    # ------------------------------------------------------------------
    # LANDING PAGE REPORT
    # ------------------------------------------------------------------
    async def get_landing_page_report(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
        min_impressions: int = 1,
    ) -> Dict[str, Any]:
        """Get landing page performance report.

        Same as UI 'Pages de destination' — clicks, conversions, mobile-friendliness,
        and valid AMP rate per final URL.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            googleads_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    landing_page_view.unexpanded_final_url,
                    metrics.clicks,
                    metrics.impressions,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value,
                    metrics.ctr,
                    metrics.average_cpc,
                    metrics.mobile_friendly_clicks_percentage,
                    metrics.valid_accelerated_mobile_pages_clicks_percentage
                FROM landing_page_view
                WHERE segments.date DURING {date_range}
                  AND metrics.impressions >= {min_impressions}
            """

            if campaign_id:
                query += f" AND campaign.id = {campaign_id}"

            query += " ORDER BY metrics.cost_micros DESC"

            response = googleads_service.search(
                customer_id=customer_id, query=query
            )

            pages = []
            total_cost = 0.0
            total_conv = 0.0

            for row in response:
                cost = micros_to_currency(row.metrics.cost_micros)
                conversions = float(row.metrics.conversions)
                clicks = int(row.metrics.clicks)
                conv_value = float(row.metrics.conversions_value)

                total_cost += cost
                total_conv += conversions

                pages.append(
                    {
                        "final_url": str(row.landing_page_view.unexpanded_final_url),
                        "clicks": clicks,
                        "impressions": int(row.metrics.impressions),
                        "cost": round(cost, 2),
                        "conversions": round(conversions, 2),
                        "conversion_value": round(conv_value, 2),
                        "ctr": f"{(row.metrics.ctr or 0) * 100:.2f}%",
                        "avg_cpc": round(micros_to_currency(row.metrics.average_cpc), 2),
                        "cpa": round(cost / conversions, 2) if conversions > 0 else None,
                        "conversion_rate": (
                            f"{conversions / clicks * 100:.2f}%" if clicks > 0 else "0.00%"
                        ),
                        "mobile_friendly_pct": round(
                            float(row.metrics.mobile_friendly_clicks_percentage or 0) * 100, 2
                        ),
                        "valid_amp_pct": round(
                            float(row.metrics.valid_accelerated_mobile_pages_clicks_percentage or 0)
                            * 100,
                            2,
                        ),
                    }
                )

            # Insights
            insights = []
            if pages:
                best = max(pages, key=lambda p: p["conversions"])
                worst = max(
                    (p for p in pages if p["cost"] > 10 and p["conversions"] == 0),
                    key=lambda p: p["cost"],
                    default=None,
                )
                insights.append(
                    f"🏆 Meilleure LP en conv: {best['final_url']} ({best['conversions']} conv / {best['cost']} CHF)"
                )
                if worst:
                    insights.append(
                        f"🚨 LP qui consomme sans convertir: {worst['final_url']} ({worst['cost']} CHF, 0 conv)"
                    )
                if len(pages) == 1:
                    insights.append(
                        "⚠️ Une seule landing page utilisée — créer des LP dédiées par cluster d'intention"
                    )
                blended_cpa = total_cost / total_conv if total_conv > 0 else None
                if blended_cpa:
                    insights.append(f"📊 CPA blended landing pages: {blended_cpa:.2f} CHF")

            return {
                "success": True,
                "date_range": date_range,
                "page_count": len(pages),
                "pages": pages,
                "insights": insights,
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to get landing page report: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }

    # ------------------------------------------------------------------
    # SEARCH TERM CLUSTERS
    # ------------------------------------------------------------------
    async def get_search_term_clusters(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Get Google's semantically-clustered search term insights.

        Different from the standard search_term_view: this groups search queries
        into semantic categories (the same view as 'Termes de recherche → Catégories'
        in the UI). Each cluster has aggregated metrics across all variants.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            googleads_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    campaign_search_term_insight.category_label,
                    campaign_search_term_insight.id,
                    campaign_search_term_insight.campaign_id,
                    metrics.clicks,
                    metrics.impressions,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM campaign_search_term_insight
                WHERE segments.date DURING {date_range}
            """

            if campaign_id:
                query += f" AND campaign_search_term_insight.campaign_id = {campaign_id}"

            query += " ORDER BY metrics.impressions DESC"

            response = googleads_service.search(
                customer_id=customer_id, query=query
            )

            clusters = []
            for row in response:
                cost = micros_to_currency(row.metrics.cost_micros)
                conv = float(row.metrics.conversions)
                clusters.append(
                    {
                        "cluster_label": str(row.campaign_search_term_insight.category_label),
                        "cluster_id": str(row.campaign_search_term_insight.id),
                        "campaign_id": str(row.campaign_search_term_insight.campaign_id),
                        "clicks": int(row.metrics.clicks),
                        "impressions": int(row.metrics.impressions),
                        "cost": round(cost, 2),
                        "conversions": round(conv, 2),
                        "conversion_value": round(float(row.metrics.conversions_value), 2),
                        "cpa": round(cost / conv, 2) if conv > 0 else None,
                    }
                )

            insights = [f"🔍 {len(clusters)} cluster(s) sémantique(s) identifié(s)"]
            converters = [c for c in clusters if c["conversions"] >= 1]
            if converters:
                insights.append(
                    f"✅ {len(converters)} cluster(s) avec conversion(s)"
                )
            waste = sorted(
                [c for c in clusters if c["cost"] >= 10 and c["conversions"] == 0],
                key=lambda c: -c["cost"],
            )
            if waste:
                insights.append(
                    f"🚨 {len(waste)} cluster(s) gaspillent du budget (top: {waste[0]['cluster_label']} — {waste[0]['cost']} CHF, 0 conv)"
                )

            return {
                "success": True,
                "date_range": date_range,
                "cluster_count": len(clusters),
                "clusters": clusters,
                "insights": insights,
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to get search term clusters: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }

    # ------------------------------------------------------------------
    # HOURLY & DAY-OF-WEEK PERFORMANCE
    # ------------------------------------------------------------------
    async def get_hourly_performance(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Get performance broken down by hour of day (0-23)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            googleads_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    segments.hour,
                    metrics.clicks,
                    metrics.impressions,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.ctr
                FROM campaign
                WHERE segments.date DURING {date_range}
            """

            if campaign_id:
                query += f" AND campaign.id = {campaign_id}"

            query += " ORDER BY segments.hour ASC"

            response = googleads_service.search(
                customer_id=customer_id, query=query
            )

            # Aggregate by hour
            buckets: Dict[int, Dict[str, float]] = {
                h: {"clicks": 0, "impressions": 0, "cost": 0.0, "conversions": 0.0}
                for h in range(24)
            }
            for row in response:
                h = int(row.segments.hour)
                buckets[h]["clicks"] += int(row.metrics.clicks)
                buckets[h]["impressions"] += int(row.metrics.impressions)
                buckets[h]["cost"] += micros_to_currency(row.metrics.cost_micros)
                buckets[h]["conversions"] += float(row.metrics.conversions)

            hours = []
            for h in range(24):
                b = buckets[h]
                hours.append(
                    {
                        "hour": h,
                        "clicks": b["clicks"],
                        "impressions": b["impressions"],
                        "cost": round(b["cost"], 2),
                        "conversions": round(b["conversions"], 2),
                        "cpa": round(b["cost"] / b["conversions"], 2)
                        if b["conversions"] > 0
                        else None,
                        "ctr": f"{(b['clicks'] / b['impressions'] * 100):.2f}%"
                        if b["impressions"] > 0
                        else "0.00%",
                    }
                )

            # Top converting hours
            top_hours = sorted(
                [h for h in hours if h["conversions"] > 0],
                key=lambda h: -h["conversions"],
            )[:5]
            insights = []
            if top_hours:
                top_str = ", ".join(
                    "{h}h ({c} conv)".format(h=item["hour"], c=item["conversions"])
                    for item in top_hours
                )
                insights.append(f"🕐 Top heures convertisseuses: {top_str}")
            zero_hours = [h["hour"] for h in hours if h["impressions"] > 50 and h["conversions"] == 0]
            if zero_hours:
                insights.append(
                    f"⚠️ Heures avec volume mais 0 conv: {zero_hours}"
                )

            return {
                "success": True,
                "date_range": date_range,
                "hourly_breakdown": hours,
                "insights": insights,
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to get hourly performance: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }

    async def get_day_of_week_performance(
        self,
        customer_id: str,
        campaign_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> Dict[str, Any]:
        """Get performance broken down by day of week (MONDAY..SUNDAY)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            googleads_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    segments.day_of_week,
                    metrics.clicks,
                    metrics.impressions,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.ctr
                FROM campaign
                WHERE segments.date DURING {date_range}
            """

            if campaign_id:
                query += f" AND campaign.id = {campaign_id}"

            response = googleads_service.search(
                customer_id=customer_id, query=query
            )

            day_order = [
                "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY",
                "FRIDAY", "SATURDAY", "SUNDAY",
            ]
            buckets: Dict[str, Dict[str, float]] = {
                d: {"clicks": 0, "impressions": 0, "cost": 0.0, "conversions": 0.0}
                for d in day_order
            }
            for row in response:
                day = str(row.segments.day_of_week.name)
                if day not in buckets:
                    continue
                buckets[day]["clicks"] += int(row.metrics.clicks)
                buckets[day]["impressions"] += int(row.metrics.impressions)
                buckets[day]["cost"] += micros_to_currency(row.metrics.cost_micros)
                buckets[day]["conversions"] += float(row.metrics.conversions)

            days = []
            for d in day_order:
                b = buckets[d]
                days.append(
                    {
                        "day_of_week": d,
                        "clicks": b["clicks"],
                        "impressions": b["impressions"],
                        "cost": round(b["cost"], 2),
                        "conversions": round(b["conversions"], 2),
                        "cpa": round(b["cost"] / b["conversions"], 2)
                        if b["conversions"] > 0
                        else None,
                        "ctr": f"{(b['clicks'] / b['impressions'] * 100):.2f}%"
                        if b["impressions"] > 0
                        else "0.00%",
                    }
                )

            insights = []
            converters = [d for d in days if d["conversions"] > 0]
            if converters:
                best_day = max(converters, key=lambda d: d["conversions"])
                insights.append(
                    f"📅 Meilleur jour: {best_day['day_of_week']} ({best_day['conversions']} conv)"
                )

            return {
                "success": True,
                "date_range": date_range,
                "day_of_week_breakdown": days,
                "insights": insights,
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to get day of week performance: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }

    # ------------------------------------------------------------------
    # CHANGE HISTORY
    # ------------------------------------------------------------------
    async def get_change_history(
        self,
        customer_id: str,
        date_range: str = "LAST_14_DAYS",
        resource_type: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get the change event audit trail.

        Args:
            resource_type: Optional filter. Examples: CAMPAIGN, AD_GROUP, AD,
                AD_GROUP_CRITERION, CAMPAIGN_BUDGET, CAMPAIGN_CRITERION,
                BIDDING_STRATEGY, FEED, FEED_ITEM, AD_GROUP_AD.
            limit: Max number of events to return (default 100).
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            googleads_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    change_event.resource_name,
                    change_event.change_date_time,
                    change_event.change_resource_type,
                    change_event.change_resource_name,
                    change_event.client_type,
                    change_event.user_email,
                    change_event.resource_change_operation,
                    change_event.changed_fields,
                    change_event.campaign,
                    change_event.ad_group
                FROM change_event
                WHERE change_event.change_date_time DURING {date_range}
            """

            if resource_type:
                query += f" AND change_event.change_resource_type = '{resource_type}'"

            query += f" ORDER BY change_event.change_date_time DESC LIMIT {limit}"

            response = googleads_service.search(
                customer_id=customer_id, query=query
            )

            events = []
            for row in response:
                events.append(
                    {
                        "timestamp": str(row.change_event.change_date_time),
                        "resource_type": str(row.change_event.change_resource_type.name),
                        "resource_name": str(row.change_event.change_resource_name),
                        "operation": str(row.change_event.resource_change_operation.name),
                        "user_email": str(row.change_event.user_email),
                        "client_type": str(row.change_event.client_type.name),
                        "changed_fields": str(row.change_event.changed_fields) or None,
                        "campaign": str(row.change_event.campaign) or None,
                        "ad_group": str(row.change_event.ad_group) or None,
                    }
                )

            # Aggregate by user + operation
            users: Dict[str, int] = {}
            ops: Dict[str, int] = {}
            for e in events:
                users[e["user_email"]] = users.get(e["user_email"], 0) + 1
                ops[e["operation"]] = ops.get(e["operation"], 0) + 1

            return {
                "success": True,
                "date_range": date_range,
                "event_count": len(events),
                "by_user": users,
                "by_operation": ops,
                "events": events,
            }

        except GoogleAdsException as e:
            logger.error(f"Failed to get change history: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "GoogleAdsException",
            }
