"""Route submodules."""

from .agent import router as agent_router
from .automations import router as automations_router
from .integrations import router as integrations_router
from .dashboard import router as dashboard_router
from .activity import router as activity_router
from .executions import router as executions_router

__all__ = [
    "agent_router",
    "automations_router",
    "integrations_router",
    "dashboard_router",
    "activity_router",
    "executions_router",
]
