"""
Subscriptions API endpoints
Subscription packages, purchase, payment, and status
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.subscription import SubscriptionPackage, Subscription, PaymentTransaction, Transaction
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response
import uuid
from app.core.config import settings

router = APIRouter()


# Schemas
class SubscriptionPackageResponse(BaseModel):
    """Subscription package response"""
    id: int
    name: str
    description: Optional[str]
    price: int
    duration_days: int
    publish_quota: int
    bonus_credits: int
    
    class Config:
        from_attributes = True


class PurchaseSubscription(BaseModel):
    """Purchase subscription request"""
    package_id: Optional[int] = Field(None, description="Subscription package ID", alias="packageId")
    package_slug: Optional[str] = Field(None, description="Package slug/name (e.g. credits-20)", alias="packageSlug")
    payment_method: Optional[str] = Field(None, description="Payment method code", alias="paymentMethod")
    
    model_config = ConfigDict(populate_by_name=True)


class PaymentMethod(BaseModel):
    """Payment method"""
    group: str
    code: str
    name: str


class SubscriptionStatusResponse(BaseModel):
    """Subscription status response"""
    has_active_subscription: bool
    package_name: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    days_remaining: Optional[int]
    publish_quota: int


class PaymentHistoryItem(BaseModel):
    """Payment history item"""
    id: int
    invoice_number: Optional[str] = Field(None, alias="invoiceNumber") # Mapped from doku_order_id
    amount: int
    status: str
    payment_method: Optional[str]
    created_at: datetime
    type_transaction: Optional[str]
    
    class Config:
        from_attributes = True


def process_successful_payment(db: Session, transaction: PaymentTransaction) -> bool:
    """
    Process successful payment transaction
    Updates subscription, credits, and transaction status
    """
    # Prevent double processing
    if transaction.status == "success":
        return True
        
    # Get user
    user = db.query(User).filter(User.id_users == transaction.user_id).first()
    if not user:
        print(f"Error: User {transaction.user_id} not found for transaction {transaction.id}")
        return False
        
    # Find package based on amount (temporary solution until package_id is stored in transaction)
    package = db.query(SubscriptionPackage).filter(
        SubscriptionPackage.price == transaction.amount
    ).first()
    
    if not package:
        print(f"Error: Package not found for amount {transaction.amount}")
        return False
        
    print(f"Processing success for user {user.email} package {package.name}")

    # Create or update subscription
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user.id_users
    ).first()
    
    if subscription:
        # Update existing subscription
        subscription.package_id = package.id
        subscription.status = "active"
        subscription.start_date = datetime.utcnow()
        subscription.end_date = datetime.utcnow() + timedelta(days=package.duration_days)
    else:
        # Create new subscription
        subscription = Subscription(
            user_id=user.id_users,
            package_id=package.id,
            status="active",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=package.duration_days)
        )
        db.add(subscription)
    
    db.flush() # Sync ID
    
    # Update transaction
    transaction.status = "success"
    transaction.subscription_id = subscription.id
    
    # Update User Quota/Credits (Accumulate)
    # DISABLED: User requested to handle credit addition on FE side (or not at all here)
    # user.publish_quota += package.publish_quota
    # user.kredit += package.bonus_credits
    
    try:
        db.commit()
        return True
    except Exception as e:
        print(f"Error processing payment: {e}")
        db.rollback()
        return False



@router.get("/subscriptions/packages", response_model=dict)
async def list_packages(db: Session = Depends(get_db)):
    """
    Get all subscription packages
    
    Returns list of available subscription packages with pricing and features
    """
    packages = db.query(SubscriptionPackage).all()
    
    packages_data = [
        SubscriptionPackageResponse.model_validate(pkg).model_dump()
        for pkg in packages
    ]
    
    return {
        "ok": True,
        "data": packages_data
    }


@router.get("/payment-methods", response_model=dict)
async def get_payment_methods():
    """
    Get available payment methods
    
    Returns list of payment methods grouped by type
    """
    methods = [
        {"group": "QRIS", "code": "qris", "name": "QRIS (All E-Wallets)"},
        {"group": "E-Wallet", "code": "gopay", "name": "GoPay"},
        {"group": "E-Wallet", "code": "dana", "name": "DANA"},
        {"group": "E-Wallet", "code": "ovo", "name": "OVO"},
        {"group": "Virtual Account", "code": "bni_va", "name": "BNI Virtual Account"},
        {"group": "Virtual Account", "code": "bri_va", "name": "BRI Virtual Account"},
        {"group": "Virtual Account", "code": "bca_va", "name": "BCA Virtual Account"},
        {"group": "Virtual Account", "code": "mandiri_va", "name": "Mandiri Virtual Account"},
    ]
    
    return {
        "ok": True,
        "data": methods
    }


@router.post("/subscriptions/purchase", response_model=dict, status_code=status.HTTP_201_CREATED)
async def purchase_subscription(
    purchase_data: PurchaseSubscription,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Purchase subscription package
    
    - **package_id**: Subscription package ID
    - **payment_method**: Optional payment method code
    
    Returns payment URL for checkout
    """
    print(f"Purchase request data: {purchase_data.dict(exclude_none=True)}")
    # Get package by ID or Slug
    package = None
    if purchase_data.package_id:
        package = db.query(SubscriptionPackage).filter(
            SubscriptionPackage.id == purchase_data.package_id
        ).first()
    elif purchase_data.package_slug:
         # Try finding by name (slug)
         slug = purchase_data.package_slug
         # Try exact match
         package = db.query(SubscriptionPackage).filter(SubscriptionPackage.name == slug).first()
         if not package:
         # Try robust match (credits-20 -> Credits 20)
             name_guess = slug.replace("-", " ").title()
             package = db.query(SubscriptionPackage).filter(
                 (SubscriptionPackage.name == slug) | 
                 (SubscriptionPackage.name == name_guess) |
                 (SubscriptionPackage.name.ilike(f"%{name_guess}%"))
             ).first()
             
             # Fallback: if slug is like "package-1", try to find by ID 1
             if not package and slug.startswith("package-") and slug.split("-")[-1].isdigit():
                 try:
                     pkg_id = int(slug.split("-")[-1])
                     package = db.query(SubscriptionPackage).filter(SubscriptionPackage.id == pkg_id).first()
                 except:
                     pass
             
             # Debugging log (visible in cloud logs)
             print(f"Package lookup for slug '{slug}': found={package}")
             
             if not package:
                 all_packages = db.query(SubscriptionPackage).all()
                 print(f"Available packages: {[{'id': p.id, 'name': p.name} for p in all_packages]}")
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription package not found (id={purchase_data.package_id}, slug={purchase_data.package_slug})"
        )
    
    # Generate order ID (used as invoice number)
    order_id = f"INV-{uuid.uuid4().hex[:8].upper()}-{int(datetime.now().timestamp())}"
    
    # Set payment expiration (24 hours from now - standard for Doku)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Create payment transaction
    transaction = PaymentTransaction(
        user_id=current_user.id_users,
        subscription_id=None,
        invoice_number=order_id,
        doku_order_id=order_id,
        amount=package.price,
        payment_method=purchase_data.payment_method,
        status="pending",
        type_transaction="subscription",  # Type of transaction
        expires_at=expires_at  # Payment expiration time
    )
    
    db.add(transaction)
    
    # Generate payment URL via Doku API (Sandbox or Production)
    try:
        if settings.USE_MOCK_PAYMENT:
            # Use local mock payment page
            base_url = str(request.base_url).rstrip("/")
            payment_url = f"{base_url}/api/v1/mock-payment/{order_id}"
            print(f"Generated Mock Payment URL: {payment_url}")
        else:
            from app.utils.doku import doku_client
            
            customer_data = {
                "id": current_user.id_users,
                "name": current_user.full_name,
                "email": current_user.email,
                "phone": current_user.phone_number or ""
            }
            
            # Real Doku API call
            payment_url = doku_client.generate_payment_url(
                order_id=order_id,
                amount=package.price,
                customer_data=customer_data,
                package_name=package.name
            )
            print(f"Generated Doku Payment URL: {payment_url}")
        
    except Exception as e:
        print(f"Failed to generate Payment URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Payment gateway error: {str(e)}"
        )
        
    transaction.payment_url = payment_url
    
    db.commit()
    db.refresh(transaction)
    
    return {
        "ok": True,
        "message": "Transaction created successfully. Please proceed to payment.",
        "data": {
            "invoice_number": transaction.doku_order_id, # Map back for frontend
            "amount": transaction.amount,
            "payment_url": transaction.payment_url,
            "package_name": package.name
        }
    }



