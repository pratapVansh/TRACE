"""Reproduce the MissingGreenlet error by uploading a document."""
import asyncio
import uuid
from datetime import UTC, datetime

from app.db.session import async_session_factory
from app.models.user import User
from app.core.security.passwords import hash_password
from sqlalchemy import select

async def setup_test_user():
    """Create a test user with known password and Engineer role."""
    async with async_session_factory() as session:
        # Find the Engineer role
        from app.models.role import Role
        r = await session.execute(
            select(Role).where(Role.name == "Engineer")
        )
        role = r.scalar_one_or_none()
        if role is None:
            print("No Engineer role found!")
            return None

        email = f"upload-test-{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            full_name="Upload Test User",
            email=email,
            password_hash=hash_password("testpass123"),
            role_id=role.id,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user, attribute_names=["id", "created_at"])
        
        print(f"Created test user: {email} / testpass123")
        print(f"User ID: {user.id}")
        
        return email

async def reproduce():
    email = await setup_test_user()
    if not email:
        return

    from app.main import app
    from app.api.deps import get_db, get_current_user
    from app.schemas.auth import UserMeResponse
    from app.services.document_service import DocumentService
    from app.services.document_processing_queue import DocumentProcessingQueueService
    from app.services.document_processing_service import DocumentProcessingService
    from app.services.processing_factory import create_document_processing_service
    from app.core.storage import create_storage_service
    from app.repositories.document_repository import DocumentRepository
    from app.schemas.documents import UploadDocumentRequest

    async with async_session_factory() as session:
        # Create the processing service
        repository = DocumentRepository(session)
        storage = create_storage_service()
        processing_service = create_document_processing_service(session, repository, storage)
        processing_queue = DocumentProcessingQueueService(
            session=session,
            processing_service=processing_service,
            document_repository=repository,
        )
        
        # Create the document service
        doc_service = DocumentService(
            session=session,
            document_repository=repository,
            storage=storage,
            processing_queue=processing_queue,
        )

        # Create a test actor
        actor = UserMeResponse(
            id=uuid.uuid4(),
            email=email,
            full_name="Upload Test User",
            role="Engineer",
            is_active=True,
            created_at=datetime.now(UTC),
        )

        try:
            # Create the upload request
            payload = UploadDocumentRequest(
                filename="test.txt",
                content=b"Hello, this is a test document content.",
                title="Test Upload",
                doc_type="document",
            )
            
            print("Calling upload_document...")
            result = await doc_service.upload_document(actor, payload)
            print(f"SUCCESS! Document uploaded: {result.id}")
            print(f"  mime_type: {result.mime_type}")
            print(f"  filename: {result.original_filename}")
            print(f"  job_id: {result.job_id}")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(reproduce())
