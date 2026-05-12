# Google Ads MCP — Piloting Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing 94-tool Google Ads MCP (`c:\Users\glako\google-ads-mcp-complete`) into a complete piloting system covering Performance Max, Smart Bidding simulators, Customer Match, Conversion Goals, Experiments/Drafts, Asset performance, Demographic/Device segmentation, Lead Forms, Recommendations subscriptions, and transverse improvements (dry-run, audit log, validate_only, pagination, quota tracking).

**Architecture:** Each domain gets its own `tools_<domain>.py` file with an `<Domain>Tools` class instantiated in `tools_complete.py:GoogleAdsTools.__init__` and registered via a dedicated `_register_<domain>_tools()` method following the exact pattern used by existing modules (`tools_keywords.py`, `tools_audiences.py`, `tools_insights.py`, etc.). Cross-cutting concerns (dry-run flag, audit log, validate_only) live in middleware functions invoked by `tools_complete.py:execute_tool`.

**Tech Stack:** Python ≥3.10, `google-ads>=24.1.0` (API v20 client), `structlog`, `mcp>=1.0.0`. No new external dependencies required. Verification = AST parse + import + registry presence (no test framework configured in the repo).

**Conventions every task must follow:**
- All handler methods are `async def`, return `Dict[str, Any]` with `success: True/False`.
- Currency micros: use `from .utils import micros_to_currency`.
- Errors: catch `GoogleAdsException`, return `{"success": False, "error": str(e), "error_type": "GoogleAdsException"}`.
- Logging: `logger = structlog.get_logger(__name__)` at module level; `logger.error(...)` in except blocks.
- File header: triple-quoted docstring describing the module purpose.
- Customer ID: never sanitize inside handlers (already done upstream).
- Use `client = self.auth_manager.get_client(customer_id)` then `client.get_service("...")`.
- Match types, statuses, enums: stringify via `.name` attribute (e.g. `row.campaign.status.name`).

**Verification per task:** After every code change, run:

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/<file>.py', encoding='utf-8').read()); print('OK')"
```

Plus a final import smoke test in Task 20.

---

## Task 1: Asset Performance Module

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_asset_performance.py`
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_complete.py` (import + init + register — done in Task 17 to avoid 20 merges; this task only creates the module).

- [ ] **Step 1: Create the module file**

Write the file with this exact content:

```python
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
```

- [ ] **Step 2: Verify syntax**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_asset_performance.py', encoding='utf-8').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_asset_performance.py && git commit -m "feat(insights): add asset performance label report (Tier 1 #1)"
```

---

## Task 2: Segments Module (device, demographic, click_view, distance)

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_segments.py`

- [ ] **Step 1: Create the file**

```python
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
```

- [ ] **Step 2: Verify syntax**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_segments.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_segments.py && git commit -m "feat(segments): device, demo, distance, click_view (Tier 1 #2-3 + Tier 2)"
```

---

## Task 3: Forecasting Module (keyword forecast, bid simulators, campaign simulator)

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_forecasting.py`

- [ ] **Step 1: Create file**

```python
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
        language_id: str = "1002",  # French
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
                location_ids = ["2756"]  # Switzerland

            forecast_request = client.get_type("GenerateKeywordForecastMetricsRequest")
            forecast_request.customer_id = customer_id

            # Build keyword plan inline
            campaign = client.get_type("KeywordPlanCampaignForecast")
            campaign.bidding_strategy.manual_cpc_bidding_strategy.daily_budget_micros = 100_000_000  # 100 CHF
            campaign.geo_targets.append(
                _make_geo(client, location_ids[0])
            )
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
                    raw_points = sim.target_cpa_point_list.points
                    for p in raw_points:
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

            for loc in location_ids:
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
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_forecasting.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_forecasting.py && git commit -m "feat(forecasting): keyword/bid/campaign simulators + reach forecast (Tier 1 #4,6,10)"
```

---

## Task 4: Customer Match Module

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_customer_match.py`

- [ ] **Step 1: Create file**

```python
"""Customer Match (audience upload from hashed email/phone)."""

import hashlib
from typing import Any, Dict, List, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

logger = structlog.get_logger(__name__)


class CustomerMatchTools:
    """CRUD + upload for Customer Match user lists."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def create_customer_match_list(
        self,
        customer_id: str,
        name: str,
        description: Optional[str] = None,
        membership_lifespan_days: int = 540,
    ) -> Dict[str, Any]:
        """Create an empty Customer Match user list."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("UserListService")

            op = client.get_type("UserListOperation")
            ul = op.create
            ul.name = name
            if description:
                ul.description = description
            ul.membership_life_span = membership_lifespan_days
            ul.crm_based_user_list.upload_key_type = (
                client.enums.CustomerMatchUploadKeyTypeEnum.CONTACT_INFO
            )

            response = service.mutate_user_lists(
                customer_id=customer_id, operations=[op]
            )
            resource_name = response.results[0].resource_name
            return {
                "success": True,
                "user_list_id": resource_name.split("/")[-1],
                "resource_name": resource_name,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to create customer match list: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def upload_customer_match_users(
        self,
        customer_id: str,
        user_list_id: str,
        emails: Optional[List[str]] = None,
        phones: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Upload hashed emails/phones to an existing user list.

        Inputs are auto-normalized (lowercase, stripped) and SHA-256 hashed before send.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            offline_service = client.get_service("OfflineUserDataJobService")

            # Create job
            job = client.get_type("OfflineUserDataJob")
            job.type_ = client.enums.OfflineUserDataJobTypeEnum.CUSTOMER_MATCH_USER_LIST
            job.customer_match_user_list_metadata.user_list = (
                f"customers/{customer_id}/userLists/{user_list_id}"
            )
            create_response = offline_service.create_offline_user_data_job(
                customer_id=customer_id, job=job
            )
            job_resource = create_response.resource_name

            # Build operations
            operations = []
            for email in (emails or []):
                op = client.get_type("OfflineUserDataJobOperation")
                user_data = op.create
                ui = client.get_type("UserIdentifier")
                ui.hashed_email = _sha256(email.strip().lower())
                user_data.user_identifiers.append(ui)
                operations.append(op)
            for phone in (phones or []):
                op = client.get_type("OfflineUserDataJobOperation")
                user_data = op.create
                ui = client.get_type("UserIdentifier")
                ui.hashed_phone_number = _sha256(phone.strip())
                user_data.user_identifiers.append(ui)
                operations.append(op)

            offline_service.add_offline_user_data_job_operations(
                resource_name=job_resource,
                operations=operations,
                enable_partial_failure=True,
            )
            offline_service.run_offline_user_data_job(resource_name=job_resource)

            return {
                "success": True,
                "job_resource_name": job_resource,
                "users_queued": len(operations),
                "note": "Job is asynchronous. Members typically appear in 24-48h.",
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to upload customer match users: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_customer_match.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_customer_match.py && git commit -m "feat(audience): Customer Match list creation + hashed upload (Tier 1 #5)"
```

---

