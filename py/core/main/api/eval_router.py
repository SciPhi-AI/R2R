import logging
from pathlib import Path
from typing import Optional

import yaml
from fastapi import Body, Depends
from pydantic import Json

from core.base import EvalConfig, RunType
from core.base.api.models import (
    WrappedEvalResponse,
    WrappedEvalResultResponse,
)
from core.base.providers import OrchestrationProvider

from ...main.hatchet import r2r_hatchet
from ..hatchet import EvaluationWorkflow
from ..services.eval_service import EvalService
from .base_router import BaseRouter

logger = logging.getLogger(__name__)

class EvalRouter(BaseRouter):
    def __init__(
        self,
        service: EvalService,
        run_type: RunType = RunType.EVALUATION,
        orchestration_provider: Optional[OrchestrationProvider] = None,
    ):
        if not orchestration_provider:
            raise ValueError(
                "EvalRouter requires an orchestration provider."
            )
        super().__init__(service, run_type, orchestration_provider)
        self.service: EvalService = service

    def _load_openapi_extras(self):
        yaml_path = (
            Path(__file__).parent / "data" / "eval_router_openapi.yml"
        )
        with open(yaml_path, "r") as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
        return yaml_content

    def _register_workflows(self):
        self.orchestration_provider.register_workflow(
            EvaluationWorkflow(self.service)
        )

    def _setup_routes(self):
        @self.router.post(
            "/run_evaluation",
        )
        @self.base_endpoint
        async def run_evaluation(
            eval_config: Json[EvalConfig] = Body(
                ..., description="Configuration for the evaluation process."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
            response_model=WrappedEvalResponse,
        ):
            """
            Run an evaluation process based on the provided configuration.
            """
            if not auth_user.is_superuser:
                raise ValueError("Only superusers can run evaluations.")

            workflow_input = {
                "eval_config": eval_config.json(),
                "user": auth_user.json(),
            }

            task_id = r2r_hatchet.admin.run_workflow(
                "run-evaluation", {"request": workflow_input}
            )

            return {
                "message": "Evaluation task queued successfully.",
                "task_id": str(task_id),
            }

        @self.router.get(
            "/get_evaluation_result/{task_id}",
        )
        @self.base_endpoint
        async def get_evaluation_result(
            task_id: str,
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
            response_model=WrappedEvalResultResponse,
        ):
            """
            Retrieve the results of a previously run evaluation task.
            """
            if not auth_user.is_superuser:
                raise ValueError("Only superusers can retrieve evaluation results.")

            result = await self.service.get_evaluation_result(task_id)
            return result
