"""Verify the fix by calling the service directly."""
import asyncio
import uuid
from datetime import UTC, datetime

from app.db.session import async_session_factory
from app.models.user import User
from app.models.role import Role
from app.core.security.passwords import hash_password
from app.repositories.document_repository import DocumentRepository
from app.core.storage import create_storage_service
from app.services.document_service import DocumentService
from app.services.document_processing_queue import DocumentProcessingQueueService
from app.services.document_processing_service import DocumentProcessingService
from app.services.processing_factory import create_document_processing_service
from app.schemas.auth import UserMeResponse
from app.schemas.documents import UploadDocumentRequest
from sqlalchemy import select, text

async def verify():
    async with async_session_factory() as session:
        # Get our test user from DB
        r = await session.execute(
            select(User).where(User.email == "fix-test@example.com")
        )
        user = r.scalar_one_or_none()
        if not user:
            print("Test user not found")
            return

        # Find the Engineer role for the actor
        r = await session.execute(select(Role).where(Role.name == "Engineer"))
        role = r.scalar_one_or_none()
        role_name = role.name if role else "Engineer"

        actor = UserMeResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=role_name,
            is_active=True,
            created_at=datetime.now(UTC),
        )

        # Create services
        repository = DocumentRepository(session)
        storage = create_storage_service()
        processing_service = create_document_processing_service(session, repository, storage)
        processing_queue = DocumentProcessingQueueService(
            session=session,
            processing_service=processing_service,
            document_repository=repository,
        )
        doc_service = DocumentService(
            session=session,
            document_repository=repository,
            storage=storage,
            processing_queue=processing_queue,
        )

        # Upload a document
        payload = UploadDocumentRequest(
            filename="verify_test.txt",
            content=b"This is a test upload to verify the MissingGreenlet fix.",
            title="Verify Fix Upload",
            doc_type="document",
        )

        print("Calling upload_document...")
        result = await doc_service.upload_document(actor, payload)
        print(f"SUCCESS! Response:")
        print(f"  id: {result.id}")
        print(f"  title: {result.title}")
        print(f"  original_filename: {result.original_filename}")
        print(f"  mime_type: {result.mime_type}")
        print(f"  file_extension: {result.file_extension}")
        print(f"  file_size_bytes: {result.file_size_bytes}")
        print(f"  status: {result.status}")
        print(f"  job_id: {result.job_id}")
        print(f"  uploaded_by: {result.uploaded_by}")
        print(f"  created_at: {result.created_at}")
        print(f"  updated_at: {result.updated_at}")

asyncio.run(verify())
