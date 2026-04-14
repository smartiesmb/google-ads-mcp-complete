"""Conversion tracking and offline conversion upload tools for Google Ads API v21."""

from typing import Any, Dict, List, Optional
import structlog

from google.ads.googleads.errors import GoogleAdsException

from .utils import micros_to_currency

logger = structlog.get_logger(__name__)


# Google Ads ConversionAction category values (v21)
CATEGORY_MAP = {
    "DEFAULT": "DEFAULT",
    "PAGE_VIEW": "PAGE_VIEW",
    "PURCHASE": "PURCHASE",
    "SIGNUP": "SIGNUP",
    "LEAD": "LEAD",
    "DOWNLOAD": "DOWNLOAD",
    "ADD_TO_CART": "ADD_TO_CART",
    "BEGIN_CHECKOUT": "BEGIN_CHECKOUT",
    "SUBSCRIBE_PAID": "SUBSCRIBE_PAID",
    "PHONE_CALL_LEAD": "PHONE_CALL_LEAD",
    "IMPORTED_LEAD": "IMPORTED_LEAD",
    "SUBMIT_LEAD_FORM": "SUBMIT_LEAD_FORM",
    "BOOK_APPOINTMENT": "BOOK_APPOINTMENT",
    "REQUEST_QUOTE": "REQUEST_QUOTE",
    "GET_DIRECTIONS": "GET_DIRECTIONS",
    "OUTBOUND_CLICK": "OUTBOUND_CLICK",
    "CONTACT": "CONTACT",
    "ENGAGEMENT": "ENGAGEMENT",
    "STORE_VISIT": "STORE_VISIT",
    "STORE_SALE": "STORE_SALE",
    "QUALIFIED_LEAD": "QUALIFIED_LEAD",
    "CONVERTED_LEAD": "CONVERTED_LEAD",
}


