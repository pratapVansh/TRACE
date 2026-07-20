"""Vault integration for secure secret management."""
import os
import logging
import time
import asyncio
import httpx
from typing import Any

logger = logging.getLogger(__name__)

class VaultClient:
    """Production-ready Vault Client for fetching secrets securely."""
    
    def __init__(self, endpoint: str | None = None, token: str | None = None) -> None:
        self.endpoint = endpoint or os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        self.token = token or os.getenv("VAULT_TOKEN", "")
        self.enabled = bool(self.token)
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 300  # 5 minutes
        self._lock = asyncio.Lock()

    def get_secret(self, path: str, key: str, default: Any = None) -> Any:
        env_key = f"{path.replace('/', '_').upper()}_{key.upper()}"
        if env_key in os.environ:
            return os.environ[env_key]

        if not self.enabled:
            return default

        cache_key = f"{path}:{key}"
        
        # 2. Check Cache for rotation
        if cache_key in self._cache:
            val, expiry = self._cache[cache_key]
            if time.time() < expiry:
                return val

        # 3. Fetch from Vault Sync
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.endpoint}/v1/{path}",
                    headers={"X-Vault-Token": self.token},
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    secret_data = data.get("data", {}).get("data", {}) or data.get("data", {})
                    val = secret_data.get(key, default)
                    self._cache[cache_key] = (val, time.time() + self._cache_ttl)
                    logger.info("Fetched and cached secret (sync) from vault path: %s key: %s", path, key)
                    return val
                else:
                    logger.warning("Vault request failed: %d", response.status_code)
                    return default
        except Exception as e:
            logger.error("Vault fetch error: %s", e)
            return default

    async def get_secret_async(self, path: str, key: str, default: Any = None) -> Any:
        # 1. Environment Variable Fallback
        env_key = f"{path.replace('/', '_').upper()}_{key.upper()}"
        if env_key in os.environ:
            return os.environ[env_key]

        if not self.enabled:
            return default

        cache_key = f"{path}:{key}"
        
        async with self._lock:
            # 2. Check Cache for rotation
            if cache_key in self._cache:
                val, expiry = self._cache[cache_key]
                if time.time() < expiry:
                    return val

            # 3. Fetch from Vault Async
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.endpoint}/v1/{path}",
                        headers={"X-Vault-Token": self.token},
                        timeout=5.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        secret_data = data.get("data", {}).get("data", {}) or data.get("data", {})
                        val = secret_data.get(key, default)
                        self._cache[cache_key] = (val, time.time() + self._cache_ttl)
                        logger.info("Fetched and cached secret from vault path: %s key: %s", path, key)
                        return val
                    else:
                        logger.warning("Vault request failed: %d", response.status_code)
                        return default
            except Exception as e:
                logger.error("Vault fetch error: %s", e)
                return default

vault_client = VaultClient()
