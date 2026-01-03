
import sys
from sqlalchemy import create_engine, inspect

DATABASE_NAME = "nanobananacomic-482111-database"
PORT = 5434
# Password attempt: "Aihebat@1" (URL Encoded as Aihebat%401)
DB_URL = f"postgresql+pg8000://postgres:Aihebat%401@127.0.0.1:{PORT}/{DATABASE_NAME}"

print(f"Checking database: {DATABASE_NAME} on port {PORT}...")

try:
    engine = create_engine(DB_URL)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if not tables:
        print("RESULT: 0 Tables found (Empty Database).")
    else:
        print(f"RESULT: {len(tables)} Tables found:")
        for t in tables:
            print(f"- {t}")
            
except Exception as e:
    print("RESULT: Error connecting/inspecting:")
    print(e)
