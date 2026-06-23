"""Runtime configuration and dual-mode Databricks authentication.

In a Databricks App, ``WorkspaceClient()`` picks up the injected service-principal
credentials. Locally it falls back to a CLI profile (``DATABRICKS_PROFILE``).

The target catalog/schema/warehouse are read from env vars at startup but can be
overridden at runtime via the in-app Settings tab (see ``settings`` route). We keep
them in a small mutable singleton so a Settings change takes effect without restart.
"""
from __future__ import annotations

import os
import threading
from functools import lru_cache

from databricks.sdk import WorkspaceClient

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))


@lru_cache(maxsize=1)
def get_workspace_client() -> WorkspaceClient:
    """Authenticated WorkspaceClient (cached for the process)."""
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "DEFAULT")
    return WorkspaceClient(profile=profile)


def get_workspace_host() -> str:
    """Workspace host URL, always with an https:// scheme."""
    if IS_DATABRICKS_APP:
        host = os.environ.get("DATABRICKS_HOST", "")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        if host:
            return host
    return get_workspace_client().config.host


def get_token() -> str:
    """Bearer token for the OpenAI-compatible serving endpoint client."""
    if IS_DATABRICKS_APP:
        tok = os.environ.get("DATABRICKS_TOKEN")
        if tok:
            return tok
    auth_headers = get_workspace_client().config.authenticate()
    if auth_headers and "Authorization" in auth_headers:
        return auth_headers["Authorization"].replace("Bearer ", "")
    raise RuntimeError("Could not resolve a Databricks auth token")


class _Settings:
    """Mutable runtime settings, seeded from env, editable via the Settings tab."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.catalog = os.environ.get("CATALOG", "main")
        self.schema = os.environ.get("SCHEMA", "vehicle_upsell")
        self.warehouse_id = os.environ.get("WAREHOUSE_ID", "")
        self.default_model = os.environ.get("DEFAULT_MODEL", "databricks-claude-sonnet-4-6")
        self.jobs_workspace_dir = os.environ.get("JOBS_WORKSPACE_DIR", "")

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if v is not None and hasattr(self, k):
                    setattr(self, k, v)

    @property
    def fq_schema(self) -> str:
        return f"`{self.catalog}`.`{self.schema}`"

    def table(self, name: str) -> str:
        return f"`{self.catalog}`.`{self.schema}`.`{name}`"

    def as_dict(self) -> dict:
        return {
            "catalog": self.catalog,
            "schema": self.schema,
            "warehouse_id": self.warehouse_id,
            "default_model": self.default_model,
            "jobs_workspace_dir": self.jobs_workspace_dir,
        }


settings = _Settings()
