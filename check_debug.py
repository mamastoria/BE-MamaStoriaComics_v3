
from app.core.database import SessionLocal
from app.models.subscription import SubscriptionPackage, PaymentTransaction
from sqlalchemy import text

db = SessionLocal()

print("Checking for package with price 16500:")
pkg = db.query(SubscriptionPackage).filter(SubscriptionPackage.price == 16500).first()
if pkg:
    print(f"FOUND: ID={pkg.id}, Name={pkg.name}, Price={pkg.price}")
else:
    print("NOT FOUND!")

print("\nChecking Transaction status:")
invoice = "INV-34F941C1-1767265816"
trx = db.query(PaymentTransaction).filter(PaymentTransaction.invoice_number == invoice).first()
if trx:
    print(f"Transaction: Invoice={trx.invoice_number}, Status={trx.status}, Amount={trx.amount}, DokuOrderID={trx.doku_order_id}")
    print(f"Doku Response: {trx.doku_response}")
else:
    print("Transaction NOT FOUND")

db.close()
