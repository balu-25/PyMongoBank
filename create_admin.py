
import getpass
import hashlib
import sys

try:
    from pymongo import MongoClient
    import certifi
except ImportError:
    print("Please `pip install pymongo certifi` first.")
    sys.exit(1)

MONGO_URI = input(
    "Paste your MongoDB Atlas connection URI: "
).strip()

if not MONGO_URI:
    print("A connection URI is required.")
    sys.exit(1)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["bank_system"]
admins = db["admins"]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


admin_id = input("New Admin ID: ").strip()
if admins.find_one({"admin_id": admin_id}):
    print(f"An admin with ID '{admin_id}' already exists.")
    sys.exit(1)

password = getpass.getpass("New Admin Password: ")
confirm = getpass.getpass("Confirm Password: ")

if password != confirm:
    print("Passwords do not match.")
    sys.exit(1)

admins.insert_one({"admin_id": admin_id, "password": hash_password(password)})
print(f"✅ Admin '{admin_id}' created successfully.")