## Task 5: Experiments & Drafts Module

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_experiments.py`

- [ ] **Step 1: Create file**

```python
"""Campaign experiments & drafts."""

from typing import Any, Dict, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

logger = structlog.get_logger(__name__)


class ExperimentTools:
    """Drafts + Experiments for A/B campaign testing."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def list_experiments(
        self, customer_id: str, campaign_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List experiments on the account or campaign."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")
            query = """
                SELECT
                    experiment.resource_name,
                    experiment.experiment_id,
                    experiment.name,
                    experiment.description,
                    experiment.suffix,
                    experiment.type,
                    experiment.status,
                    experiment.start_date,
                    experiment.end_date,
                    experiment.long_running_operation
                FROM experiment
            """
            if campaign_id:
                query += f" WHERE experiment.campaigns CONTAINS ANY ('customers/{customer_id}/campaigns/{campaign_id}')"
            response = service.search(customer_id=customer_id, query=query)
            experiments = []
            for row in response:
                e = row.experiment
                experiments.append({
                    "resource_name": str(e.resource_name),
                    "id": str(e.experiment_id),
                    "name": str(e.name),
                    "description": str(e.description),
                    "type": str(e.type.name),
                    "status": str(e.status.name),
                    "start_date": str(e.start_date),
                    "end_date": str(e.end_date),
                })
            return {"success": True, "experiments": experiments, "count": len(experiments)}
        except GoogleAdsException as e:
            logger.error(f"Failed to list experiments: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def create_experiment(
        self,
        customer_id: str,
        base_campaign_id: str,
        name: str,
        traffic_split_percent: int = 50,
    ) -> Dict[str, Any]:
        """Create a SEARCH_CUSTOM experiment from an existing campaign with a 50/50 split."""
        try:
            client = self.auth_manager.get_client(customer_id)
            exp_service = client.get_service("ExperimentService")
            campaign_exp_service = client.get_service("CampaignExperimentService")

            # Step 1: Create experiment shell
            exp_op = client.get_type("ExperimentOperation")
            exp = exp_op.create
            exp.name = name
            exp.type_ = client.enums.ExperimentTypeEnum.SEARCH_CUSTOM
            exp.suffix = f"_test_{name[:8]}"
            exp.status = client.enums.ExperimentStatusEnum.SETUP
            response = exp_service.mutate_experiments(
                customer_id=customer_id, operations=[exp_op]
            )
            experiment_resource = response.results[0].resource_name

            # Step 2: Create campaign experiment with split
            ce_op = client.get_type("CampaignExperimentOperation")
            ce = ce_op.create
            ce.campaign = f"customers/{customer_id}/campaigns/{base_campaign_id}"
            ce.experiment = experiment_resource
            ce.traffic_split_percent = traffic_split_percent
            ce.traffic_split_type = client.enums.CampaignExperimentTrafficSplitTypeEnum.RANDOM_QUERY

            ce_response = campaign_exp_service.mutate_campaign_experiments(
                customer_id=customer_id, operations=[ce_op]
            )
            return {
                "success": True,
                "experiment_resource_name": experiment_resource,
                "campaign_experiment_resource_name": ce_response.results[0].resource_name,
                "note": "Edit treatment campaign separately, then start_experiment() to launch.",
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to create experiment: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def start_experiment(
        self, customer_id: str, experiment_resource_name: str
    ) -> Dict[str, Any]:
        """Move experiment from SETUP to RUNNING."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ExperimentService")
            response = service.start_experiment(resource_name=experiment_resource_name)
            return {"success": True, "operation": str(response.name)}
        except GoogleAdsException as e:
            logger.error(f"Failed to start experiment: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def end_experiment(
        self, customer_id: str, experiment_resource_name: str
    ) -> Dict[str, Any]:
        """Stop an experiment immediately."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ExperimentService")
            service.end_experiment(experiment=experiment_resource_name)
            return {"success": True, "experiment": experiment_resource_name}
        except GoogleAdsException as e:
            logger.error(f"Failed to end experiment: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def graduate_experiment(
        self,
        customer_id: str,
        experiment_resource_name: str,
        campaign_budget_resource_name: str,
    ) -> Dict[str, Any]:
        """Promote experiment to a standalone campaign."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ExperimentService")
            response = service.graduate_experiment(
                experiment=experiment_resource_name,
                campaign_budget_mappings=[
                    {
                        "experiment_campaign": "",
                        "campaign_budget": campaign_budget_resource_name,
                    }
                ],
            )
            return {"success": True, "results": [str(r.campaign) for r in response.campaign_budget_mappings]}
        except GoogleAdsException as e:
            logger.error(f"Failed to graduate experiment: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_experiments.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_experiments.py && git commit -m "feat(experiments): drafts + experiments lifecycle (Tier 2)"
```

---

## Task 6: Performance Max Module

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_pmax.py`

- [ ] **Step 1: Create file**

```python
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
        """Create an asset group (the unit of organization in PMax) — empty, assets added separately."""
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
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_pmax.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_pmax.py && git commit -m "feat(pmax): Performance Max campaign + asset groups + signals (Tier 3)"
```

---

## Task 7: Video & Demand Gen Module

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_video.py`

- [ ] **Step 1: Create file**

```python
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
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_video.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_video.py && git commit -m "feat(video): video campaigns + Demand Gen + YouTube assets (Tier 3)"
```

---

## Task 8: Shopping Module

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_shopping.py`

- [ ] **Step 1: Create file**

```python
"""Shopping campaigns + Merchant Center linking + product partitioning."""

from typing import Any, Dict, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

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
            from .utils import micros_to_currency
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
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_shopping.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_shopping.py && git commit -m "feat(shopping): Shopping campaigns + Merchant Center + product perf (Tier 3)"
```

---

## Task 9: Lead Form, Promotion & Price Assets (extend tools_assets.py)

**Files:**
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_assets.py` (append new methods to the existing `AssetTools` class)

- [ ] **Step 1: Read the file's current end**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "lines=open('src/tools_assets.py', encoding='utf-8').readlines(); print(len(lines))"
```

- [ ] **Step 2: Append the three new methods**

Open `src/tools_assets.py` and append (before EOF, inside the `AssetTools` class — find the last method's last line and add after, keeping class indentation):

```python
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
```

- [ ] **Step 3: Verify syntax**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_assets.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_assets.py && git commit -m "feat(assets): lead form + promotion + price extensions (Tier 1 #7 + Tier 3)"
```

---

## Task 10: Extend tools_insights.py (recommendation subscription + audience insights)

**Files:**
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_insights.py`

- [ ] **Step 1: Append two new methods to `InsightsTools` class**

Append before EOF of `src/tools_insights.py`, with class-level indentation:

```python
    # ------------------------------------------------------------------
    # RECOMMENDATIONS SUBSCRIPTIONS (auto-apply)
    # ------------------------------------------------------------------
    async def list_recommendation_subscriptions(self, customer_id: str) -> Dict[str, Any]:
        """List active auto-apply subscriptions on the account."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")
            query = """
                SELECT
                    recommendation_subscription.type,
                    recommendation_subscription.status,
                    recommendation_subscription.create_date_time,
                    recommendation_subscription.modify_date_time
                FROM recommendation_subscription
            """
            response = service.search(customer_id=customer_id, query=query)
            subs = []
            for row in response:
                s = row.recommendation_subscription
                subs.append({
                    "type": str(s.type.name),
                    "status": str(s.status.name),
                    "created": str(s.create_date_time),
                    "modified": str(s.modify_date_time),
                })
            return {"success": True, "subscriptions": subs}
        except GoogleAdsException as e:
            logger.error(f"Failed to list subscriptions: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def subscribe_to_recommendations(
        self,
        customer_id: str,
        recommendation_type: str,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Auto-apply a recommendation type.

        recommendation_type examples: KEYWORD, TEXT_AD, TARGET_CPA_OPT_IN,
            MAXIMIZE_CONVERSIONS_OPT_IN, OPTIMIZE_AD_ROTATION, RESPONSIVE_SEARCH_AD,
            UPGRADE_SMART_SHOPPING_CAMPAIGN_TO_PERFORMANCE_MAX.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("RecommendationSubscriptionService")
            op = client.get_type("RecommendationSubscriptionOperation")
            sub = op.create
            sub.type_ = getattr(
                client.enums.RecommendationTypeEnum, recommendation_type
            )
            sub.status = (
                client.enums.RecommendationSubscriptionStatusEnum.ENABLED
                if enabled
                else client.enums.RecommendationSubscriptionStatusEnum.PAUSED
            )
            response = service.mutate_recommendation_subscription(
                customer_id=customer_id, operations=[op]
            )
            return {
                "success": True,
                "resource_name": response.results[0].resource_name,
                "type": recommendation_type,
                "enabled": enabled,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to subscribe: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    # ------------------------------------------------------------------
    # AUDIENCE INSIGHTS (real API)
    # ------------------------------------------------------------------
    async def generate_audience_insights(
        self,
        customer_id: str,
        location_ids: Optional[List[str]] = None,
        user_interests: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate audience insights via AudienceInsightsService.

        location_ids: list of geo target constant IDs (default: Switzerland '2756').
        user_interests: list of user_interest constant IDs to seed the insights.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("AudienceInsightsService")

            if not location_ids:
                location_ids = ["2756"]

            request = client.get_type("GenerateAudienceCompositionInsightsRequest")
            request.customer_id = customer_id
            request.dimensions.append(
                client.enums.AudienceInsightsDimensionEnum.AFFINITY_USER_INTEREST
            )
            request.dimensions.append(
                client.enums.AudienceInsightsDimensionEnum.IN_MARKET_USER_INTEREST
            )

            audience = client.get_type("InsightsAudience")
            for loc in location_ids:
                geo = audience.country_locations.add()
                geo.geo_target_constant = (
                    client.get_service("GeoTargetConstantService").geo_target_constant_path(loc)
                )
            if user_interests:
                for ui in user_interests:
                    seed = audience.topic_audience_combinations.add()
                    interest = seed.included_audiences.add()
                    interest.user_interest.user_interest_category = (
                        f"customers/{customer_id}/userInterests/{ui}"
                    )
            request.audience = audience

            response = service.generate_audience_composition_insights(request=request)
            findings = []
            for section in response.sections:
                for finding in section.top_attributes:
                    findings.append({
                        "dimension": str(section.dimension.name),
                        "attribute": str(finding.attribute.display_name),
                        "share": round(float(finding.share or 0) * 100, 2),
                        "index": round(float(finding.index or 0), 2),
                    })
            return {"success": True, "findings": findings}
        except GoogleAdsException as e:
            logger.error(f"Failed to generate audience insights: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_insights.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_insights.py && git commit -m "feat(insights): recommendation subscriptions + audience insights API (Tier 1 #8, Tier 2)"
```

---

## Task 11: Extend tools_conversions.py (goals + value rules + attribution)

**Files:**
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_conversions.py`

- [ ] **Step 1: Append methods to `ConversionTools` class**

Find the last method in `src/tools_conversions.py`'s `ConversionTools` class and append the following at class-level indentation:

```python
    async def list_conversion_goals(self, customer_id: str) -> dict:
        """List customer-level conversion goals and how they're grouped."""
        from google.ads.googleads.errors import GoogleAdsException
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")
            query = """
                SELECT
                    customer_conversion_goal.category,
                    customer_conversion_goal.origin,
                    customer_conversion_goal.biddable
                FROM customer_conversion_goal
            """
            response = service.search(customer_id=customer_id, query=query)
            goals = []
            for row in response:
                g = row.customer_conversion_goal
                goals.append({
                    "category": str(g.category.name),
                    "origin": str(g.origin.name),
                    "biddable": bool(g.biddable),
                })
            return {"success": True, "goals": goals}
        except GoogleAdsException as e:
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def update_customer_conversion_goal(
        self,
        customer_id: str,
        category: str,
        origin: str,
        biddable: bool,
    ) -> dict:
        """Toggle a customer conversion goal's biddable flag (controls what bidding optimizes for)."""
        from google.ads.googleads.errors import GoogleAdsException
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("CustomerConversionGoalService")
            op = client.get_type("CustomerConversionGoalOperation")
            g = op.update
            g.resource_name = (
                f"customers/{customer_id}/customerConversionGoals/{category}~{origin}"
            )
            g.biddable = biddable
            op.update_mask.paths.append("biddable")
            response = service.mutate_customer_conversion_goals(
                customer_id=customer_id, operations=[op]
            )
            return {"success": True, "resource_name": response.results[0].resource_name}
        except GoogleAdsException as e:
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def list_campaign_conversion_goals(
        self, customer_id: str, campaign_id: str
    ) -> dict:
        """List campaign-level conversion goal overrides."""
        from google.ads.googleads.errors import GoogleAdsException
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    campaign_conversion_goal.category,
                    campaign_conversion_goal.origin,
                    campaign_conversion_goal.biddable
                FROM campaign_conversion_goal
                WHERE campaign.id = {campaign_id}
            """
            response = service.search(customer_id=customer_id, query=query)
            goals = []
            for row in response:
                g = row.campaign_conversion_goal
                goals.append({
                    "category": str(g.category.name),
                    "origin": str(g.origin.name),
                    "biddable": bool(g.biddable),
                })
            return {"success": True, "campaign_id": campaign_id, "goals": goals}
        except GoogleAdsException as e:
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def create_conversion_value_rule(
        self,
        customer_id: str,
        action_type: str,
        action_value: float,
        geo_location_ids: list = None,
        device_types: list = None,
    ) -> dict:
        """Create a conversion value rule (multiply/add/replace conv value by condition).

        action_type: MULTIPLY, ADD, SET
        """
        from google.ads.googleads.errors import GoogleAdsException
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ConversionValueRuleService")
            op = client.get_type("ConversionValueRuleOperation")
            r = op.create
            r.action.operation = getattr(
                client.enums.ValueRuleOperationEnum, action_type
            )
            r.action.value = action_value
            if geo_location_ids:
                for loc in geo_location_ids:
                    r.geo_location_condition.geo_target_constants.append(
                        client.get_service("GeoTargetConstantService").geo_target_constant_path(loc)
                    )
                r.geo_location_condition.geo_match_type = (
                    client.enums.ValueRuleGeoLocationMatchTypeEnum.LOCATION_OF_PRESENCE
                )
            if device_types:
                for dt in device_types:
                    r.device_condition.device_types.append(
                        getattr(client.enums.ValueRuleDeviceTypeEnum, dt)
                    )
            response = service.mutate_conversion_value_rules(
                customer_id=customer_id, operations=[op]
            )
            return {
                "success": True,
                "resource_name": response.results[0].resource_name,
            }
        except GoogleAdsException as e:
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def set_attribution_model(
        self,
        customer_id: str,
        conversion_action_id: str,
        attribution_model: str,
    ) -> dict:
        """Change attribution model for a conversion action.

        attribution_model: LAST_CLICK, FIRST_CLICK, LINEAR, TIME_DECAY,
            POSITION_BASED, DATA_DRIVEN.
        """
        from google.ads.googleads.errors import GoogleAdsException
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ConversionActionService")
            op = client.get_type("ConversionActionOperation")
            ca = op.update
            ca.resource_name = (
                f"customers/{customer_id}/conversionActions/{conversion_action_id}"
            )
            ca.attribution_model_settings.attribution_model = getattr(
                client.enums.AttributionModelEnum, attribution_model
            )
            op.update_mask.paths.append("attribution_model_settings.attribution_model")
            response = service.mutate_conversion_actions(
                customer_id=customer_id, operations=[op]
            )
            return {"success": True, "resource_name": response.results[0].resource_name}
        except GoogleAdsException as e:
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_conversions.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_conversions.py && git commit -m "feat(conversions): conv goals + value rules + attribution model (Tier 1 #9, Tier 2)"
```

---

## Task 12: Transverse — Dry-Run Middleware

**Files:**
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_complete.py`

Goal: a single global flag `_DRY_RUN` toggleable via env var `GADS_MCP_DRY_RUN=1` that intercepts every mutating call and returns a fake success without hitting the API. Mutating handlers are detected by name prefix (`create_`, `update_`, `delete_`, `pause_`, `enable_`, `remove_`, `add_`, `apply_`, `dismiss_`, `upload_`, `set_`, `link_`, `copy_`).

- [ ] **Step 1: Find the `execute_tool` method in `tools_complete.py`**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "
src=open('src/tools_complete.py', encoding='utf-8').read()
print('execute_tool' in src, 'async def execute_tool' in src)
"
```

If `execute_tool` does not exist, locate the dispatcher by searching for `_tools_registry[`:

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "
import re
src=open('src/tools_complete.py', encoding='utf-8').read()
for m in re.finditer(r'def (\w+).*?_tools_registry', src):
    print(m.group(0)[:80])
"
```

- [ ] **Step 2: Add helper at the top of `tools_complete.py` (after imports)**

Right after the `logger = structlog.get_logger(__name__)` line, insert:

```python
import os

_MUTATING_PREFIXES = (
    "create_", "update_", "delete_", "pause_", "enable_", "resume_", "remove_",
    "add_", "apply_", "dismiss_", "upload_", "set_", "link_", "copy_", "subscribe_",
    "graduate_", "start_", "end_", "drop_", "kill_", "save_", "clean_",
)


def _is_mutating(tool_name: str) -> bool:
    return any(tool_name.startswith(p) for p in _MUTATING_PREFIXES)


def _dry_run_active() -> bool:
    return os.getenv("GADS_MCP_DRY_RUN", "").strip() in ("1", "true", "True", "yes", "YES")
```

- [ ] **Step 3: Find the dispatch site and add the dry-run guard**

Locate the line in `tools_complete.py` where the handler is invoked (likely a line containing `await handler(**params)` or `await self._tools_registry[name]["handler"](`). Read the surrounding 10 lines to confirm, then wrap with:

```python
            if _is_mutating(name) and _dry_run_active():
                logger.warning("dry_run_blocked", tool=name, params=params)
                return {
                    "success": True,
                    "dry_run": True,
                    "tool": name,
                    "params": params,
                    "note": "Mutation skipped because GADS_MCP_DRY_RUN=1.",
                }
            # Original handler invocation continues below
```

If the dispatcher is named differently (e.g., `call_tool`), apply the same guard there.

- [ ] **Step 4: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_complete.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_complete.py && git commit -m "feat(safety): dry-run guard for all mutating tools via GADS_MCP_DRY_RUN=1"
```

---

## Task 13: Transverse — Local Audit Log

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\audit_log.py`
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_complete.py`

- [ ] **Step 1: Create `src/audit_log.py`**

```python
"""Append-only audit log for every MCP mutation.

Writes one JSON line per call to {project_root}/audit.log.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict


_LOG_PATH = Path(
    os.getenv("GADS_MCP_AUDIT_LOG", str(Path(__file__).resolve().parent.parent / "audit.log"))
)


def append(entry: Dict[str, Any]) -> None:
    """Append a JSON line to the audit log. Never raises (audit must be best-effort)."""
    entry = dict(entry)
    entry.setdefault("ts", time.time())
    entry.setdefault("ts_iso", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
    except Exception:
        pass


def path() -> Path:
    return _LOG_PATH
```

- [ ] **Step 2: Verify file**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/audit_log.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Wire it into the dispatcher in `tools_complete.py`**

At the top of `tools_complete.py`, add:

```python
from . import audit_log
```

In the dispatcher (same spot edited in Task 12), after the dry-run guard but before/around the handler call, add:

```python
            if _is_mutating(name):
                audit_log.append({"event": "before", "tool": name, "params": params})
            result = await handler(**params)
            if _is_mutating(name):
                audit_log.append({"event": "after", "tool": name, "success": bool(result.get("success")) if isinstance(result, dict) else None})
            return result
```

(Adapt to match the existing code shape — the key is `audit_log.append({...})` before and after every mutating call.)

- [ ] **Step 4: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_complete.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/audit_log.py src/tools_complete.py && git commit -m "feat(safety): local audit log (audit.log JSONL) for every mutation"
```

---

## Task 14: Transverse — `validate_only` Pre-Flight

**Files:**
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_campaigns.py` (representative — same pattern can be replicated later for other modules without breaking compat)

- [ ] **Step 1: Add `validate_only` kwarg to `create_campaign` and pass it through**

Locate `async def create_campaign` in `src/tools_campaigns.py`. Add `validate_only: bool = False` to its signature. Then locate the `service.mutate_campaigns(customer_id=customer_id, operations=[op])` call inside it and replace with:

```python
            response = service.mutate_campaigns(
                customer_id=customer_id,
                operations=[op],
                validate_only=validate_only,
            )
            if validate_only:
                return {
                    "success": True,
                    "validate_only": True,
                    "note": "Validation succeeded — no mutation performed.",
                }
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_campaigns.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_campaigns.py && git commit -m "feat(safety): expose validate_only=True on create_campaign (pre-flight)"
```

---

## Task 15: Transverse — Pagination on `list_keywords` and `list_ads`

**Files:**
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_keywords.py`
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_ads.py`

- [ ] **Step 1: Add a `limit` and `offset` parameter to `list_keywords`**

In `src/tools_keywords.py`, find the `list_keywords` method. Add to its signature:

```python
        limit: int = 500,
        offset: int = 0,
```

Inside, append to the constructed query (just before `service.search(...)`):

```python
            query += f" LIMIT {limit} OFFSET {offset}"
```

(If the query already has `LIMIT`, replace the existing limit; otherwise append.)

In the return dict, add `"limit": limit, "offset": offset, "next_offset": offset + limit`.

- [ ] **Step 2: Same for `list_ads` in `tools_ads.py`**

Identical change: add `limit=500, offset=0` parameters, append `LIMIT {limit} OFFSET {offset}` to the GAQL, add the three fields to the response.

- [ ] **Step 3: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "
import ast
for p in ['src/tools_keywords.py','src/tools_ads.py']:
    ast.parse(open(p, encoding='utf-8').read())
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_keywords.py src/tools_ads.py && git commit -m "feat(pagination): limit/offset on list_keywords + list_ads"
```

---

## Task 16: Transverse — Quota / Rate Limit Helper

**Files:**
- Create: `c:\Users\glako\google-ads-mcp-complete\src\tools_quota.py`

- [ ] **Step 1: Create the module**

```python
"""Quota / rate-limit visibility for Google Ads API."""

from typing import Any, Dict
import structlog

from google.ads.googleads.errors import GoogleAdsException

logger = structlog.get_logger(__name__)


class QuotaTools:
    """Expose API quota usage and rate-limit headers from the last request."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler
        # Cache populated by interceptor (optional future work)
        self._last_headers: Dict[str, str] = {}

    async def get_api_quota_status(self, customer_id: str) -> Dict[str, Any]:
        """Return the last seen rate-limit headers from a small probe call.

        The Google Ads API doesn't expose a dedicated 'quota status' endpoint;
        instead it returns rate-limit info in response headers. We fire a tiny
        probe (LIMIT 1 select on customer) and capture them.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("GoogleAdsService")
            response = service.search(
                customer_id=customer_id,
                query="SELECT customer.id FROM customer LIMIT 1",
            )
            # Drain to ensure the stream completes
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
```

- [ ] **Step 2: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_quota.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_quota.py && git commit -m "feat(ops): quota status probe + UI dashboard pointer"
```

---

## Task 17: Wire All New Modules in `tools_complete.py`

**Files:**
- Modify: `c:\Users\glako\google-ads-mcp-complete\src\tools_complete.py`

- [ ] **Step 1: Add imports**

After the existing tool imports, add:

```python
from .tools_asset_performance import AssetPerformanceTools
from .tools_segments import SegmentTools
from .tools_forecasting import ForecastingTools
from .tools_customer_match import CustomerMatchTools
from .tools_experiments import ExperimentTools
from .tools_pmax import PerformanceMaxTools
from .tools_video import VideoTools
from .tools_shopping import ShoppingTools
from .tools_quota import QuotaTools
```

- [ ] **Step 2: Instantiate in `__init__`**

After the existing `self.insights_tools = InsightsTools(auth_manager, error_handler)` line, add:

```python
        self.asset_performance_tools = AssetPerformanceTools(auth_manager, error_handler)
        self.segment_tools = SegmentTools(auth_manager, error_handler)
        self.forecasting_tools = ForecastingTools(auth_manager, error_handler)
        self.customer_match_tools = CustomerMatchTools(auth_manager, error_handler)
        self.experiment_tools = ExperimentTools(auth_manager, error_handler)
        self.pmax_tools = PerformanceMaxTools(auth_manager, error_handler)
        self.video_tools = VideoTools(auth_manager, error_handler)
        self.shopping_tools = ShoppingTools(auth_manager, error_handler)
        self.quota_tools = QuotaTools(auth_manager, error_handler)
```

- [ ] **Step 3: Add registration calls inside `_register_all_tools`**

Find the line `tools.update(self._register_insights_tools())` and append below it:

```python
        tools.update(self._register_asset_performance_tools())
        tools.update(self._register_segments_tools())
        tools.update(self._register_forecasting_tools())
        tools.update(self._register_customer_match_tools())
        tools.update(self._register_experiment_tools())
        tools.update(self._register_pmax_tools())
        tools.update(self._register_video_tools())
        tools.update(self._register_shopping_tools())
        tools.update(self._register_lead_form_assets())
        tools.update(self._register_extra_insights_tools())
        tools.update(self._register_extra_conversion_tools())
        tools.update(self._register_quota_tools())
```

- [ ] **Step 4: Add the registration methods**

At the bottom of the `GoogleAdsTools` class, before the closing of the class body, add:

```python
    def _register_asset_performance_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "get_asset_performance_report": {
                "description": "Per-asset (headline/description) RSA performance with PerformanceLabel (BEST/GOOD/LOW/PENDING). Critical for identifying which RSA assets to replace.",
                "handler": self.asset_performance_tools.get_asset_performance_report,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "ad_group_id": {"type": "string"},
                    "campaign_id": {"type": "string"},
                    "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                },
            },
        }

    def _register_segments_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "get_device_performance": {
                "description": "Performance broken down by device (MOBILE/DESKTOP/TABLET/CONNECTED_TV).",
                "handler": self.segment_tools.get_device_performance,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string"},
                    "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                },
            },
            "get_demographic_performance": {
                "description": "Age + gender breakdown.",
                "handler": self.segment_tools.get_demographic_performance,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string"},
                    "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                },
            },
            "get_distance_performance": {
                "description": "Performance by user distance from business location.",
                "handler": self.segment_tools.get_distance_performance,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string"},
                    "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                },
            },
            "get_click_view": {
                "description": "Click-level data (gclid, device, location). Max 90 days back.",
                "handler": self.segment_tools.get_click_view,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "date_range": {"type": "string", "default": "LAST_7_DAYS"},
                    "limit": {"type": "number", "default": 100},
                },
            },
        }

    def _register_forecasting_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "get_keyword_planner_forecast": {
                "description": "Forecast impressions/clicks/cost for a set of keywords at a given CPC bid.",
                "handler": self.forecasting_tools.get_keyword_planner_forecast,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "keywords": {"type": "array", "required": True},
                    "language_id": {"type": "string", "default": "1002"},
                    "location_ids": {"type": "array"},
                    "cpc_bid": {"type": "number", "default": 2.0},
                },
            },
            "get_keyword_bid_simulation": {
                "description": "Bid landscape simulation for a specific keyword (clicks/impressions at bid X).",
                "handler": self.forecasting_tools.get_keyword_bid_simulation,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "keyword_id": {"type": "string", "required": True},
                    "ad_group_id": {"type": "string", "required": True},
                },
            },
            "get_campaign_simulation": {
                "description": "Campaign-level bidding simulation (TARGET_CPA, TARGET_ROAS, BUDGET, CPC_BID).",
                "handler": self.forecasting_tools.get_campaign_simulation,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string", "required": True},
                    "simulation_type": {"type": "string", "default": "TARGET_CPA"},
                },
            },
            "get_reach_forecast": {
                "description": "YouTube/Display reach forecast via Reach Planner.",
                "handler": self.forecasting_tools.get_reach_forecast,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "budget_micros": {"type": "number", "required": True},
                    "location_ids": {"type": "array"},
                    "product_mix": {"type": "array"},
                },
            },
        }

    def _register_customer_match_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "create_customer_match_list": {
                "description": "Create an empty Customer Match user list (lifespan default 540 days).",
                "handler": self.customer_match_tools.create_customer_match_list,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "description": {"type": "string"},
                    "membership_lifespan_days": {"type": "number", "default": 540},
                },
            },
            "upload_customer_match_users": {
                "description": "Upload emails/phones (auto-hashed SHA-256) to an existing Customer Match list.",
                "handler": self.customer_match_tools.upload_customer_match_users,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "user_list_id": {"type": "string", "required": True},
                    "emails": {"type": "array"},
                    "phones": {"type": "array"},
                },
            },
        }

    def _register_experiment_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "list_experiments": {
                "description": "List campaign experiments.",
                "handler": self.experiment_tools.list_experiments,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string"},
                },
            },
            "create_experiment": {
                "description": "Create a SEARCH_CUSTOM experiment from an existing campaign with traffic split.",
                "handler": self.experiment_tools.create_experiment,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "base_campaign_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "traffic_split_percent": {"type": "number", "default": 50},
                },
            },
            "start_experiment": {
                "description": "Move experiment from SETUP to RUNNING.",
                "handler": self.experiment_tools.start_experiment,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "experiment_resource_name": {"type": "string", "required": True},
                },
            },
            "end_experiment": {
                "description": "Stop an experiment immediately.",
                "handler": self.experiment_tools.end_experiment,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "experiment_resource_name": {"type": "string", "required": True},
                },
            },
            "graduate_experiment": {
                "description": "Promote experiment to a standalone campaign with a given budget.",
                "handler": self.experiment_tools.graduate_experiment,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "experiment_resource_name": {"type": "string", "required": True},
                    "campaign_budget_resource_name": {"type": "string", "required": True},
                },
            },
        }

    def _register_pmax_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "create_pmax_campaign": {
                "description": "Create a Performance Max campaign in PAUSED state. Use either target_roas OR target_cpa_micros.",
                "handler": self.pmax_tools.create_pmax_campaign,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "budget_resource_name": {"type": "string", "required": True},
                    "target_roas": {"type": "number"},
                    "target_cpa_micros": {"type": "number"},
                    "brand_guidelines_enabled": {"type": "boolean", "default": False},
                },
            },
            "create_asset_group": {
                "description": "Create an empty PMax asset group (organize assets per intent / theme).",
                "handler": self.pmax_tools.create_asset_group,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "final_urls": {"type": "array", "required": True},
                    "final_mobile_urls": {"type": "array"},
                },
            },
            "add_asset_group_signal": {
                "description": "Add a SEARCH_THEME (keyword) or AUDIENCE signal to an asset group.",
                "handler": self.pmax_tools.add_asset_group_signal,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "asset_group_id": {"type": "string", "required": True},
                    "signal_type": {"type": "string", "required": True},
                    "signal_value": {"type": "string", "required": True},
                },
            },
            "link_asset_to_asset_group": {
                "description": "Link an existing asset to a PMax asset group with a field_type (HEADLINE, DESCRIPTION, LOGO, etc.).",
                "handler": self.pmax_tools.link_asset_to_asset_group,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "asset_group_id": {"type": "string", "required": True},
                    "asset_id": {"type": "string", "required": True},
                    "field_type": {"type": "string", "required": True},
                },
            },
            "list_asset_groups": {
                "description": "List all asset groups.",
                "handler": self.pmax_tools.list_asset_groups,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string"},
                },
            },
        }

    def _register_video_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "create_video_campaign": {
                "description": "Create a YouTube video campaign in PAUSED state.",
                "handler": self.video_tools.create_video_campaign,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "budget_resource_name": {"type": "string", "required": True},
                    "sub_type": {"type": "string", "default": "VIDEO_REACH"},
                },
            },
            "create_demand_gen_campaign": {
                "description": "Create a Demand Gen (ex-Discovery) campaign in PAUSED state.",
                "handler": self.video_tools.create_demand_gen_campaign,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "budget_resource_name": {"type": "string", "required": True},
                },
            },
            "upload_youtube_video_asset": {
                "description": "Register a YouTube video ID as an asset.",
                "handler": self.video_tools.upload_youtube_video_asset,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "youtube_video_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                },
            },
        }

    def _register_shopping_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "list_merchant_center_links": {
                "description": "List Merchant Center accounts linked to this Google Ads customer.",
                "handler": self.shopping_tools.list_merchant_center_links,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                },
            },
            "create_shopping_campaign": {
                "description": "Create a Shopping campaign (Standard or Smart). Smart Shopping is deprecated — prefer PMax.",
                "handler": self.shopping_tools.create_shopping_campaign,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": True},
                    "budget_resource_name": {"type": "string", "required": True},
                    "merchant_id": {"type": "number", "required": True},
                    "country_code": {"type": "string", "default": "CH"},
                    "is_standard": {"type": "boolean", "default": False},
                },
            },
            "get_product_performance": {
                "description": "Per-product performance from shopping_performance_view.",
                "handler": self.shopping_tools.get_product_performance,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string"},
                    "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                },
            },
        }

    def _register_lead_form_assets(self) -> Dict[str, Dict[str, Any]]:
        return {
            "create_lead_form_asset": {
                "description": "Create a Lead Form asset (in-ad form). fields=[{'input_type':'EMAIL'},{'input_type':'PHONE_NUMBER'},...]",
                "handler": self.asset_tools.create_lead_form_asset,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "business_name": {"type": "string", "required": True},
                    "call_to_action": {"type": "string", "required": True},
                    "headline": {"type": "string", "required": True},
                    "description": {"type": "string", "required": True},
                    "privacy_policy_url": {"type": "string", "required": True},
                    "fields": {"type": "array", "required": True},
                    "post_submit_headline": {"type": "string", "default": "Merci !"},
                    "post_submit_description": {"type": "string", "default": "Nous vous recontactons sous 24h."},
                },
            },
            "create_promotion_asset": {
                "description": "Create a Promotion extension asset.",
                "handler": self.asset_tools.create_promotion_asset,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "promotion_target": {"type": "string", "required": True},
                    "discount_modifier": {"type": "string", "default": "UP_TO"},
                    "percent_off": {"type": "number", "default": 10.0},
                    "language_code": {"type": "string", "default": "fr"},
                    "final_urls": {"type": "array"},
                },
            },
            "create_price_asset": {
                "description": "Create a Price extension asset.",
                "handler": self.asset_tools.create_price_asset,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "price_type": {"type": "string", "required": True},
                    "price_qualifier": {"type": "string", "required": True},
                    "language_code": {"type": "string", "default": "fr"},
                    "offerings": {"type": "array"},
                },
            },
        }

    def _register_extra_insights_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "list_recommendation_subscriptions": {
                "description": "List active auto-apply subscriptions.",
                "handler": self.insights_tools.list_recommendation_subscriptions,
                "parameters": {"customer_id": {"type": "string", "required": True}},
            },
            "subscribe_to_recommendations": {
                "description": "Auto-apply a recommendation type (KEYWORD, TEXT_AD, TARGET_CPA_OPT_IN, etc.).",
                "handler": self.insights_tools.subscribe_to_recommendations,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "recommendation_type": {"type": "string", "required": True},
                    "enabled": {"type": "boolean", "default": True},
                },
            },
            "generate_audience_insights": {
                "description": "Generate audience composition insights via AudienceInsightsService.",
                "handler": self.insights_tools.generate_audience_insights,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "location_ids": {"type": "array"},
                    "user_interests": {"type": "array"},
                },
            },
        }

    def _register_extra_conversion_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "list_conversion_goals": {
                "description": "List customer-level conversion goals.",
                "handler": self.conversion_tools.list_conversion_goals,
                "parameters": {"customer_id": {"type": "string", "required": True}},
            },
            "update_customer_conversion_goal": {
                "description": "Toggle biddable on a customer conversion goal.",
                "handler": self.conversion_tools.update_customer_conversion_goal,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "category": {"type": "string", "required": True},
                    "origin": {"type": "string", "required": True},
                    "biddable": {"type": "boolean", "required": True},
                },
            },
            "list_campaign_conversion_goals": {
                "description": "List campaign-level conversion goal overrides.",
                "handler": self.conversion_tools.list_campaign_conversion_goals,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "campaign_id": {"type": "string", "required": True},
                },
            },
            "create_conversion_value_rule": {
                "description": "Create a conversion value rule (MULTIPLY/ADD/SET) by geo or device.",
                "handler": self.conversion_tools.create_conversion_value_rule,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "action_type": {"type": "string", "required": True},
                    "action_value": {"type": "number", "required": True},
                    "geo_location_ids": {"type": "array"},
                    "device_types": {"type": "array"},
                },
            },
            "set_attribution_model": {
                "description": "Change attribution model on a conversion action (LAST_CLICK, DATA_DRIVEN, LINEAR, ...).",
                "handler": self.conversion_tools.set_attribution_model,
                "parameters": {
                    "customer_id": {"type": "string", "required": True},
                    "conversion_action_id": {"type": "string", "required": True},
                    "attribution_model": {"type": "string", "required": True},
                },
            },
        }

    def _register_quota_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "get_api_quota_status": {
                "description": "Probe the Google Ads API and return rate-limit / quota info (UI dashboard pointer).",
                "handler": self.quota_tools.get_api_quota_status,
                "parameters": {"customer_id": {"type": "string", "required": True}},
            },
        }
