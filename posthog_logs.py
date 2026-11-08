"""Dedicated PostHog log export for Streamlit analysis lifecycle logs."""

import atexit
import logging
import os
from typing import Optional

import streamlit as st


_setup_logger = logging.getLogger(__name__)
_LOGGER_NAME = "intonation_analysis.posthog_logs"


def _warn_missing_configuration(variable_name: str) -> None:
    if os.getenv("ENVIRONMENT", "").lower() != "production":
        _setup_logger.warning(
            "%s variable required by PostHog is missing or un-configured, this causes "
            "events to be silently missed. This error stops appearing once %s is configured",
            variable_name,
            variable_name,
        )


@st.cache_resource
def get_posthog_logs_logger() -> Optional[logging.Logger]:
    """Return a logger whose records, and only its records, are exported to PostHog."""
    project_token = os.getenv("POSTHOG_PROJECT_TOKEN")
    if not project_token:
        _warn_missing_configuration("POSTHOG_PROJECT_TOKEN")
        return None

    host = os.getenv("POSTHOG_HOST")
    if not host:
        _warn_missing_configuration("POSTHOG_HOST")
        return None

    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    logger_provider = LoggerProvider()
    exporter = OTLPLogExporter(
        endpoint=f"{host.rstrip('/')}/i/v1/logs",
        headers={"Authorization": f"Bearer {project_token}"},
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    posthog_logs_logger = logging.getLogger(_LOGGER_NAME)
    posthog_logs_logger.setLevel(logging.INFO)
    posthog_logs_logger.propagate = False
    posthog_logs_logger.addHandler(LoggingHandler(logger_provider=logger_provider))
    atexit.register(logger_provider.shutdown, 3000)
    return posthog_logs_logger
