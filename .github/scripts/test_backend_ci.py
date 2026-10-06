"""Safety checks for the CI-only cloud authentication adapter."""

from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from qdrant_client import QdrantClient

from backend_ci import (
    ConfigurationError, RequiredTests, authenticated_qdrant, base_collection,
    ci_collection, cleanup, current_run_collection, guarded_cloud_writes,
    preflight, require_configuration, storage_prefix,
)


class BackendCISafetyTests(unittest.TestCase):
    def isolated_configuration(self):
        return {
            "GITHUB_ACTIONS": "true",
            "TRACE_CI_RUN_ID": "123_1",
            "QDRANT_URL": "https://ci.example.qdrant.io",
            "TRACE_TEST_QDRANT_URL": "https://ci.example.qdrant.io",
            "QDRANT_API_KEY": "ci-test-key",
            "QDRANT_COLLECTION_NAME": "trace_ci_123_1_base",
            "NEO4J_URI": "neo4j+s://ci.example.neo4j.io",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "ci-test-password",
            "NEO4J_DATABASE": "neo4j",
            "SUPABASE_URL": "https://ci.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "ci-test-key",
            "SUPABASE_STORAGE_BUCKET": "trace",
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

    def test_rejects_non_run_collection_and_non_trace_bucket(self):
        for field, value in (("QDRANT_COLLECTION_NAME", "document_chunks"),
                             ("QDRANT_COLLECTION_NAME", "trace_ci_other_base"),
                             ("SUPABASE_STORAGE_BUCKET", "trace-ci"),
                             ("TRACE_CI_RUN_ID", "../production")):
            config = self.isolated_configuration()
            config[field] = value
            with self.subTest(field=field, value=value), patch.dict(os.environ, config, clear=True):
                with self.assertRaises(ConfigurationError):
                    require_configuration()

    def test_namespace_predicates_are_exact(self):
        with patch.dict(os.environ, self.isolated_configuration(), clear=True):
            self.assertEqual(base_collection(), "trace_ci_123_1_base")
            self.assertEqual(storage_prefix(), "ci/123_1/")
            self.assertTrue(current_run_collection("trace_ci_123_1_itest_abc"))
            for name in ("document_chunks", "trace_ci_other", "trace_ci_123_10_base",
                         "trace_ci_123_1/unsafe", "not_trace_ci_123_1_base"):
                self.assertFalse(current_run_collection(name))
            self.assertTrue(ci_collection("trace_ci_old"))

    def test_preflight_ignores_production_qdrant_data_but_rejects_ci_data(self):
        qdrant = Mock()
        qdrant.get_collections.return_value.collections = [
            SimpleNamespace(name="document_chunks"), SimpleNamespace(name="trace_ci_old")
        ]
        qdrant.count.return_value.count = 0
        qdrant_type = Mock(return_value=qdrant)
        graph_session = Mock()
        graph_session.run.return_value.single.return_value = {"count": 0}
        graph_driver = Mock()
        graph_driver.__enter__ = Mock(return_value=graph_driver)
        graph_driver.__exit__ = Mock(return_value=None)
        graph_driver.session.return_value.__enter__ = Mock(return_value=graph_session)
        graph_driver.session.return_value.__exit__ = Mock(return_value=None)
        http_client = Mock()
        http_client.__enter__ = Mock(return_value=http_client)
        http_client.__exit__ = Mock(return_value=None)
        http_client.get.return_value.json.return_value = {"public": False}
        http_client.post.return_value.json.return_value = []
        with patch.dict(os.environ, self.isolated_configuration(), clear=True), \
                patch("qdrant_client.QdrantClient", qdrant_type), \
                patch("neo4j.GraphDatabase.driver", return_value=graph_driver), \
                patch("httpx.Client", return_value=http_client), \
                patch("httpx.get"), patch("backend_ci.graph_probe"):
            preflight()
            qdrant.count.assert_called_once_with("trace_ci_old", exact=True)
            self.assertEqual(http_client.post.call_args.kwargs["json"]["prefix"], "ci/123_1/")
            qdrant.count.return_value.count = 1
            with self.assertRaises(ConfigurationError):
                preflight()

    def test_qdrant_write_guard_rejects_production_and_other_runs(self):
        with patch.dict(os.environ, self.isolated_configuration(), clear=True), \
                patch.object(QdrantClient, "delete_collection", return_value=True) as deleted:
            with guarded_cloud_writes():
                client = object.__new__(QdrantClient)
                for name in ("document_chunks", "trace_ci_999_1_base"):
                    with self.assertRaises(ConfigurationError):
                        client.delete_collection(collection_name=name)
                client.delete_collection(collection_name="trace_ci_123_1_itest_abc")
            deleted.assert_called_once()

    def test_storage_guard_rejects_unowned_paths(self):
        from app.core.storage.supabase_storage import SupabaseStorageBackend
        with tempfile.TemporaryDirectory() as temp, \
                patch.dict(os.environ, {**self.isolated_configuration(), "RUNNER_TEMP": temp}, clear=True):
            storage = SupabaseStorageBackend(
                url="https://ci.supabase.co", service_role_key="key", bucket="trace"
            )
            with guarded_cloud_writes():
                path = storage.build_document_path(uuid4(), 1, "test.pdf")
                self.assertTrue(path.startswith("ci/123_1/documents/"))
                for outside in ("documents/prod/file.pdf", "ci/123_10/file.pdf"):
                    with self.assertRaises(ConfigurationError):
                        storage.delete(outside)
                    with self.assertRaises(ConfigurationError):
                        storage.save(outside, b"test")
                with self.assertRaises(ConfigurationError):
                    storage.delete(path)

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