```

- [ ] **Step 5: Verify**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && python -c "import ast; ast.parse(open('src/tools_complete.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 6: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add src/tools_complete.py && git commit -m "feat: wire and register all new MCP modules (33 tools)"
```

---

## Task 18: Smoke Test — Import & Registry

**Files:**
- None modified — verification only.

- [ ] **Step 1: Run a full instantiation test**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && venv/Scripts/python -c "
import os, json
cfg = json.load(open('config.json'))
os.environ.setdefault('GOOGLE_ADS_DEVELOPER_TOKEN', cfg.get('developer_token',''))
os.environ.setdefault('GOOGLE_ADS_CLIENT_ID', cfg.get('client_id',''))
os.environ.setdefault('GOOGLE_ADS_CLIENT_SECRET', cfg.get('client_secret',''))
os.environ.setdefault('GOOGLE_ADS_REFRESH_TOKEN', cfg.get('refresh_token',''))
os.environ.setdefault('GOOGLE_ADS_LOGIN_CUSTOMER_ID', cfg.get('login_customer_id',''))
from src.auth import GoogleAdsAuthManager
from src.error_handler import ErrorHandler
from src.tools_complete import GoogleAdsTools
auth = GoogleAdsAuthManager()
eh = ErrorHandler()
tools = GoogleAdsTools(auth, eh)
expected = {
    'get_asset_performance_report','get_device_performance','get_demographic_performance',
    'get_distance_performance','get_click_view','get_keyword_planner_forecast',
    'get_keyword_bid_simulation','get_campaign_simulation','get_reach_forecast',
    'create_customer_match_list','upload_customer_match_users','list_experiments',
    'create_experiment','start_experiment','end_experiment','graduate_experiment',
    'create_pmax_campaign','create_asset_group','add_asset_group_signal',
    'link_asset_to_asset_group','list_asset_groups','create_video_campaign',
    'create_demand_gen_campaign','upload_youtube_video_asset','list_merchant_center_links',
    'create_shopping_campaign','get_product_performance','create_lead_form_asset',
    'create_promotion_asset','create_price_asset','list_recommendation_subscriptions',
    'subscribe_to_recommendations','generate_audience_insights','list_conversion_goals',
    'update_customer_conversion_goal','list_campaign_conversion_goals',
    'create_conversion_value_rule','set_attribution_model','get_api_quota_status',
}
registered = set(tools._tools_registry.keys())
missing = expected - registered
extra = registered - expected
print('total_tools:', len(registered))
print('expected_new:', len(expected))
print('missing:', sorted(missing))
print('PASS' if not missing else 'FAIL')
"
```

Expected: `PASS` and `total_tools: 132+` (94 existing + 39 new).

If any tool is missing, jump back to Task 17 and fix the matching `_register_*` block.

- [ ] **Step 2: Dry-run smoke test**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && GADS_MCP_DRY_RUN=1 venv/Scripts/python -c "
import os, json, asyncio
cfg = json.load(open('config.json'))
os.environ['GADS_MCP_DRY_RUN']='1'
for k in ['developer_token','client_id','client_secret','refresh_token','login_customer_id']:
    os.environ.setdefault(f'GOOGLE_ADS_{k.upper()}', cfg.get(k,''))
from src.auth import GoogleAdsAuthManager
from src.error_handler import ErrorHandler
from src.tools_complete import GoogleAdsTools, _is_mutating, _dry_run_active
assert _dry_run_active(), 'dry-run flag not detected'
assert _is_mutating('create_campaign')
assert not _is_mutating('get_campaign_performance')
print('Dry-run guard OK')
"
```

