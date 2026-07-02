"""
Page 2: User Signin
After verifying userid/password against MongoDB:
  - Display balance
  - 1) Check Balance
  - 2) Deposit
  - 3) Withdraw
  - 4) Loan Apply (with PDF doc upload, interest calc, pending admin approval)
  - 5) Loan Pay (repay against an approved loan, view pending balance)
"""

import streamlit as st
import base64
import datetime

from db import (
    users_col,
    loans_col,
    verify_password,
    get_user,
    update_balance,
    record_transaction,
    generate_interest_rate,
    calc_total_payable,
    LOAN_TYPES,
)

st.set_page_config(page_title="User Signin", page_icon="🔐", layout="centered")

# ------------------------------------------------------------------
# SESSION STATE INIT
# ------------------------------------------------------------------
if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False
if "current_user_id" not in st.session_state:
    st.session_state.current_user_id = None


def logout():
    st.session_state.user_logged_in = False
    st.session_state.current_user_id = None


# ------------------------------------------------------------------
# LOGIN FORM
# ------------------------------------------------------------------
if not st.session_state.user_logged_in:
    st.title("🔐 User Signin")

    with st.form("signin_form"):
        user_id = st.text_input("User ID")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        user = get_user(user_id.strip())
        if user is None:
            st.error("No account found with that User ID.")
        elif not verify_password(password, user["password"]):
            st.error("Incorrect password.")
        else:
            st.session_state.user_logged_in = True
            st.session_state.current_user_id = user["user_id"]
            st.rerun()

    st.stop()

# ------------------------------------------------------------------
# LOGGED IN VIEW
# ------------------------------------------------------------------
user = get_user(st.session_state.current_user_id)

if user is None:
    st.error("Session error: user not found. Please log in again.")
    logout()
    st.stop()

st.title(f"👋 Welcome, {user['name']}")
col1, col2 = st.columns([3, 1])
with col1:
    st.metric("💰 Current Balance", f"₹{user['balance']:,.2f}")
with col2:
    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

st.divider()

menu = st.selectbox(
    "Select an operation",
    [
        "1) Check Balance",
        "2) Deposit",
        "3) Withdraw",
        "4) Loan Apply",
        "5) Loan Pay",
    ],
)

# ------------------------------------------------------------------
# 1) CHECK BALANCE
# ------------------------------------------------------------------
if menu == "1) Check Balance":
    st.subheader("💰 Check Balance")
    st.success(f"Your current balance is **₹{user['balance']:,.2f}**")

# ------------------------------------------------------------------
# 2) DEPOSIT
# ------------------------------------------------------------------
elif menu == "2) Deposit":
    st.subheader("📥 Deposit")
    amount = st.number_input("Enter amount to deposit", min_value=0.0, step=100.0)
    if st.button("Deposit", use_container_width=True):
        if amount <= 0:
            st.error("Please enter an amount greater than 0.")
        else:
            new_balance = user["balance"] + amount
            update_balance(user["user_id"], new_balance)
            record_transaction(user["user_id"], "DEPOSIT", amount)
            st.success(f"₹{amount:,.2f} deposited successfully!")
            st.info(f"New balance: ₹{new_balance:,.2f}")
            st.rerun()

# ------------------------------------------------------------------
# 3) WITHDRAW
# ------------------------------------------------------------------
elif menu == "3) Withdraw":
    st.subheader("📤 Withdraw")
    amount = st.number_input("Enter amount to withdraw", min_value=0.0, step=100.0)
    if st.button("Withdraw", use_container_width=True):
        if amount <= 0:
            st.error("Please enter an amount greater than 0.")
        elif amount > user["balance"]:
            st.error("Insufficient balance for this withdrawal.")
        else:
            new_balance = user["balance"] - amount
            update_balance(user["user_id"], new_balance)
            record_transaction(user["user_id"], "WITHDRAW", amount)
            st.success(f"₹{amount:,.2f} withdrawn successfully!")
            st.info(f"New balance: ₹{new_balance:,.2f}")
            st.rerun()

