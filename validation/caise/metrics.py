"""Create and export metrics produced by validation runs."""

import dataclasses
import logging
import typing

import opentelemetry.metrics
import opentelemetry.sdk.metrics
import opentelemetry.sdk.metrics.export
import opentelemetry.sdk.resources
from opentelemetry.exporter.prometheus_remote_write import (
    PrometheusRemoteWriteMetricsExporter,
)

import caise.environment

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class ReportMetrics:
    """Hold OpenTelemetry objects used to report validation metrics."""

    _exporter: opentelemetry.sdk.metrics.export.MetricExporter
    _reader: opentelemetry.sdk.metrics.export.InMemoryMetricReader
    _meter: opentelemetry.metrics.Meter

    @classmethod
    def initialize(cls) -> typing.Self:
        """Create a configured metrics reporter.

        Returns:
            A reporter connected to the configured remote-write
            endpoint.
        """
        exporter = PrometheusRemoteWriteMetricsExporter(
            endpoint=caise.environment.CAISE_MONITORING_ENDPOINT,
            headers={
                "X-Scope-OrgID": caise.environment.CAISE_MONITORING_USERNAME
            },
            basic_auth={
                "username": caise.environment.CAISE_MONITORING_USERNAME,
                "password": caise.environment.CAISE_MONITORING_PASSWORD,
            },
            resources_as_labels=False,
        )
        reader = opentelemetry.sdk.metrics.export.InMemoryMetricReader()
        provider = opentelemetry.sdk.metrics.MeterProvider(
            metric_readers=[reader]
        )
        meter = provider.get_meter("caise_validation")

        return cls(_exporter=exporter, _reader=reader, _meter=meter)

    def set(
        self, name: str, value: float | int, labels: dict[str, str] | None
    ) -> None:
        """Create a gauge and record one value.

        Args:
            name: Gauge name.
            value: Numeric value to record.
            labels: Attributes attached to the recorded value.
        """
        metric = self._meter.create_gauge(name)
        metric.set(value, labels)

    def export(self) -> None:
        """Export collected metrics, or log when none are available."""
        if metrics_data := self._reader.get_metrics_data():
            logger.info(
                "Exporting metrics to: %s",
                caise.environment.CAISE_MONITORING_ENDPOINT,
            )
            self._exporter.export(metrics_data)
            logger.info("Job metrics exported successfully.")
        else:
            logger.warning("No metrics data to export.")


def report_result(result: float, duration: float) -> None:
    """Report a validation score and its duration.

    Args:
        result: Numeric validation score.
        duration: Validation duration in seconds.
    """
    metric_labels = {
        "service": caise.environment.CAISE_SERVICE_NAME,
        "instance": caise.environment.CAISE_SERVICE_INSTANCE,
        "test": caise.environment.CAISE_SERVICE_TEST,
        "resource": caise.environment.CAISE_SERVICE_KUBERNETES_RESOURCE,
    }
    report_metrics = ReportMetrics.initialize()
    report_metrics.set("caise_validation_test_result", result, metric_labels)
    report_metrics.set(
        "caise_validation_test_duration", duration, metric_labels
    )
    report_metrics.export()
