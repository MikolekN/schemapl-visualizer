#!/usr/bin/env python3

"""Run the configured validation test and export its metrics."""

import logging
import sys
import time

import caise.environment
import caise.http
import caise.logging
import caise.metrics
import tests.health
import tests.reproducibility
import tests.volume

logger = logging.getLogger(__name__)


def run_test() -> float:
    """Run the validation test selected by the environment.

    Returns:
        The selected test's numeric score.

    Raises:
        NotImplementedError: If the configured test name is unknown.
    """
    match caise.environment.CAISE_SERVICE_TEST:
        case "health":
            return tests.health.run()
        case "reproducibility":
            return tests.reproducibility.run()
        case "volume":
            return tests.volume.run()
        case _:
            raise NotImplementedError(
                f"Unknown test: {caise.environment.CAISE_SERVICE_TEST}"
            )


def main() -> int:
    """Run validation with logging and metrics reporting.

    Returns:
        Zero after a successful validation run.
    """
    caise.logging.configure()
    logger.info(
        "Running %s test for service: %s (%s)",
        caise.environment.CAISE_SERVICE_TEST,
        caise.environment.CAISE_SERVICE_NAME,
        caise.environment.CAISE_SERVICE_INSTANCE,
    )

    test_result = 0.0
    test_start = time.perf_counter()
    try:
        test_result = run_test()
    except Exception:
        logger.exception("Error while running test")
        raise
    finally:
        test_stop = time.perf_counter()
        logger.info("Test result: %f", test_result)
        caise.metrics.report_result(test_result, test_stop - test_start)

    logger.info("Test completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
