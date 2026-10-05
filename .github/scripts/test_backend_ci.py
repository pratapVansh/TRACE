"""Safety checks for the CI-only cloud authentication adapter."""

from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from qdrant_client import QdrantClient

from backend_ci import ConfigurationError, RequiredTests, authenticated_qdrant, require_configuration


class BackendCISafetyTests(unittest.TestCase):
    def isolated_configuration(self):
        return {
            "CI_CLOUD_RESOURCES_ISOLATED": "true",
            "QDRANT_URL": "https://ci.example.qdrant.io",
            "TRACE_TEST_QDRANT_URL": "https://ci.example.qdrant.io",
            "QDRANT_API_KEY": "ci-test-key",
            "QDRANT_COLLECTION_NAME": "trace_ci_base",
            "NEO4J_URI": "neo4j+s://ci.example.neo4j.io",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "ci-test-password",
            "NEO4J_DATABASE": "neo4j",
            "SUPABASE_URL": "https://ci.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "ci-test-key",
            "SUPABASE_STORAGE_BUCKET": "trace-ci",
            "GROQ_API_KEY": "ci-test-key",
            "STORAGE_BACKEND": "supabase",
            "DATABASE_URL": "postgresql+asyncpg://trace_ci:ephemeral-ci-password@127.0.0.1:5432/trace_ci",
            "DATABASE_URL_SYNC": "postgresql+psycopg2://trace_ci:ephemeral-ci-password@127.0.0.1:5432/trace_ci",
        }

    def test_missing_configuration_fails(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError):
                require_configuration()

    def test_isolated_configuration_passes_without_network(self):
        with patch.dict(os.environ, self.isolated_configuration(), clear=True):
            require_configuration()

    def test_qdrant_probe_url_must_match_exactly(self):
        settings = self.isolated_configuration()
        settings["QDRANT_URL"] += "/"
        settings["TRACE_TEST_QDRANT_URL"] += "/"
        with patch.dict(os.environ, settings, clear=True):
            with self.assertRaises(ConfigurationError):
                require_configuration()

    def test_credentials_are_scoped_to_approved_qdrant_url(self):
        endpoint = "https://ci.example.qdrant.io"
        calls = []

        def fake_init(self, url=None, api_key=None, timeout=None):
            calls.append((url, api_key))

        fake_get = Mock(return_value=SimpleNamespace(status_code=200))
        with patch.object(QdrantClient, "__init__", fake_init), \
                patch.object(httpx, "get", fake_get):
            with authenticated_qdrant(endpoint, "ci-test-key"):
                QdrantClient(url=endpoint)
                QdrantClient(url="https://other.example.qdrant.io")
                httpx.get(endpoint + "/collections")
                httpx.get("https://other.example.qdrant.io/collections")

        self.assertEqual(calls, [(endpoint, "ci-test-key"),
                                 ("https://other.example.qdrant.io", None)])
        self.assertEqual(fake_get.call_args_list[0].kwargs["headers"],
                         {"api-key": "ci-test-key"})
        self.assertFalse(fake_get.call_args_list[0].kwargs["follow_redirects"])
        self.assertNotIn("headers", fake_get.call_args_list[1].kwargs)

    def test_existing_test_skips_fail_required_gate(self):
        reporter = SimpleNamespace(stats={"skipped": [object()]}, write_sep=Mock())
        manager = SimpleNamespace(get_plugin=lambda name: reporter)
        session = SimpleNamespace(config=SimpleNamespace(pluginmanager=manager), exitstatus=0)
        RequiredTests().pytest_sessionfinish(session, 0)
        self.assertEqual(session.exitstatus, 1)


if __name__ == "__main__":
    unittest.main()
