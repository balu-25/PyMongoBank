"""
Page 1: User Signup
Collects name, phone, email, user id, password, and an ID-proof image.
Stores everything (including the image, base64-encoded) in MongoDB.
On successful creation, starting balance is set to 1000.
"""

import streamlit as st
import base64
import re
import datetime

from db import users_col, hash_password, STARTING_BALANCE, record_transaction

st.set_page_config(page_title="User Signup", page_icon="📝", layout="centered")
st.title("📝 User Signup")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\d{7,15}$")


def user_id_exists(user_id: str) -> bool:
    return users_col().find_one({"user_id": user_id}) is not None


with st.form("signup_form", clear_on_submit=False):
    name = st.text_input("Full Name *")
    phone = st.text_input("Phone Number *")
    email = st.text_input("Email *")
    user_id = st.text_input("Choose a User ID *")
    password = st.text_input("Choose a Password *", type="password")
    confirm_password = st.text_input("Confirm Password *", type="password")
    id_proof = st.file_uploader(
        "Upload ID Proof (image) *", type=["png", "jpg", "jpeg"]
    )

    submitted = st.form_submit_button("Create Account", use_container_width=True)

if submitted:
    errors = []

    if not all([name, phone, email, user_id, password, confirm_password]):
        errors.append("Please fill in all required fields.")
    if email and not EMAIL_RE.match(email):
        errors.append("Please enter a valid email address.")
    if phone and not PHONE_RE.match(phone):
        errors.append("Please enter a valid phone number (digits only, 7-15 chars).")
    if password and confirm_password and password != confirm_password:
        errors.append("Password and Confirm Password do not match.")
    if password and len(password) < 6:
        errors.append("Password should be at least 6 characters long.")
    if id_proof is None:
        errors.append("Please upload an image of your ID proof.")
    if user_id and user_id_exists(user_id):
        errors.append("This User ID is already taken. Please choose another.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        img_bytes = id_proof.read()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        new_user = {
            "name": name.strip(),
            "phone": phone.strip(),
            "email": email.strip().lower(),
            "user_id": user_id.strip(),
            "password": hash_password(password),
            "id_proof_image": img_b64,
            "id_proof_filename": id_proof.name,
            "balance": STARTING_BALANCE,
            "created_at": datetime.datetime.utcnow(),
            "loans": [],  # embedded list of loan application summaries (also stored fully in loans_col)
        }

        users_col().insert_one(new_user)
        record_transaction(
            user_id.strip(), "ACCOUNT_OPENED", STARTING_BALANCE, "Initial balance credited"
        )

        st.success(
            f"🎉 Account created successfully for **{name}**! "
            f"Your starting balance is ₹{STARTING_BALANCE}."
        )
        st.info("Head to **User Signin** from the sidebar to log in.")
        st.balloons()
