from passlib.context import CryptContext
import sys

try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password = "12345678"
    print(f"Hashing password: '{password}' (type: {type(password)}, length: {len(password)})")
    
    hashed = pwd_context.hash(password)
    print(f"Hashed: {hashed}")
    
    verify = pwd_context.verify(password, hashed)
    print(f"Verify: {verify}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
