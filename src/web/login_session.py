from fastapi import Request
from pravburo_ref_common.models import Agent, AgentRole


def start_login(request: Request, agent: Agent) -> str:
    """Give admins only a pending session until the second factor is verified."""
    request.session.clear()
    if agent.role == AgentRole.ADMIN:
        request.session["pending_admin_id"] = agent.id
        return "/admin/2fa/verify" if agent.totp_enabled else "/admin/2fa/setup"
    request.session["agent_id"] = agent.id
    request.session["role"] = agent.role.value
    return "/cabinet"
