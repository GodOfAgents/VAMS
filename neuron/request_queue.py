import os
import time
import json
import logging
import asyncio
import requests
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("VAMSQueue")

class RequestStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"

@dataclass
class QueuedRequest:
    id: str
    target: str
    payload: Dict[str, Any]
    status: RequestStatus = RequestStatus.PENDING
    retry_count: int = 0
    max_retries: int = 5
    created_at: float = field(default_factory=time.time)
    last_attempt: float = 0.0
    error: Optional[str] = None

class RequestQueue:
    """
    Pillar 4: Request Guarantee.
    Ensures that agent requests (inference, transactions) are eventually processed via retry logic.
    """
    
    BASE_BACKOFF_MS = 1000
    MAX_BACKOFF_MS = 60000
    
    def __init__(self, persistence_path: Optional[str] = "queue_state.json", webhook_url: Optional[str] = None):
        self.queue: Dict[str, QueuedRequest] = {}
        self.persistence_path = persistence_path
        self.webhook_url = webhook_url or os.getenv("VAMS_WEBHOOK_URL")
        self._load_state()
        logger.info(f"Request Queue initialized (Webhook: {'Yes' if self.webhook_url else 'No'})")


    def _load_state(self):
        """Load queue from disk."""
        if self.persistence_path:
            try:
                import os
                if os.path.exists(self.persistence_path):
                    with open(self.persistence_path, 'r') as f:
                        data = json.load(f)
                        for q_id, q_data in data.items():
                            # Rehydrate dataclass manually or use library
                            self.queue[q_id] = QueuedRequest(
                                id=q_data['id'],
                                target=q_data['target'],
                                payload=q_data['payload'],
                                status=RequestStatus(q_data['status']),
                                retry_count=q_data['retry_count'],
                                max_retries=q_data['max_retries'],
                                created_at=q_data['created_at'],
                                last_attempt=q_data.get('last_attempt', 0.0),
                                error=q_data.get('error')
                            )
            except Exception as e:
                logger.error(f"Failed to load queue state: {e}")

    def _save_state(self):
        """Persist queue to disk."""
        if self.persistence_path:
            try:
                data = {}
                for q_id, req in self.queue.items():
                    if req.status not in [RequestStatus.COMPLETED, RequestStatus.DEAD_LETTER]:
                        data[q_id] = {
                            'id': req.id, 'target': req.target, 'payload': req.payload,
                            'status': req.status.value, 'retry_count': req.retry_count,
                            'max_retries': req.max_retries, 'created_at': req.created_at,
                            'last_attempt': req.last_attempt, 'error': req.error
                        }
                with open(self.persistence_path, 'w') as f:
                    json.dump(data, f)
            except Exception as e:
                logger.error(f"Failed to save queue state: {e}")

    def enqueue(self, request_id: str, target: str, payload: Dict[str, Any]) -> str:
        """Add request to queue."""
        req = QueuedRequest(id=request_id, target=target, payload=payload)
        self.queue[request_id] = req
        self._save_state()
        logger.info(f"Request {request_id} enqueued for {target}")
        return request_id

    async def process_queue(self, handler: Callable[[str, Dict[str, Any]], Any]):
        """
        Process pending items in the queue.
        handler: async function(target, payload) -> success (bool)
        """
        now = time.time()
        
        for req_id, req in list(self.queue.items()):
            if req.status in [RequestStatus.COMPLETED, RequestStatus.DEAD_LETTER]:
                continue
                
            if req.status == RequestStatus.PROCESSING:
                continue
                
            # Check backoff
            backoff_s = (self.BASE_BACKOFF_MS * (2 ** req.retry_count)) / 1000.0
            backoff_s = min(backoff_s, self.MAX_BACKOFF_MS / 1000.0)
            
            if now - req.last_attempt < backoff_s:
                continue
                
            # Attempt processing
            req.status = RequestStatus.PROCESSING
            req.last_attempt = now
            req.retry_count += 1
            self._save_state()
            
            try:
                success = await handler(req.target, req.payload)
                if success:
                    req.status = RequestStatus.COMPLETED
                    self._save_state()
                    logger.info(f"Request {req_id} completed successfully")
                else:
                    self._handle_failure(req, "Handler returned false")
            except Exception as e:
                self._handle_failure(req, str(e))
                
    def _handle_failure(self, req: QueuedRequest, error: str):
        req.error = error
        if req.retry_count >= req.max_retries:
            req.status = RequestStatus.DEAD_LETTER
            self._notify_webhook(req, "DEAD_LETTER")
            logger.error(f"Request {req.id} moved to DEAD LETTER: {error}")
        else:
            req.status = RequestStatus.PENDING # Retry pending
            logger.warning(f"Request {req.id} failed (Attempt {req.retry_count}): {error}")
        self._save_state()

    def _notify_webhook(self, req: QueuedRequest, event: str):
        """Send webhook notification for critical events."""
        logger.warning(f"🔔 WEBHOOK ALERT: Request {req.id} {event} - {req.error}")
        
        if not self.webhook_url:
            return
            
        try:
            payload = {
                "event": event,
                "request_id": req.id,
                "target": req.target,
                "error": req.error,
                "retry_count": req.retry_count,
                "timestamp": time.time()
            }
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                logger.info(f"Webhook delivered for {req.id}")
            else:
                logger.warning(f"Webhook failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Webhook error: {e}")

    def get_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        req = self.queue.get(request_id)
        if not req: return None
        return {
            "status": req.status.value,
            "retries": req.retry_count,
            "error": req.error
        }
