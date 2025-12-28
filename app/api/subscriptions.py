"""
Subscriptions API endpoints
Subscription packages, purchase, payment, and status
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.subscription import SubscriptionPackage, Subscription, PaymentTransaction
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response
import uuid

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
    package_id: int = Field(..., description="Subscription package ID")
    payment_method: Optional[str] = Field(None, description="Payment method code")


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
    invoice_number: str
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
    # Get package
    package = db.query(SubscriptionPackage).filter(
        SubscriptionPackage.id == purchase_data.package_id
    ).first()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription package not found"
        )
    
    # Generate invoice number
    invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}-{int(datetime.now().timestamp())}"
    
    # Create payment transaction
    transaction = PaymentTransaction(
        user_id=current_user.id_users,
        subscription_id=None,  # Will be set after payment success
        invoice_number=invoice_number,
        amount=package.price,
        payment_method=purchase_data.payment_method,
        status="pending"
    )
    
    db.add(transaction)
    
    # TODO: Integrate with DOKU payment gateway
    # For now, generate mock payment URL
    payment_url = f"https://payment.mamastoria.com/checkout/{invoice_number}"
    transaction.payment_url = payment_url
    
    db.commit()
    db.refresh(transaction)
    
    return {
        "ok": True,
        "message": "Transaction created successfully. Please proceed to payment.",
        "data": {
            "invoice_number": transaction.invoice_number,
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
    
    # Extract data
    invoice_number = body.get("order", {}).get("invoice_number")
    transaction_status = body.get("transaction", {}).get("status")
    
    if not invoice_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice number not found"
        )
    
    # Find transaction
    transaction = db.query(PaymentTransaction).filter(
        PaymentTransaction.invoice_number == invoice_number
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
            "invoice_number": transaction.invoice_number,
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
