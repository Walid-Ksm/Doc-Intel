from app.infrastructure.celery.celery_app import celery_app
from app.infrastructure.celery.tasks import process_document_task

__all__ = ["celery_app", "process_document_task"]