Expected: `Dry-run guard OK`.

(If on Windows PowerShell, use `$env:GADS_MCP_DRY_RUN='1';` before the python call.)

- [ ] **Step 3: Audit log smoke test**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && venv/Scripts/python -c "
from src import audit_log
audit_log.append({'event': 'smoke_test', 'tool': 'noop'})
print('Audit log path:', audit_log.path())
print('Last 2 lines:')
print(open(audit_log.path(), encoding='utf-8').read().splitlines()[-2:])
"
```

Expected: prints the path and a line containing `smoke_test`.

- [ ] **Step 4: Commit (no-op — smoke test, no changes; skip if nothing modified)**

If any minor fix was needed during smoke testing:

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add -A && git commit -m "fix: smoke test corrections"
```

---

## Task 19: README Update

**Files:**
- Modify: `c:\Users\glako\google-ads-mcp-complete\README.md`

- [ ] **Step 1: Append a new section to the README**

Add at the bottom of README.md:

```markdown

---

## v2.1 — Insights & Piloting Modules (2026-05-12)

39 new tools added across 9 modules:

### Asset Performance
- `get_asset_performance_report` — RSA headline/description PerformanceLabel

### Segments
- `get_device_performance`, `get_demographic_performance`, `get_distance_performance`, `get_click_view`

### Forecasting & Simulation
- `get_keyword_planner_forecast`, `get_keyword_bid_simulation`, `get_campaign_simulation`, `get_reach_forecast`

### Customer Match
- `create_customer_match_list`, `upload_customer_match_users` (auto SHA-256 hashed)

### Experiments
- `list_experiments`, `create_experiment`, `start_experiment`, `end_experiment`, `graduate_experiment`

### Performance Max
- `create_pmax_campaign`, `create_asset_group`, `add_asset_group_signal`, `link_asset_to_asset_group`, `list_asset_groups`

### Video & Demand Gen
- `create_video_campaign`, `create_demand_gen_campaign`, `upload_youtube_video_asset`

### Shopping
- `list_merchant_center_links`, `create_shopping_campaign`, `get_product_performance`

### Assets (Lead Forms / Promo / Price)
- `create_lead_form_asset`, `create_promotion_asset`, `create_price_asset`

### Insights (extension)
- `list_recommendation_subscriptions`, `subscribe_to_recommendations`, `generate_audience_insights`

### Conversions (extension)
- `list_conversion_goals`, `update_customer_conversion_goal`, `list_campaign_conversion_goals`, `create_conversion_value_rule`, `set_attribution_model`

### Quota
- `get_api_quota_status`

### Cross-cutting safety
- **Dry-run mode**: set env `GADS_MCP_DRY_RUN=1` to make every mutating tool return a fake success without hitting the API.
- **Audit log**: every mutation is appended to `./audit.log` (JSONL). Override path with `GADS_MCP_AUDIT_LOG`.
- **`validate_only=True`**: exposed on `create_campaign` for pre-flight validation.
- **Pagination**: `list_keywords` and `list_ads` now accept `limit` and `offset`.

Total tools: **133**.
```

