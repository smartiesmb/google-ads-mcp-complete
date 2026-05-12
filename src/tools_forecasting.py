"""Forecasting & simulation tools (keyword forecasts, bid simulators, campaign simulators)."""

from typing import Any, Dict, List, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

from .utils import micros_to_currency, currency_to_micros

logger = structlog.get_logger(__name__)


class ForecastingTools:
    """KeywordPlan forecasts and bid/campaign simulations."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def get_keyword_planner_forecast(
        self,
        customer_id: str,
        keywords: List[str],
        language_id: str = "1002",
        location_ids: Optional[List[str]] = None,
        cpc_bid: float = 2.0,
    ) -> Dict[str, Any]:
        """Forecast clicks/impressions/cost for a set of keywords + bid.

        Default location: Switzerland (2756). Default language: French (1002).
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("KeywordPlanIdeaService")

            if not location_ids:
                location_ids = ["2756"]

            forecast_request = client.get_type("GenerateKeywordForecastMetricsRequest")
            forecast_request.customer_id = customer_id

            campaign = client.get_type("KeywordPlanCampaignForecast")
            campaign.bidding_strategy.manual_cpc_bidding_strategy.daily_budget_micros = 100_000_000
            campaign.geo_targets.append(_make_geo(client, location_ids[0]))
            campaign.language_constants.append(
                client.get_service("GoogleAdsService").language_constant_path(language_id)
            )
            campaign.keyword_plan_network = (
                client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
            )

            ad_group = client.get_type("KeywordPlanAdGroupForecast")
            ad_group.max_cpc_bid_micros = currency_to_micros(cpc_bid)
            for kw in keywords:
                fk = client.get_type("KeywordPlanAdGroupKeywordForecast")
                fk.keyword.text = kw
                fk.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
                ad_group.keywords.append(fk)
            campaign.ad_groups.append(ad_group)
            forecast_request.campaign = campaign

            response = service.generate_keyword_forecast_metrics(request=forecast_request)
            m = response.campaign_forecast_metrics

            return {
                "success": True,
                "keywords": keywords,
                "cpc_bid": cpc_bid,
                "forecast": {
                    "impressions": float(m.impressions or 0),
                    "clicks": float(m.clicks or 0),
                    "cost": round(micros_to_currency(int(m.cost_micros or 0)), 2),
                    "ctr": round(float(m.ctr or 0) * 100, 2),
                    "average_cpc": round(micros_to_currency(int(m.average_cpc_micros or 0)), 2),
                },
            }
        except GoogleAdsException as e:
            logger.error(f"Forecast failed: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def get_keyword_bid_simulation(
        self,
        customer_id: str,
        keyword_id: str,
        ad_group_id: str,
    ) -> Dict[str, Any]:
        """Get bid landscape simulation for a keyword (what happens at bid X)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    keyword_bid_landscape.criterion_id,
                    keyword_bid_landscape.bid_landscape_points,
                    keyword_bid_landscape.start_date,
                    keyword_bid_landscape.end_date
                FROM keyword_bid_landscape
                WHERE ad_group_criterion.criterion_id = {keyword_id}
                  AND ad_group.id = {ad_group_id}
            """
            response = service.search(customer_id=customer_id, query=query)
            points = []
            for row in response:
                for p in row.keyword_bid_landscape.bid_landscape_points:
                    points.append({
                        "bid": round(micros_to_currency(p.bid_micros), 2),
                        "clicks": int(p.clicks),
                        "impressions": int(p.impressions),
                        "cost": round(micros_to_currency(p.cost_micros), 2),
                    })
            return {"success": True, "keyword_id": keyword_id, "points": points}
        except GoogleAdsException as e:
            logger.error(f"Bid simulation failed: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def get_campaign_simulation(
        self,
        customer_id: str,
        campaign_id: str,
        simulation_type: str = "TARGET_CPA",
    ) -> Dict[str, Any]:
        """Simulate a campaign-level bidding change (TARGET_CPA, TARGET_ROAS, BUDGET, CPC_BID)."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    campaign_simulation.campaign_id,
                    campaign_simulation.type,
                    campaign_simulation.modification_method,
                    campaign_simulation.start_date,
                    campaign_simulation.end_date,
                    campaign_simulation.target_cpa_point_list.points,
                    campaign_simulation.target_roas_point_list.points,
                    campaign_simulation.budget_point_list.points,
                    campaign_simulation.cpc_bid_point_list.points
                FROM campaign_simulation
                WHERE campaign_simulation.campaign_id = {campaign_id}
                  AND campaign_simulation.type = '{simulation_type}'
            """
            response = service.search(customer_id=customer_id, query=query)
            points = []
            for row in response:
                sim = row.campaign_simulation
                if simulation_type == "TARGET_CPA":
                    for p in sim.target_cpa_point_list.points:
                        points.append({
                            "target_cpa": round(micros_to_currency(p.target_cpa_micros), 2),
                            "biddable_conversions": float(p.biddable_conversions),
                            "biddable_conversions_value": float(p.biddable_conversions_value),
                            "clicks": int(p.clicks),
                            "cost": round(micros_to_currency(p.cost_micros), 2),
                            "impressions": int(p.impressions),
                        })
                elif simulation_type == "TARGET_ROAS":
                    for p in sim.target_roas_point_list.points:
                        points.append({
                            "target_roas": float(p.target_roas),
                            "biddable_conversions": float(p.biddable_conversions),
                            "biddable_conversions_value": float(p.biddable_conversions_value),
                            "clicks": int(p.clicks),
                            "cost": round(micros_to_currency(p.cost_micros), 2),
                        })
                elif simulation_type == "BUDGET":
                    for p in sim.budget_point_list.points:
                        points.append({
                            "budget": round(micros_to_currency(p.budget_amount_micros), 2),
                            "biddable_conversions": float(p.biddable_conversions),
                            "clicks": int(p.clicks),
                            "cost": round(micros_to_currency(p.cost_micros), 2),
                        })
                elif simulation_type == "CPC_BID":
                    for p in sim.cpc_bid_point_list.points:
                        points.append({
                            "cpc_bid": round(micros_to_currency(p.cpc_bid_micros), 2),
                            "clicks": int(p.clicks),
                            "cost": round(micros_to_currency(p.cost_micros), 2),
                            "impressions": int(p.impressions),
                        })
            return {
                "success": True,
                "campaign_id": campaign_id,
                "simulation_type": simulation_type,
                "points": points,
                "count": len(points),
            }
        except GoogleAdsException as e:
            logger.error(f"Campaign simulation failed: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def get_reach_forecast(
        self,
        customer_id: str,
        budget_micros: int,
        location_ids: Optional[List[str]] = None,
        product_mix: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Reach Planner forecast for YouTube/Display."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ReachPlanService")

            request = client.get_type("GenerateReachForecastRequest")
            request.customer_id = customer_id

            if not location_ids:
                location_ids = ["2756"]

            request.campaign_duration.duration_in_days = 30
            request.targeting.plannable_location_ids.extend(location_ids)

            if not product_mix:
                product_mix = ["TRUEVIEW_IN_STREAM"]
            for prod in product_mix:
                planned_product = client.get_type("PlannedProduct")
                planned_product.plannable_product_code = prod
                planned_product.budget_micros = budget_micros
                request.planned_products.append(planned_product)

            response = service.generate_reach_forecast(request=request)
            curves = []
            for p in response.reach_curve.reach_forecasts:
                curves.append({
                    "cost": round(micros_to_currency(p.cost_micros), 2),
                    "on_target_reach": int(p.forecast.on_target_reach),
                    "total_reach": int(p.forecast.total_reach),
                    "on_target_impressions": int(p.forecast.on_target_impressions),
                    "total_impressions": int(p.forecast.total_impressions),
                    "viewable_impressions": int(p.forecast.viewable_impressions),
                })
            return {"success": True, "curves": curves}
        except GoogleAdsException as e:
            logger.error(f"Reach forecast failed: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}


def _make_geo(client, location_id: str):
    """Build a geo target for keyword forecast."""
    geo = client.get_type("KeywordPlanGeoTarget")
    geo.geo_target_constant = (
        client.get_service("GeoTargetConstantService").geo_target_constant_path(location_id)
    )
    return geo
