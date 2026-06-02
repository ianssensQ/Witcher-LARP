from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class FastApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        (PROJECT_ROOT / ".test-data").mkdir(exist_ok=True)

    def test_health_endpoint_reports_database_status(self) -> None:
        database_path = (
            PROJECT_ROOT / ".test-data" / f"fastapi_{uuid4().hex}.db"
        )
        settings = Settings(database_path=database_path)
        client = TestClient(create_app(settings))

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"]["status"], "ok")
        self.assertEqual(payload["database"]["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