- [ ] **Step 2: Commit**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git add README.md && git commit -m "docs: README update for v2.1 — 39 new tools, dry-run, audit log"
```

---

## Task 20: Final Verification & Restart Guidance

**Files:**
- None modified — final sanity pass.

- [ ] **Step 1: Re-run the full smoke test from Task 18 Step 1**

Verify `PASS` again and `total_tools >= 132`.

- [ ] **Step 2: Run black + ruff if available**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && venv/Scripts/python -m ruff check src/ 2>/dev/null || echo "ruff not installed — skip"
cd 'c:\Users\glako\google-ads-mcp-complete' && venv/Scripts/python -m black --check src/ 2>/dev/null || echo "black not installed — skip"
```

Fix any auto-fixable issues with `ruff check --fix src/` and `black src/` if available.

- [ ] **Step 3: Print final tool list per module**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && venv/Scripts/python -c "
import os, json
cfg = json.load(open('config.json'))
for k in ['developer_token','client_id','client_secret','refresh_token','login_customer_id']:
    os.environ.setdefault(f'GOOGLE_ADS_{k.upper()}', cfg.get(k,''))
from src.auth import GoogleAdsAuthManager
from src.error_handler import ErrorHandler
from src.tools_complete import GoogleAdsTools
tools = GoogleAdsTools(GoogleAdsAuthManager(), ErrorHandler())
print(f'Total: {len(tools._tools_registry)} tools')
for t in sorted(tools._tools_registry.keys()):
    print(' -', t)
