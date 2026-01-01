import hashlib
import hmac
import base64
import json
import uuid
from datetime import datetime
import requests
from app.core.config import settings

class DokuClient:
    def __init__(self):
        self.client_id = settings.DOKU_CLIENT_ID
        self.secret_key = settings.DOKU_SECRET_KEY
        self.is_production = settings.DOKU_IS_PRODUCTION
        self.base_url = "https://api.doku.com" if self.is_production else "https://api-sandbox.doku.com"

    def generate_digest(self, json_body: str) -> str:
        """Generate Digest from request body"""
        digest = hashlib.sha256(json_body.encode('utf-8')).digest()
        return base64.b64encode(digest).decode('utf-8')

    def generate_signature(self, request_id: str, timestamp: str, target_path: str, digest: str) -> str:
        """Generate HMAC-SHA256 Signature"""
        # Format: Client-Id + Request-Id + Request-Timestamp + Request-Target + Digest
        raw_signature = f"Client-Id:{self.client_id}\nRequest-Id:{request_id}\nRequest-Timestamp:{timestamp}\nRequest-Target:{target_path}\nDigest:{digest}"
        
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return f"HMACSHA256={base64.b64encode(signature).decode('utf-8')}"

    def validate_signature(self, signature: str, raw_body: bytes, request_id: str, timestamp: str, target_path: str) -> bool:
        """
        Validate Signature from Doku Notification
        Uses DOKU_NOTIFICATION_SECRET if defined, otherwise falls back to DOKU_SECRET_KEY
        """
        # Determine which secret to use for notifications
        secret = settings.DOKU_NOTIFICATION_SECRET if settings.DOKU_NOTIFICATION_SECRET else self.secret_key
        
        # Calculate digest of the raw body
        digest = hashlib.sha256(raw_body).digest()
        digest_str = base64.b64encode(digest).decode('utf-8')
        
        # Construct raw signature string
        # Format: Client-Id:{client_id}\nRequest-Id:{request_id}...
        # Note: Ensure target_path includes query params if any, Doku usually sends path without host
        raw_signature_str = f"Client-Id:{self.client_id}\nRequest-Id:{request_id}\nRequest-Timestamp:{timestamp}\nRequest-Target:{target_path}\nDigest:{digest_str}"
        
        calculated_signature_bytes = hmac.new(
            secret.encode('utf-8'),
            raw_signature_str.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        calculated_signature = f"HMACSHA256={base64.b64encode(calculated_signature_bytes).decode('utf-8')}"
        
        # Safe comparison
        return hmac.compare_digest(signature, calculated_signature)

    def generate_payment_url(self, order_id: str, amount: int, customer_data: dict, package_name: str) -> str:
        """
        Generate Doku Checkout Payment URL
        """
        target_path = "/checkout/v1/payment"
        request_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Construct Request Body
        body = {
            "order": {
                "amount": amount,
                "invoice_number": order_id,
                "currency": "IDR",
                "callback_url": "https://nanobanana-backend-1089713441636.asia-southeast2.run.app/api/v1/subscriptions/payment-callback", # Fixed for now or typical callback
                # "callback_url": f"{settings.API_BASE_URL}/subscriptions/payment-callback" # Ideal
                "line_items": [
                    {
                        "name": package_name,
                        "price": amount,
                        "quantity": 1
                    }
                ]
            },
            "payment": {
                "payment_due_date": 60 # 60 minutes
            },
            "customer": {
                "id": str(customer_data.get("id", "")),
                "name": customer_data.get("name", "Customer"),
                "email": customer_data.get("email", "nomail@example.com"),
                "phone": customer_data.get("phone", "")
            }
        }
        
        json_body = json.dumps(body)
        digest = self.generate_digest(json_body)
        signature = self.generate_signature(request_id, timestamp, target_path, digest)
        
        headers = {
            "Content-Type": "application/json",
            "Client-Id": self.client_id,
            "Request-Id": request_id,
            "Request-Timestamp": timestamp,
            "Signature": signature
        }
        
        try:
            response = requests.post(
                f"{self.base_url}{target_path}",
                headers=headers,
                data=json_body,
                timeout=10
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and "response" in response_data:
                return response_data["response"]["payment"]["url"]
            elif "message" in response_data:
                 print(f"Doku Error: {response_data}")
                 raise Exception(f"Doku API Error: {response_data['message'][0] if isinstance(response_data['message'], list) else response_data['message']}")
            else:
                 print(f"Doku Unknown Response: {response.text}")
                 raise Exception("Unknown error from Doku Payment Gateway")
                 
        except Exception as e:
            print(f"Doku Request Exception: {str(e)}")
            raise e

    def check_status(self, invoice_number: str) -> dict:
        """
        Check Transaction Status from Doku API
        """
        target_path = f"/orders/v1/status/{invoice_number}"
        request_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # For GET request, body is empty
        json_body = ""
        digest = self.generate_digest(json_body)
        signature = self.generate_signature(request_id, timestamp, target_path, digest)
        
        headers = {
            "Content-Type": "application/json",
            "Client-Id": self.client_id,
            "Request-Id": request_id,
            "Request-Timestamp": timestamp,
            "Signature": signature
        }
        
        try:
            response = requests.get(
                f"{self.base_url}{target_path}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Doku Check Status Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"Doku Check Status Exception: {str(e)}")
            return None

# Global instance
doku_client = DokuClient()