@router.get("/mock-payment/{order_id}", response_class=HTMLResponse)
async def mock_payment_page(order_id: str, db: Session = Depends(get_db)):
    """
    Mock Payment Page for Development
    """
    # Find transaction
    transaction = db.query(PaymentTransaction).filter(
        PaymentTransaction.doku_order_id == order_id
    ).first()
    
    if not transaction:
        return HTMLResponse(content="<h1>Transaction not found</h1>", status_code=404)
        
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mock Payment Gateway</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f5f5f5; }}
            .card {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; width: 100%; text-align: center; }}
            h1 {{ color: #333; }}
            .amount {{ font-size: 2rem; font-weight: bold; color: #2ecc71; margin: 1rem 0; }}
            .details {{ text-align: left; margin-bottom: 2rem; color: #666; }}
            .btn {{ display: block; width: 100%; padding: 10px; margin: 10px 0; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }}
            .btn-success {{ background-color: #2ecc71; color: white; }}
            .btn-fail {{ background-color: #e74c3c; color: white; }}
            .btn:hover {{ opacity: 0.9; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>MamaStoria Mock Payment</h1>
            <p>Order ID: {order_id}</p>
            <div class="amount">Rp {transaction.amount:,}</div>
            <div class="details">
                <p>Status: {transaction.status}</p>
                <p>Date: {transaction.created_at}</p>
            </div>
            
            <button class="btn btn-success" onclick="completePayment('SUCCESS')">Simulate Success</button>
            <button class="btn btn-fail" onclick="completePayment('FAILED')">Simulate Failure</button>
        </div>

        <script>
            async function completePayment(status) {{
                const payload = {{
                    order: {{ invoice_number: '{order_id}' }},
                    transaction: {{ status: status }}
                }};
                
                try {{
                    const response = await fetch('/api/v1/subscriptions/payment-callback', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(payload)
                    }});
                    
                    const result = await response.json();
                    
                    if (status === 'SUCCESS') {{
                        alert('Payment Successful! You can close this tab.');
                    }} else {{
                        alert('Payment Failed.');
                    }}
                    window.close();
                }} catch (error) {{
                    alert('Error processing callback: ' + error);
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/subscriptions/payment-callback", response_model=dict)
async def payment_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Payment callback from payment gateway (DOKU)
    
    This endpoint receives payment notifications from DOKU
    """
    # Get request body (raw bytes for signature validation)
    raw_body = await request.body()
    try:
        import json
        body = json.loads(raw_body)
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Validate Doku Signature
    signature = request.headers.get("Signature")
    if signature:
        # Real Doku Callback (Sandbox or Production)
        request_id = request.headers.get("Request-Id", "")
        timestamp = request.headers.get("Request-Timestamp", "")
        # Construct target path (path + query)
        target_path = request.url.path
        if request.url.query:
            target_path += "?" + request.url.query
            
        from app.utils.doku import doku_client
        if not doku_client.validate_signature(signature, raw_body, request_id, timestamp, target_path):
            print(f"Invalid Doku Signature! Headers: {request.headers}")
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif settings.DOKU_IS_PRODUCTION:
        # In Production, signature is mandatory
        raise HTTPException(status_code=401, detail="Missing signature")
    else:
        # In Development, allow missing signature (Mock Page)
        pass
    
    # Extract data (DOKU sends invoice number as order id)
    invoice_number = body.get("order", {}).get("invoice_number")
    # Also support searching by doku_order_id directly
    order_id = invoice_number 
    
    transaction_status = body.get("transaction", {}).get("status")
    
    if not order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order ID / Invoice number not found"
        )
    
    # Find transaction by doku_order_id
    transaction = db.query(PaymentTransaction).filter(
        PaymentTransaction.doku_order_id == order_id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Store Doku response for audit trail
    import json
    transaction.doku_response = json.dumps(body)
    
    # Handle payment success
    if transaction_status == "SUCCESS":
        if transaction.status == "pending":
            if process_successful_payment(db, transaction):
                return {"ok": True, "message": "Payment processed successfully"}
            else:
                 # If processing failed (e.g. package not found), return success to Doku but log error
                 # or maybe we should return error to Doku to force manual intervention?
                 # Returning success to Doku prevents endless retries for unfixable errors
                 return {"ok": True, "message": "Payment successful but processing failed (check logs)"}
        elif transaction.status == "success":
             return {"ok": True, "message": "Payment already processed"}

    
    # Handle payment failure or expiration
    if transaction_status in ["FAILED", "EXPIRED"]:
        transaction.status = transaction_status.lower()
        db.commit()
    
    return {"ok": True, "message": "Callback received"}


@router.get("/subscriptions/payment-status/{invoice_number}", response_model=dict)
async def check_payment_status(
    invoice_number: str,
    db: Session = Depends(get_db)
):
    """
    Check payment status by invoice number
    """
    transaction = db.query(PaymentTransaction).filter(
        PaymentTransaction.invoice_number == invoice_number
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Lazy Status Check: If pending, ask Doku
    if transaction.status == "pending" and not settings.USE_MOCK_PAYMENT:
        try:
            from app.utils.doku import doku_client
            # Check status at Doku
            print(f"Checking Doku status for {invoice_number}...")
            status_response = doku_client.check_status(invoice_number)
            
            if status_response:
                doku_status = status_response.get("transaction", {}).get("status")
                print(f"Doku status for {invoice_number}: {doku_status}")
                
                if doku_status == "SUCCESS":
                    # Payment is confirmed by Gateway
                    if process_successful_payment(db, transaction):
                         # Credits given, status updated to success inside logic
                         pass
                    else:
                         # Payment successful at Doku but app processing failed (e.g. package not found)
                         # We force status to success so it's recorded as paid
                         print(f"CRITICAL: Payment {invoice_number} success at Doku but processing failed.")
                         import json
                         transaction.status = "success"
                         transaction.doku_response = json.dumps(status_response)
                         db.commit()
                    
                    db.refresh(transaction)
                elif doku_status in ["FAILED", "EXPIRED"]:
                    transaction.status = doku_status.lower()
                    db.commit()
                    db.refresh(transaction)
        except Exception as e:
            print(f"Failed to auto-update status: {e}")

        
    return {
        "ok": True,
        "data": {
            "invoice_number": transaction.invoice_number,
            "status": transaction.status,
            "amount": transaction.amount,
            "payment_method": transaction.payment_method,
            "created_at": transaction.created_at,
            "payment_url": transaction.payment_url,
            "type_transaction": transaction.type_transaction,
            "expires_at": transaction.expires_at
        }
    }


@router.get("/me/subscription", response_model=dict)
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's subscription status
    
    Returns active subscription details or null if no active subscription
    """
    # Get active subscription
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id_users,
        Subscription.status == "active",
        Subscription.end_date > datetime.utcnow()
    ).first()
    
    if subscription:
        # Get package
        package = db.query(SubscriptionPackage).filter(
            SubscriptionPackage.id == subscription.package_id
        ).first()
        
        days_remaining = (subscription.end_date - datetime.utcnow()).days
        
        return {
            "ok": True,
            "data": {
                "has_active_subscription": True,
                "package_name": package.name if package else None,
                "start_date": subscription.start_date,
                "end_date": subscription.end_date,
                "days_remaining": days_remaining,
                "publish_quota": current_user.publish_quota
            }
        }
    
    return {
        "ok": True,
        "data": {
            "has_active_subscription": False,
            "package_name": None,
            "start_date": None,
            "end_date": None,
            "days_remaining": None,
            "publish_quota": current_user.publish_quota
        }
    }


@router.get("/subscriptions/payment-history", response_model=dict)
async def get_payment_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's payment history
    
    - **page**: Page number
    - **per_page**: Items per page
    
    Returns paginated list of payment transactions ordered by most recent
    """
    query = db.query(PaymentTransaction).filter(
        PaymentTransaction.user_id == current_user.id_users
    ).order_by(PaymentTransaction.created_at.desc())
    
    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    history_data = []
    for transaction in items:

        history_data.append({
            "id": transaction.id,
            "invoice_number": transaction.doku_order_id, # Map doku_order_id to invoice_number for FE compatibility
            "amount": transaction.amount,
            "status": transaction.status,
            "payment_method": transaction.payment_method,
            "created_at": transaction.created_at,
            "type_transaction": transaction.type_transaction
        })
    
    return paginated_response(history_data, page, per_page, total)
@router.get("/transactions/check-status", response_model=dict)
async def check_transaction_status(
    user_id: int,
    type_transaction: str = "topup",
    db: Session = Depends(get_db)
):
    """
    Check if a transaction exists for a user with specific type
    
    - **user_id**: User ID to check
    - **type_transaction**: Transaction type (default: "topup")
    
    Returns true/false in data field
    """
    # Query Transaction table
    exists = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.type == type_transaction
    ).first() is not None
    
    return {
        "ok": True,
        "data": exists
    }


@router.get("/referral/check-bonus", response_model=dict)
async def check_referral_bonus(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Check if user is eligible for referral bonus
    
    - **user_id**: User ID to check
    
    Logic:
    1. Check if user has a parent referral (exists in referrals table as referred_user_id)
    2. If has parent, check if user has any successful subscription payment (type_transaction='subscription')
    3. Return true if both conditions met, false otherwise
    
    Returns boolean indicating eligibility for referral bonus
    """
    from app.models.referral import Referral
    
    # Step 1: Check if user has parent referral
    referral_record = db.query(Referral).filter(
        Referral.referred_user_id == user_id
    ).first()
    
    if not referral_record:
        # No parent referral found
        return {
            "ok": True,
            "data": False,
            "message": "User has no parent referral"
        }
    
    # Step 2: Check if user has successful subscription payment
    has_subscription = db.query(PaymentTransaction).filter(
        PaymentTransaction.user_id == user_id,
        PaymentTransaction.type_transaction == "subscription",
        PaymentTransaction.status == "success"
    ).count() > 0
    
    return {
        "ok": True,
        "data": has_subscription,
        "message": "Eligible for referral bonus" if has_subscription else "No successful subscription payment found",
        "referrer_id": referral_record.referrer_id if has_subscription else None
    }