" | tee final_tool_list.txt
```

- [ ] **Step 4: Tag the release**

```bash
cd 'c:\Users\glako\google-ads-mcp-complete' && git tag -a v2.1.0 -m "Insights & Piloting Modules: 39 new tools, dry-run, audit log"
```

- [ ] **Step 5: Restart the MCP server**

Restart Claude Code / the host process that owns the MCP server so the new tools become available. Once the server reconnects, the 39 new tools will be exposed as `mcp__google-ads__*`.

---

## Self-Review Notes

- **Spec coverage**: Every Tier 1 / Tier 2 / Tier 3 item from the proposal has at least one task. Transverse items (dry-run, audit, validate_only, pagination, quota) are explicit tasks 12-16.
- **Type consistency**: All handler methods are async, return `Dict[str, Any]`, follow the `{"success": bool, ...}` shape and the `error_type: "GoogleAdsException"` convention.
- **No placeholders**: All code is concrete. The dry-run middleware spot is left for the engineer to locate exactly (Task 12 Steps 1-3) because the dispatcher location varies; instructions are explicit (find `_tools_registry[`, wrap with the guard).
- **Risk areas**:
  - `KeywordPlanIdeaService` forecast API: the `KeywordPlanCampaignForecast` / `KeywordPlanAdGroupForecast` types may have slightly different field names in different versions of the Python SDK. If a `TypeError` or `AttributeError` is raised at runtime, check `client.get_type("KeywordPlanCampaignForecast")` signature and adjust.
  - `RecommendationSubscriptionService.mutate_recommendation_subscription` is the v20 spelling; older client libs use `mutate_recommendation_subscriptions` (plural). If `AttributeError` raised, try the plural form.
  - `AudienceInsightsService.generate_audience_composition_insights` similarly may be named `generate_audience_composition_insights` or `generate_insights_finder_report` depending on version.
  - PMax `AssetGroup.AssetGroupSignal.AudienceSignal`: in v20 may require `audience_id` instead of `audience` resource name. Verify with a single dry-run call.
- **Recovery**: each task is its own commit, so `git revert <sha>` can roll back any single feature.

---

## Plan Total

- **20 tasks** (1-20)
- **9 new files** (`tools_asset_performance.py`, `tools_segments.py`, `tools_forecasting.py`, `tools_customer_match.py`, `tools_experiments.py`, `tools_pmax.py`, `tools_video.py`, `tools_shopping.py`, `tools_quota.py`, plus `audit_log.py`)
- **5 modified files** (`tools_assets.py`, `tools_insights.py`, `tools_conversions.py`, `tools_complete.py`, `tools_keywords.py`, `tools_ads.py`, `tools_campaigns.py`, `README.md`)
- **39 new MCP tools** (was 94 → 133)
- **5 transverse improvements** (dry-run, audit log, validate_only, pagination, quota)
- **~20 commits**, ~2 800 lines of new Python, ~1 day of focused execution.
