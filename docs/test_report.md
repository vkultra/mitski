# Test Report — $(date +%Y-%m-%d)

## Command
- `pytest`

## Environment
- Python 3.13.2
- Platform: macOS (Darwin)
- Plugins: pytest-asyncio, pytest-cov, Faker, anyio

## Summary
- Collected tests: 301
- Passed: 233
- Skipped: 19
- Failed: 46
- Errors: 3

## Key Failures
- `tests/test_ai_system.py`: multiple failures/errors in Grok client, phase detection, conversation service, and integration flows (likely missing AI service configuration or mocks).
- `tests/test_mirror_system.py`: mirror service and centralized mode scenarios failed, indicating absent Redis/PostgreSQL fixtures or Docker services.
- `tests/test_recovery_bugs.py`: race condition checks errored, pointing to required background workers not running.
- `tests/test_stats_service.py` & `tests/test_stats_worker_chart.py`: stats summary and chart generation mismatches.
- `tests/test_upsell_system.py`: repository CRUD operations failed, suggesting missing database migrations or fixtures.
- `tests/test_workers.py`: Telegram update processing tests failed because external dependencies (Telegram API, task queues) are unavailable in the local test run.

## Notes
- Numerous failures share dependency issues (external APIs, database, queues). Configure the required services or add mocks before rerunning the suite.
- Logging emitted `ValueError: I/O operation on closed file` during graceful shutdown hooks; check logger handlers when running under pytest.