# ------------------------------------------------------------------
# 4) LOAN APPLY
# ------------------------------------------------------------------
elif menu == "4) Loan Apply":
    st.subheader("🏠 Loan Apply")

    # Show existing pending loans, if any
    pending = list(
        loans_col().find({"user_id": user["user_id"], "status": "PENDING"})
    )
    if pending:
        st.warning(
            f"You already have {len(pending)} pending loan application(s) "
            "awaiting admin approval."
        )
        for p in pending:
            st.write(
                f"- **{p['loan_type']}** loan of ₹{p['amount']:,.2f} "
                f"for {p['years']} year(s) — Status: **{p['status']}**"
            )
        st.divider()

    loan_type = st.selectbox("Loan Type", LOAN_TYPES)
    loan_amount = st.number_input("Enter Loan Amount", min_value=0.0, step=1000.0)
    years = st.number_input(
        "No. of years you will clear the loan", min_value=1, max_value=30, step=1
    )

    # Show a preview interest rate (recomputed on submit for consistency)
    if loan_amount > 0 and years > 0:
        preview_rate = generate_interest_rate(loan_type, loan_amount, int(years))
        preview_total = calc_total_payable(loan_amount, preview_rate, int(years))
        st.info(
            f"📊 Estimated Interest Rate: **{preview_rate}% p.a.**  \n"
            f"Estimated Total Payable (principal + interest): **₹{preview_total:,.2f}**"
        )

    doc_file = st.file_uploader("Upload Document Verification (PDF)", type=["pdf"])

    if st.button("Submit Loan Application", use_container_width=True):
        if loan_amount <= 0:
            st.error("Please enter a valid loan amount.")
        elif doc_file is None:
            st.error("Please upload your document verification PDF.")
        else:
            rate = generate_interest_rate(loan_type, loan_amount, int(years))
            total_payable = calc_total_payable(loan_amount, rate, int(years))
            pdf_bytes = doc_file.read()
            pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

            loan_doc = {
                "user_id": user["user_id"],
                "user_name": user["name"],
                "loan_type": loan_type,
                "amount": loan_amount,
                "years": int(years),
                "interest_rate": rate,
                "total_payable": total_payable,
                "amount_paid": 0.0,
                "pending_balance": total_payable,
                "document_pdf": pdf_b64,
                "document_filename": doc_file.name,
                "status": "PENDING",  # PENDING / APPROVED / REJECTED
                "applied_at": datetime.datetime.utcnow(),
                "decided_at": None,
            }
            loans_col().insert_one(loan_doc)
            record_transaction(
                user["user_id"],
                "LOAN_APPLY",
                loan_amount,
                f"{loan_type} loan applied, {years} yrs, {rate}% interest — pending approval",
            )

            st.success(
                "✅ Loan application submitted successfully! "
                "It is now **pending admin approval**. The loan amount + interest "
                "will be credited to your balance once approved."
            )
            st.rerun()

# ------------------------------------------------------------------
# 5) LOAN PAY
# ------------------------------------------------------------------
elif menu == "5) Loan Pay":
    st.subheader("💳 Loan Pay")

    approved_loans = list(
        loans_col().find(
            {
                "user_id": user["user_id"],
                "status": "APPROVED",
                "pending_balance": {"$gt": 0},
            }
        )
    )

    if not approved_loans:
        st.info("You have no active loans with a pending balance to repay.")
    else:
        loan_options = {
            f"{l['loan_type']} — ₹{l['amount']:,.0f} ({l['years']}y) | Pending: ₹{l['pending_balance']:,.2f}": l
            for l in approved_loans
        }
        choice = st.selectbox("Select loan to pay", list(loan_options.keys()))
        selected_loan = loan_options[choice]

        st.write(f"**Total Payable:** ₹{selected_loan['total_payable']:,.2f}")
        st.write(f"**Already Paid:** ₹{selected_loan['amount_paid']:,.2f}")
        st.write(f"**Pending Balance:** ₹{selected_loan['pending_balance']:,.2f}")

        pay_amount = st.number_input(
            "Enter amount to pay", min_value=0.0, step=500.0,
            max_value=float(selected_loan["pending_balance"]),
        )

        if st.button("Pay Loan Amount", use_container_width=True):
            if pay_amount <= 0:
                st.error("Please enter a valid amount.")
            elif pay_amount > user["balance"]:
                st.error("Insufficient account balance to make this payment.")
            elif pay_amount > selected_loan["pending_balance"]:
                st.error("Payment exceeds pending loan balance.")
            else:
                new_user_balance = user["balance"] - pay_amount
                new_paid = selected_loan["amount_paid"] + pay_amount
                new_pending = round(selected_loan["pending_balance"] - pay_amount, 2)

                update_balance(user["user_id"], new_user_balance)
                loans_col().update_one(
                    {"_id": selected_loan["_id"]},
                    {
                        "$set": {
                            "amount_paid": new_paid,
                            "pending_balance": new_pending,
                            "status": "APPROVED"
                            if new_pending > 0
                            else "CLOSED",
                        }
                    },
                )
                record_transaction(
                    user["user_id"],
                    "LOAN_PAYMENT",
                    pay_amount,
                    f"{selected_loan['loan_type']} loan repayment, "
                    f"remaining: ₹{new_pending:,.2f}",
                )

                st.success(f"✅ ₹{pay_amount:,.2f} paid towards your loan.")
                st.info(
                    f"New account balance: ₹{new_user_balance:,.2f}  \n"
                    f"Remaining loan balance: ₹{new_pending:,.2f}"
                )
                st.rerun()
