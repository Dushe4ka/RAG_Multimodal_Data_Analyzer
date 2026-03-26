from __future__ import annotations

from deepagents.backends import CompositeBackend, StateBackend, StoreBackend, FilesystemBackend,LocalShellBackend


def _store_namespace(ctx):
    """Namespace для Store только по user_id текущего запроса — агент видит только память этого пользователя."""
    user_id = None
    raw = getattr(ctx.runtime, "context", None)
    if raw is not None:
        user_id = raw.get("user_id") if isinstance(raw, dict) else getattr(raw, "user_id", None)
    if user_id is None:
        cfg = getattr(ctx.runtime, "config", None) or {}
        user_id = (cfg.get("configurable") or {}).get("user_id")
    return ((user_id or "anonymous"), "filesystem")


def make_backend(rt):
    return CompositeBackend(
        default=LocalShellBackend(root_dir="/home/paul/Разработка/Проекты/ai_rag/agents_nodes", virtual_mode=True),
        routes={
            "/memories/": StoreBackend(rt, namespace=_store_namespace),
        },
    )

