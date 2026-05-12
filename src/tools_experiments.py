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
