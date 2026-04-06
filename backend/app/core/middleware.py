import contextvars

_tenant_ctx_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)

def get_current_tenant_id_from_context() -> str | None:
    return _tenant_ctx_var.get()

def set_current_tenant_id_in_context(tenant_id: str | None) -> contextvars.Token:
    return _tenant_ctx_var.set(tenant_id)

def reset_tenant_id_in_context(token: contextvars.Token):
    _tenant_ctx_var.reset(token)
