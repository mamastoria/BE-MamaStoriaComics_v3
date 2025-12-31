"""
Subscriptions API endpoints
Subscription packages, purchase, payment, and status
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
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
    package_name: Optional[str]
    
    class Config:
        from_attributes = True


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
    
    # Create payment transaction
    transaction = PaymentTransaction(
        user_id=current_user.id_users,
        subscription_id=None,
        invoice_number=None, # Removed from DB
        doku_order_id=order_id, # Use doku_order_id as main identifier
        amount=package.price,
        payment_method=purchase_data.payment_method,
        status="pending"
    )
    
    db.add(transaction)
    
    # Generate payment URL
    # For now, we simulate DOKU Sandbox Checkout URL
    # In production, this should be generated via DOKU API
    if settings.DOKU_IS_PRODUCTION:
        payment_url = f"https://payment.mamastoria.com/checkout/{order_id}"
    else:
        # User requested fix: use sandbox.doku.com or similar for testing
        # Since we don't have full API integration yet, we point to a DOKU Simulator or staying on broken link
        # However, to unblock the user's Flow, let's use a dummy success URL or a generic Sandbox URL
        # payment_url = f"https://sandbox.doku.com/checkout/link/{order_id}" 
        
        # BETTER: Point to a mock payment page on the frontend or backend if DOKU API is not integrated
        # But user specifically asked for "sandbox.doku.com" address because "payment.mamastoria.com" is down
        payment_url = f"https://jokul.doku.com/checkout/link/{order_id}" # Placeholder
        
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


@router.post("/subscriptions/payment-callback", response_model=dict)
async def payment_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Payment callback from payment gateway (DOKU)
    
    This endpoint receives payment notifications from DOKU
    """
    # Get request body
    body = await request.json()
    
    # TODO: Validate DOKU signature
    # signature = request.headers.get("Signature")
    # if not validate_doku_signature(signature, body):
    #     raise HTTPException(status_code=401, detail="Invalid signature")
    
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
    
    # Handle payment success
    if transaction_status == "SUCCESS" and transaction.status == "pending":
        # Update transaction status
        transaction.status = "success"
        
        # Get user and package
        user = db.query(User).filter(User.id_users == transaction.user_id).first()
        
        # Find package from transaction amount (temporary solution)
        package = db.query(SubscriptionPackage).filter(
            SubscriptionPackage.price == transaction.amount
        ).first()
        
        if user and package:
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
            
            # Update transaction with subscription_id
            db.flush()  # Get subscription.id
            transaction.subscription_id = subscription.id
            
            # Add publish quota and bonus credits
            user.publish_quota += package.publish_quota
            user.kredit += package.bonus_credits
            
            db.commit()
            
            return {"ok": True, "message": "Payment processed successfully"}
    
    # Handle payment failure or expiration
    if transaction_status in ["FAILED", "EXPIRED"]:
        transaction.status = transaction_status.lower()
        db.commit()
    
    return {"ok": True, "message": "Callback received"}


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's payment history
    
    Returns list of all payment transactions ordered by most recent
    """
    transactions = db.query(PaymentTransaction).filter(
        PaymentTransaction.user_id == current_user.id_users
    ).order_by(PaymentTransaction.created_at.desc()).all()
    
    history_data = []
    for transaction in transactions:
        # Get package name if subscription exists
        package_name = None
        if transaction.subscription_id:
            subscription = db.query(Subscription).filter(
                Subscription.id == transaction.subscription_id
            ).first()
            if subscription:
                package = db.query(SubscriptionPackage).filter(
                    SubscriptionPackage.id == subscription.package_id
                ).first()
                if package:
                    package_name = package.name
        
        history_data.append({
            "id": transaction.id,
            "invoice_number": transaction.doku_order_id, # Map doku_order_id to invoice_number for FE compatibility
            "amount": transaction.amount,
            "status": transaction.status,
            "payment_method": transaction.payment_method,
            "created_at": transaction.created_at,
            "package_name": package_name
        })
    
    return {
        "ok": True,
        "data": history_data
    }
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
