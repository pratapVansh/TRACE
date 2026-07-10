"""Verify the fix by uploading a document via the API."""
import asyncio
from uuid import UUID

import httpx
from app.main import app
from app.core.config import settings

BASE = f"http://localhost:{settings.port}" if hasattr(settings, 'port') else "http://localhost:8000"

async def verify():
    async with httpx.AsyncClient(base_url=BASE) as client:
        # Login
        r = await client.post("/api/auth/login", json={
            "email": "fix-test@example.com",
            "password": "testpass123",
        })
        print(f"Login: {r.status_code}")
        if r.status_code != 200:
            print(r.text)
            return
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload a text file
        content = b"Hello, this is a test document upload."
        files = {
            "file": ("test_upload.txt", content, "text/plain"),
        }
        data = {"title": "Fix Verification Upload", "doc_type": "document"}

        r = await client.post(
            "/api/documents",
            headers=headers,
            data=data,
            files=files,
        )
        print(f"\nUpload: {r.status_code}")
        if r.status_code == 201:
            j = r.json()
            print(f"  id: {j['id']}")
            print(f"  title: {j['title']}")
            print(f"  original_filename: {j['original_filename']}")
            print(f"  mime_type: {j['mime_type']}")
            print(f"  file_extension: {j['file_extension']}")
            print(f"  file_size_bytes: {j['file_size_bytes']}")
            print(f"  status: {j['status']}")
            print(f"  job_id: {j['job_id']}")
            print(f"  doc_type: {j['doc_type']}")
            print("SUCCESS: All expected fields present")
        else:
            print(f"Error: {r.text}")

        # Now check processing status
        if r.status_code == 201:
            doc_id = r.json()["id"]
            import time
            await asyncio.sleep(2)
            r2 = await client.get(
                f"/api/documents/{doc_id}/processing-status",
                headers=headers,
            )
            print(f"\nProcessing status: {r2.status_code}")
            if r2.status_code == 200:
                j2 = r2.json()
                print(f"  status: {j2['status']}")
                print(f"  stage: {j2['stage']}")
                print(f"  document_status: {j2['document_status']}")

asyncio.run(verify())
