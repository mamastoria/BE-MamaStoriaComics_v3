
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize Firebase Admin
try:
    if not firebase_admin._apps:
        # Use default credentials (works on Cloud Run if SA has permissions)
        # Or use service account file if provided in env
        if settings.FIREBASE_CREDENTIALS:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
        else:
            # Default Application Default Credentials (ADC)
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {
                'projectId': settings.GOOGLE_PROJECT_ID
            })
        logger.info("Firebase Admin initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase Admin: {e}")

def send_push_notification(fcm_token: str, title: str, body: str, data: dict = None):
    """
    Send push notification to a single device via FCM
    
    Args:
        fcm_token: The client FCM token
        title: Notification title
        body: Notification body text
        data: Optional data dictionary
        
    Returns:
        str: Message ID if successful, None otherwise
    """
    if not fcm_token:
        logger.warning("Attempted to send push notification without FCM token")
        return None
        
    try:
        # Construct message
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={k: str(v) for k, v in (data or {}).items()}, # Ensure values are strings
            token=fcm_token,
        )
        
        # Send
        response = messaging.send(message)
        logger.info(f"Successfully sent message: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Error sending push notification: {e}")
        return None
