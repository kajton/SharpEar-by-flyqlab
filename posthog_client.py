"""Shared PostHog client for the Streamlit application."""

import atexit
import logging
import os
from typing import Optional

import streamlit as st


logger = logging.getLogger(__name__)


def _warn_missing_configuration(variable_name: str) -> None:
    if os.getenv("ENVIRONMENT", "").lower() != "production":
        logger.warning(
            "%s variable required by PostHog is missing or un-configured, this causes "
            "events to be silently missed. This error stops appearing once %s is configured",
            variable_name,
            variable_name,
        )


@st.cache_resource
def get_posthog_client() -> Optional["Posthog"]:
    """Create and cache one PostHog client for the Streamlit server process."""
    project_token = os.getenv("POSTHOG_PROJECT_TOKEN")
    if not project_token:
        _warn_missing_configuration("POSTHOG_PROJECT_TOKEN")
        return None

    host = os.getenv("POSTHOG_HOST")
    if not host:
        _warn_missing_configuration("POSTHOG_HOST")
        return None

    from posthog import Posthog

    posthog_client = Posthog(
        project_token,
        host=host,
        enable_exception_autocapture=True,
    )
    atexit.register(posthog_client.shutdown)
    return posthog_client
