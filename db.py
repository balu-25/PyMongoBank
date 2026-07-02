import streamlit as st
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import certifi
import datetime
import random
import hashlib


# ----------------------------------------------------------------------
# CONNECTION
# ----------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_client():
    try:
        uri = st.secrets["mongo"]["uri"]
    except Exception:
        st.error(
            "MongoDB URI not found. Add it to `.streamlit/secrets.toml` under "
            "`[mongo]` -> `uri = \"...\"`."
        )
        st.stop()

    try:
        client = MongoClient(uri, tlsCAFile=certifi.where())
        client.admin.command("ping")  # verify connection early
        return client
    except ConnectionFailure as e:
        st.error(f"Could not connect to MongoDB Atlas: {e}")
        st.stop()


def get_db():
    client = get_client()
    return client["bank_system"]  # database name


# Collections (created lazily by MongoDB on first insert)
def users_col():
    return get_db()["users"]


def admins_col():
    return get_db()["admins"]


def transactions_col():
    return get_db()["transactions"]


def loans_col():
    return get_db()["loans"]


# ----------------------------------------------------------------------
# SECURITY HELPERS
# ----------------------------------------------------------------------
def hash_password(password: str) -> str:
    """One-way salted-ish hash. (SHA-256; swap for bcrypt in production.)"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# ----------------------------------------------------------------------
# ACCOUNT / TRANSACTION HELPERS
# ----------------------------------------------------------------------
STARTING_BALANCE = 1000

LOAN_TYPES = ["HOME", "CAR", "EDUCATION", "PERSONAL", "GOLD"]


def generate_interest_rate(loan_type: str, amount: float, years: int) -> float:

    base_rates = {
        "HOME": 7.0,
        "CAR": 9.0,
        "EDUCATION": 6.0,
        "PERSONAL": 12.0,
        "GOLD": 8.0,
    }
    base = base_rates.get(loan_type, 10.0)
    # slight variation based on amount & duration
    amount_factor = min(amount / 100000, 5) * 0.3
    duration_factor = years * 0.15
    random_noise = random.uniform(-0.5, 0.5)
    rate = base + amount_factor + duration_factor + random_noise
    return round(max(rate, 4.0), 2)


def record_transaction(user_id: str, txn_type: str, amount: float, details: str = ""):

    transactions_col().insert_one(
        {
            "user_id": user_id,
            "type": txn_type,
            "amount": amount,
            "details": details,
            "timestamp": datetime.datetime.utcnow(),
        }
    )


def get_user(user_id: str):
    return users_col().find_one({"user_id": user_id})


def update_balance(user_id: str, new_balance: float):
    users_col().update_one({"user_id": user_id}, {"$set": {"balance": new_balance}})


def calc_total_payable(principal: float, rate: float, years: int) -> float:
    """Simple interest total payable = principal + (principal * rate% * years)."""
    interest = principal * (rate / 100) * years
    return round(principal + interest, 2)
