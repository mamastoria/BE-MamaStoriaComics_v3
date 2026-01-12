
from sqlalchemy.engine.url import make_url
import os

# Simulasi string dari .env user
url_raw = "postgresql://postgres:Aihebat%%401@127.0.0.1:5433/nanobanana_db"
print(f"Raw URL: {url_raw}")

try:
    u = make_url(url_raw)
    print(f"Parsed Password (Default): {u.password}")
except Exception as e:
    print(f"Error parse default: {e}")

# Simulasi fix saya
username = "postgres"
password_raw = u.password # Ini yang didapat sqlalchemy
print(f"SQLAlchemy extracted: {password_raw}")

if password_raw and "%%" in password_raw:
    password_fixed = password_raw.replace("%%", "%")
    print(f"Fixed Password (%% -> %): {password_fixed}")
else:
    print("Fix did not trigger because %% not found in extracted password")

# Test case manual: literal %40
url_encoded = "postgresql://postgres:Aihebat%401@127.0.0.1:5433/nanobanana_db"
u2 = make_url(url_encoded)
print(f"Encoded %40 password: {u2.password}")
