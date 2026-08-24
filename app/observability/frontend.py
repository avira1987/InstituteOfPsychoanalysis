"""Runtime config injected into admin-ui index.html (prebuilt dist)."""

from __future__ import annotations

import json

from app.observability.sentry import frontend_sentry_dsn
from app.observability.setup import effective_environment


def observability_bootstrap_script(settings) -> str:
    payload = {
        "sentryDsn": frontend_sentry_dsn(settings),
        "environment": effective_environment(settings),
        "release": f"anistito@{getattr(settings, 'APP_VERSION', '0')}",
    }
    return (
        "<script>window.__ANISTITO_OBS__="
        + json.dumps(payload, ensure_ascii=False)
        + ";</script>\n"
    )