class ConversionTools:
    """Conversion action management and offline conversion upload."""

    def __init__(self, auth_manager, error_handler):
        self.auth_manager = auth_manager
        self.error_handler = error_handler

    async def create_conversion_action(
        self,
        customer_id: str,
        name: str,
        category: str = "LEAD",
        action_type: str = "WEBPAGE",
        value: Optional[float] = None,
        currency_code: str = "CHF",
        count_type: str = "ONE_PER_CLICK",
        click_through_lookback_days: int = 30,
        view_through_lookback_days: int = 1,
        include_in_conversions_metric: bool = True,
        status: str = "ENABLED",
    ) -> Dict[str, Any]:
        """Create a conversion action.

        Args:
            customer_id: Target account ID (no dashes).
            name: Conversion action name, e.g. 'Lead Form Submit'.
            category: DEFAULT, LEAD, PURCHASE, SIGNUP, SUBMIT_LEAD_FORM, PHONE_CALL_LEAD,
                BOOK_APPOINTMENT, REQUEST_QUOTE, CONTACT, DOWNLOAD, ADD_TO_CART, etc.
            type: WEBPAGE, UPLOAD_CLICKS, UPLOAD_CALLS, AD_CALL, CLICK_TO_CALL,
                WEBSITE_CALL, SMART_CAMPAIGN_ADS_CLICKS_TO_CALL, GOOGLE_PLAY_DOWNLOAD,
                GOOGLE_PLAY_IN_APP_PURCHASE, FIREBASE_ANDROID_FIRST_OPEN, etc.
            value: Default conversion value (optional).
            currency_code: ISO 4217 code, default CHF.
            count_type: ONE_PER_CLICK (leads) or MANY_PER_CLICK (sales).
            click_through_lookback_days: 1-90, default 30.
            view_through_lookback_days: 1-30, default 1.
            include_in_conversions_metric: Count in main "Conversions" column.
            status: ENABLED, REMOVED, HIDDEN.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ConversionActionService")

            op = client.get_type("ConversionActionOperation")
            ca = op.create
            ca.name = name
            ca.category = getattr(client.enums.ConversionActionCategoryEnum, category.upper())
            ca.type_ = getattr(client.enums.ConversionActionTypeEnum, action_type.upper())
            ca.status = getattr(client.enums.ConversionActionStatusEnum, status.upper())
            ca.counting_type = getattr(
                client.enums.ConversionActionCountingTypeEnum, count_type.upper()
            )
            ca.click_through_lookback_window_days = int(click_through_lookback_days)
            ca.view_through_lookback_window_days = int(view_through_lookback_days)
            # include_in_conversions_metric is immutable at create time — Google
            # auto-sets it based on category. Change it afterwards via update_conversion_action.

            if value is not None:
                ca.value_settings.default_value = float(value)
                ca.value_settings.default_currency_code = currency_code
                ca.value_settings.always_use_default_value = True

            response = service.mutate_conversion_actions(
                customer_id=customer_id, operations=[op]
            )
            result = response.results[0]
            conversion_id = result.resource_name.split("/")[-1]

            return {
                "success": True,
                "conversion_action_id": conversion_id,
                "resource_name": result.resource_name,
                "name": name,
                "category": category,
                "type": action_type,
                "status": status,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to create conversion action: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
        except Exception as e:
            logger.error(f"Unexpected error creating conversion action: {e}")
            return {"success": False, "error": str(e), "error_type": e.__class__.__name__}

    async def list_conversion_actions(
        self, customer_id: str, status: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all conversion actions in the account."""
        try:
            client = self.auth_manager.get_client(customer_id)
            ga_service = client.get_service("GoogleAdsService")

            where = ""
            if status:
                where = f" WHERE conversion_action.status = '{status.upper()}'"

            query = (
                "SELECT conversion_action.id, conversion_action.name, "
                "conversion_action.category, conversion_action.type, "
                "conversion_action.status, conversion_action.counting_type, "
                "conversion_action.include_in_conversions_metric, "
                "conversion_action.click_through_lookback_window_days, "
                "conversion_action.view_through_lookback_window_days, "
                "conversion_action.value_settings.default_value, "
                "conversion_action.value_settings.default_currency_code, "
                "conversion_action.tag_snippets "
                f"FROM conversion_action{where}"
            )

            rows = ga_service.search(customer_id=customer_id, query=query)
            actions = []
            for row in rows:
                ca = row.conversion_action
                actions.append(
                    {
                        "id": str(ca.id),
                        "name": ca.name,
                        "category": ca.category.name if hasattr(ca.category, "name") else str(ca.category),
                        "type": ca.type_.name if hasattr(ca.type_, "name") else str(ca.type_),
                        "status": ca.status.name if hasattr(ca.status, "name") else str(ca.status),
                        "counting_type": ca.counting_type.name if hasattr(ca.counting_type, "name") else str(ca.counting_type),
                        "include_in_conversions_metric": ca.include_in_conversions_metric,
                        "click_through_lookback_days": ca.click_through_lookback_window_days,
                        "view_through_lookback_days": ca.view_through_lookback_window_days,
                        "default_value": ca.value_settings.default_value,
                        "default_currency": ca.value_settings.default_currency_code,
                    }
                )
            return {"success": True, "conversion_actions": actions, "count": len(actions)}
        except GoogleAdsException as e:
            logger.error(f"Failed to list conversion actions: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def get_conversion_action(
        self, customer_id: str, conversion_action_id: str
    ) -> Dict[str, Any]:
        """Get full details for a conversion action including the HTML tag snippets."""
        try:
            client = self.auth_manager.get_client(customer_id)
            ga_service = client.get_service("GoogleAdsService")

            query = (
                "SELECT conversion_action.id, conversion_action.name, "
                "conversion_action.category, conversion_action.type, "
                "conversion_action.status, conversion_action.counting_type, "
                "conversion_action.include_in_conversions_metric, "
                "conversion_action.click_through_lookback_window_days, "
                "conversion_action.view_through_lookback_window_days, "
                "conversion_action.value_settings.default_value, "
                "conversion_action.value_settings.default_currency_code, "
                "conversion_action.value_settings.always_use_default_value, "
                "conversion_action.tag_snippets "
                f"FROM conversion_action WHERE conversion_action.id = {conversion_action_id}"
            )

            rows = list(ga_service.search(customer_id=customer_id, query=query))
            if not rows:
                return {"success": False, "error": f"Conversion action {conversion_action_id} not found"}

            ca = rows[0].conversion_action
            snippets = []
            for snip in ca.tag_snippets:
                snippets.append(
                    {
                        "type": snip.type_.name if hasattr(snip.type_, "name") else str(snip.type_),
                        "page_format": snip.page_format.name if hasattr(snip.page_format, "name") else str(snip.page_format),
                        "global_site_tag": snip.global_site_tag,
                        "event_snippet": snip.event_snippet,
                    }
                )
            return {
                "success": True,
                "id": str(ca.id),
                "name": ca.name,
                "category": ca.category.name if hasattr(ca.category, "name") else str(ca.category),
                "type": ca.type_.name if hasattr(ca.type_, "name") else str(ca.type_),
                "status": ca.status.name if hasattr(ca.status, "name") else str(ca.status),
                "counting_type": ca.counting_type.name if hasattr(ca.counting_type, "name") else str(ca.counting_type),
                "include_in_conversions_metric": ca.include_in_conversions_metric,
                "click_through_lookback_days": ca.click_through_lookback_window_days,
                "view_through_lookback_days": ca.view_through_lookback_window_days,
                "default_value": ca.value_settings.default_value,
                "default_currency": ca.value_settings.default_currency_code,
                "always_use_default_value": ca.value_settings.always_use_default_value,
                "tag_snippets": snippets,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to get conversion action: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def update_conversion_action(
        self,
        customer_id: str,
        conversion_action_id: str,
        name: Optional[str] = None,
        status: Optional[str] = None,
        value: Optional[float] = None,
        currency_code: Optional[str] = None,
        include_in_conversions_metric: Optional[bool] = None,
        click_through_lookback_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update mutable fields of a conversion action."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ConversionActionService")

            op = client.get_type("ConversionActionOperation")
            ca = op.update
            ca.resource_name = service.conversion_action_path(customer_id, conversion_action_id)

            paths = []
            if name is not None:
                ca.name = name
                paths.append("name")
            if status is not None:
                ca.status = getattr(client.enums.ConversionActionStatusEnum, status.upper())
                paths.append("status")
            if value is not None:
                ca.value_settings.default_value = float(value)
                ca.value_settings.always_use_default_value = True
                paths.append("value_settings.default_value")
                paths.append("value_settings.always_use_default_value")
            if currency_code is not None:
                ca.value_settings.default_currency_code = currency_code
                paths.append("value_settings.default_currency_code")
            if include_in_conversions_metric is not None:
                ca.include_in_conversions_metric = bool(include_in_conversions_metric)
                paths.append("include_in_conversions_metric")
            if click_through_lookback_days is not None:
                ca.click_through_lookback_window_days = int(click_through_lookback_days)
                paths.append("click_through_lookback_window_days")

            if not paths:
                return {"success": False, "error": "No fields to update"}

            from google.protobuf.field_mask_pb2 import FieldMask
            update_mask = FieldMask()
            update_mask.paths.extend(paths)
            op.update_mask = update_mask

            response = service.mutate_conversion_actions(
                customer_id=customer_id, operations=[op]
            )
            return {
                "success": True,
                "resource_name": response.results[0].resource_name,
                "updated_fields": paths,
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to update conversion action: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def remove_conversion_action(
        self, customer_id: str, conversion_action_id: str
    ) -> Dict[str, Any]:
        """Remove a conversion action."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ConversionActionService")

            op = client.get_type("ConversionActionOperation")
            op.remove = service.conversion_action_path(customer_id, conversion_action_id)
            response = service.mutate_conversion_actions(
                customer_id=customer_id, operations=[op]
            )
            return {"success": True, "removed_resource_name": response.results[0].resource_name}
        except GoogleAdsException as e:
            logger.error(f"Failed to remove conversion action: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def upload_click_conversion(
        self,
        customer_id: str,
        conversion_action_id: str,
        gclid: str,
        conversion_date_time: str,
        conversion_value: Optional[float] = None,
        currency_code: str = "CHF",
        order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload an offline click conversion (GCLID-based).

        Args:
            customer_id: Account ID.
            conversion_action_id: Target conversion action ID.
            gclid: Google Click Identifier captured on landing.
            conversion_date_time: Format 'YYYY-MM-DD HH:MM:SS+HH:MM' (include timezone).
            conversion_value: Monetary value (optional).
            currency_code: ISO 4217, default CHF.
            order_id: Deduplication key (optional, recommended).
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ConversionUploadService")
            ca_service = client.get_service("ConversionActionService")

            click_conversion = client.get_type("ClickConversion")
            click_conversion.conversion_action = ca_service.conversion_action_path(
                customer_id, conversion_action_id
            )
            click_conversion.gclid = gclid
            click_conversion.conversion_date_time = conversion_date_time
            if conversion_value is not None:
                click_conversion.conversion_value = float(conversion_value)
                click_conversion.currency_code = currency_code
            if order_id is not None:
                click_conversion.order_id = order_id

            response = service.upload_click_conversions(
                customer_id=customer_id,
                conversions=[click_conversion],
                partial_failure=True,
            )
            results = []
            for r in response.results:
                results.append(
                    {
                        "gclid": r.gclid,
                        "conversion_action": r.conversion_action,
                        "conversion_date_time": r.conversion_date_time,
                    }
                )
            errors = []
            if response.partial_failure_error and response.partial_failure_error.message:
                errors.append(response.partial_failure_error.message)

            return {"success": len(errors) == 0, "results": results, "errors": errors}
        except GoogleAdsException as e:
            logger.error(f"Failed to upload click conversion: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def upload_call_conversion(
        self,
        customer_id: str,
        conversion_action_id: str,
        caller_id: str,
        call_start_date_time: str,
        conversion_date_time: str,
        conversion_value: Optional[float] = None,
        currency_code: str = "CHF",
    ) -> Dict[str, Any]:
        """Upload an offline call conversion.

        Args:
            caller_id: E.164 phone number of the caller, e.g. '+41791234567'.
            call_start_date_time: When the call started, 'YYYY-MM-DD HH:MM:SS+HH:MM'.
            conversion_date_time: When the conversion happened, same format.
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("ConversionUploadService")
            ca_service = client.get_service("ConversionActionService")

            call_conversion = client.get_type("CallConversion")
            call_conversion.conversion_action = ca_service.conversion_action_path(
                customer_id, conversion_action_id
            )
            call_conversion.caller_id = caller_id
            call_conversion.call_start_date_time = call_start_date_time
            call_conversion.conversion_date_time = conversion_date_time
            if conversion_value is not None:
                call_conversion.conversion_value = float(conversion_value)
                call_conversion.currency_code = currency_code

            response = service.upload_call_conversions(
                customer_id=customer_id,
                conversions=[call_conversion],
                partial_failure=True,
            )
            results = []
            for r in response.results:
                results.append(
                    {
                        "caller_id": r.caller_id,
                        "conversion_action": r.conversion_action,
                        "conversion_date_time": r.conversion_date_time,
                    }
                )
            errors = []
            if response.partial_failure_error and response.partial_failure_error.message:
                errors.append(response.partial_failure_error.message)
            return {"success": len(errors) == 0, "results": results, "errors": errors}
        except GoogleAdsException as e:
            logger.error(f"Failed to upload call conversion: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    # ═══════════════════════════════════════════════════════════════
    # Customer Conversion Goals (primary / secondary management)
    # ═══════════════════════════════════════════════════════════════

    async def list_customer_conversion_goals(self, customer_id: str) -> Dict[str, Any]:
        """List account-level conversion goals (category + origin -> biddable flag).

        biddable=True  => conversion actions of this (category, origin) count as
                          primary (included in "Conversions" metric, drives bidding).
        biddable=False => secondary (observation only).
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            ga_service = client.get_service("GoogleAdsService")
            query = (
                "SELECT customer_conversion_goal.category, "
                "customer_conversion_goal.origin, "
                "customer_conversion_goal.biddable "
                "FROM customer_conversion_goal"
            )
            rows = ga_service.search(customer_id=customer_id, query=query)
            goals = []
            for row in rows:
                g = row.customer_conversion_goal
                goals.append({
                    "category": g.category.name if hasattr(g.category, "name") else str(g.category),
                    "origin": g.origin.name if hasattr(g.origin, "name") else str(g.origin),
                    "biddable": g.biddable,
                    "resource_name": g.resource_name,
                })
            return {"success": True, "goals": goals, "count": len(goals)}
        except GoogleAdsException as e:
            logger.error(f"Failed to list customer conversion goals: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def update_customer_conversion_goal(
        self,
        customer_id: str,
        category: str,
        origin: str,
        biddable: bool,
    ) -> Dict[str, Any]:
        """Mark a (category, origin) pair as primary (biddable=True) or secondary.

        Example to demote phone calls from the website to secondary:
            update_customer_conversion_goal(customer_id, "PHONE_CALL_LEAD", "WEBSITE", False)

        Category values: PURCHASE, LEAD, SIGNUP, SUBMIT_LEAD_FORM, PHONE_CALL_LEAD,
            BOOK_APPOINTMENT, REQUEST_QUOTE, CONTACT, ENGAGEMENT, DOWNLOAD, ADD_TO_CART, ...
        Origin values: WEBSITE, APP, CALL_FROM_ADS, GOOGLE_HOSTED, STORE
        """
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("CustomerConversionGoalService")

            op = client.get_type("CustomerConversionGoalOperation")
            goal = op.update
            goal.resource_name = (
                f"customers/{customer_id}/customerConversionGoals/"
                f"{category.upper()}~{origin.upper()}"
            )
            goal.biddable = bool(biddable)

            from google.protobuf.field_mask_pb2 import FieldMask
            mask = FieldMask()
            mask.paths.append("biddable")
            op.update_mask = mask

            response = service.mutate_customer_conversion_goals(
                customer_id=customer_id, operations=[op]
            )
            return {
                "success": True,
                "resource_name": response.results[0].resource_name,
                "category": category.upper(),
                "origin": origin.upper(),
                "biddable": bool(biddable),
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to update customer conversion goal: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def list_campaign_conversion_goals(
        self, customer_id: str, campaign_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List campaign-level overrides for conversion goals. An override forces
        a (category, origin) to be biddable or not for a specific campaign,
        regardless of the account-level customer_conversion_goal."""
        try:
            client = self.auth_manager.get_client(customer_id)
            ga_service = client.get_service("GoogleAdsService")
            where = ""
            if campaign_id:
                where = f" WHERE campaign_conversion_goal.campaign = 'customers/{customer_id}/campaigns/{campaign_id}'"
            query = (
                "SELECT campaign_conversion_goal.campaign, "
                "campaign_conversion_goal.category, "
                "campaign_conversion_goal.origin, "
                "campaign_conversion_goal.biddable "
                f"FROM campaign_conversion_goal{where}"
            )
            rows = ga_service.search(customer_id=customer_id, query=query)
            goals = []
            for row in rows:
                g = row.campaign_conversion_goal
                goals.append({
                    "campaign": g.campaign,
                    "campaign_id": g.campaign.split("/")[-1] if g.campaign else None,
                    "category": g.category.name if hasattr(g.category, "name") else str(g.category),
                    "origin": g.origin.name if hasattr(g.origin, "name") else str(g.origin),
                    "biddable": g.biddable,
                })
            return {"success": True, "goals": goals, "count": len(goals)}
        except GoogleAdsException as e:
            logger.error(f"Failed to list campaign conversion goals: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}

    async def update_campaign_conversion_goal(
        self,
        customer_id: str,
        campaign_id: str,
        category: str,
        origin: str,
        biddable: bool,
    ) -> Dict[str, Any]:
        """Override a (category, origin) biddable flag for a specific campaign."""
        try:
            client = self.auth_manager.get_client(customer_id)
            service = client.get_service("CampaignConversionGoalService")
            op = client.get_type("CampaignConversionGoalOperation")
            goal = op.update
            goal.resource_name = (
                f"customers/{customer_id}/campaignConversionGoals/"
                f"{campaign_id}~{category.upper()}~{origin.upper()}"
            )
            goal.biddable = bool(biddable)
            from google.protobuf.field_mask_pb2 import FieldMask
            mask = FieldMask()
            mask.paths.append("biddable")
            op.update_mask = mask
            response = service.mutate_campaign_conversion_goals(
                customer_id=customer_id, operations=[op]
            )
            return {
                "success": True,
                "resource_name": response.results[0].resource_name,
                "campaign_id": campaign_id,
                "category": category.upper(),
                "origin": origin.upper(),
                "biddable": bool(biddable),
            }
        except GoogleAdsException as e:
            logger.error(f"Failed to update campaign conversion goal: {e}")
            return {"success": False, "error": str(e), "error_type": "GoogleAdsException"}
