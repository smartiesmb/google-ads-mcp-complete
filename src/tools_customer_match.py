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

            job = client.get_type("OfflineUserDataJob")
            job.type_ = client.enums.OfflineUserDataJobTypeEnum.CUSTOMER_MATCH_USER_LIST
            job.customer_match_user_list_metadata.user_list = (
                f"customers/{customer_id}/userLists/{user_list_id}"
            )
            create_response = offline_service.create_offline_user_data_job(
                customer_id=customer_id, job=job
            )
            job_resource = create_response.resource_name

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
