"""
Page 3: Admin Signin
Admins are added manually into the `admins` collection (not via signup).
Example document to insert manually in MongoDB:
    {
        "admin_id": "admin1",
        "password": "<sha256 hash - see db.hash_password()>"
    }

Admin capabilities:
  1) View all transactions
  2) View a particular user account + approve/reject pending loans
  3) View all transactions with date-range filters (day/week/month/year)
"""

import streamlit as st
import pandas as pd
import datetime
import base64

from db import (
    admins_col,
    users_col,
    loans_col,
    transactions_col,
    verify_password,
    update_balance,
    record_transaction,
    get_user,
)

st.set_page_config(page_title="Admin Signin", page_icon="🛠️", layout="wide")

# ------------------------------------------------------------------
# SESSION STATE
# ------------------------------------------------------------------
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "current_admin_id" not in st.session_state:
    st.session_state.current_admin_id = None


def admin_logout():
    st.session_state.admin_logged_in = False
    st.session_state.current_admin_id = None


# ------------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------------
if not st.session_state.admin_logged_in:
    st.title("🛠️ Admin Signin")
    st.caption(
        "Admin accounts are created manually in the database and are not "
        "available through public signup."
    )

    with st.form("admin_signin_form"):
        admin_id = st.text_input("Admin ID")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        admin = admins_col().find_one({"admin_id": admin_id.strip()})
        if admin is None:
            st.error("No admin account found with that Admin ID.")
        elif not verify_password(password, admin["password"]):
            st.error("Incorrect password.")
        else:
            st.session_state.admin_logged_in = True
            st.session_state.current_admin_id = admin["admin_id"]
            st.rerun()

    st.stop()

# ------------------------------------------------------------------
# ADMIN DASHBOARD
# ------------------------------------------------------------------
top_l, top_r = st.columns([4, 1])
with top_l:
    st.title(f"🛠️ Admin Dashboard — {st.session_state.current_admin_id}")
with top_r:
    if st.button("Logout", use_container_width=True):
        admin_logout()
        st.rerun()

st.divider()

tab1, tab2, tab3 = st.tabs(
    [
        "📋 All Transactions",
        "👤 View / Approve User Accounts",
        "📊 Filtered Transaction Report",
    ]
)

# ------------------------------------------------------------------
# TAB 1: VIEW ALL TRANSACTIONS
# ------------------------------------------------------------------
with tab1:
    st.subheader("All Transactions")
    txns = list(transactions_col().find().sort("timestamp", -1))
    if not txns:
        st.info("No transactions recorded yet.")
    else:
        df = pd.DataFrame(txns)
        df = df.drop(columns=["_id"], errors="ignore")
        st.dataframe(df, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------
# TAB 2: VIEW A PARTICULAR USER + LOAN APPROVAL
# ------------------------------------------------------------------
with tab2:
    st.subheader("View a Particular User Account")

    all_user_ids = [u["user_id"] for u in users_col().find({}, {"user_id": 1})]
    if not all_user_ids:
        st.info("No users registered yet.")
    else:
        selected_user_id = st.selectbox("Select User ID", all_user_ids)
        user = get_user(selected_user_id)

        if user:
            c1, c2, c3 = st.columns(3)
            c1.metric("Name", user["name"])
            c2.metric("Balance", f"₹{user['balance']:,.2f}")
            c3.metric("Phone", user["phone"])
            st.write(f"**Email:** {user['email']}")

            with st.expander("🪪 View ID Proof Image"):
                try:
                    img_bytes = base64.b64decode(user["id_proof_image"])
                    st.image(img_bytes, caption=user.get("id_proof_filename", "ID Proof"))
                except Exception:
                    st.warning("Could not render ID proof image.")

            st.divider()
            st.markdown("### 📄 Loan Applications")

            user_loans = list(
                loans_col().find({"user_id": selected_user_id}).sort("applied_at", -1)
            )

            if not user_loans:
                st.info("This user has no loan applications.")
            else:
                for loan in user_loans:
                    status = loan["status"]
                    badge = {
                        "PENDING": "🟡 PENDING",
                        "APPROVED": "🟢 APPROVED",
                        "REJECTED": "🔴 REJECTED",
                        "CLOSED": "✅ CLOSED (fully paid)",
                    }.get(status, status)

                    with st.container(border=True):
                        st.write(
                            f"**{loan['loan_type']} Loan** — ₹{loan['amount']:,.2f} "
                            f"for {loan['years']} year(s) — {badge}"
                        )
                        st.write(
                            f"Interest Rate: {loan['interest_rate']}%  |  "
                            f"Total Payable: ₹{loan['total_payable']:,.2f}  |  "
                            f"Paid: ₹{loan['amount_paid']:,.2f}  |  "
                            f"Pending: ₹{loan['pending_balance']:,.2f}"
                        )
                        st.caption(
                            f"Applied at: {loan['applied_at']} | "
                            f"Document: {loan.get('document_filename', 'N/A')}"
                        )

                        if loan.get("document_pdf"):
                            pdf_bytes = base64.b64decode(loan["document_pdf"])
                            st.download_button(
                                "⬇️ Download Verification PDF",
                                data=pdf_bytes,
                                file_name=loan.get("document_filename", "document.pdf"),
                                mime="application/pdf",
                                key=f"dl_{loan['_id']}",
                            )

                        if status == "PENDING":
                            b1, b2 = st.columns(2)
                            with b1:
                                if st.button(
                                    "✅ Approve", key=f"approve_{loan['_id']}",
                                    use_container_width=True,
                                ):
                                    fresh_user = get_user(selected_user_id)
                                    new_balance = (
                                        fresh_user["balance"] + loan["amount"]
                                        + (loan["total_payable"] - loan["amount"])
                                    )
                                    # amount + interest credited to balance
                                    update_balance(selected_user_id, new_balance)
                                    loans_col().update_one(
                                        {"_id": loan["_id"]},
                                        {
                                            "$set": {
                                                "status": "APPROVED",
                                                "decided_at": datetime.datetime.utcnow(),
                                            }
                                        },
                                    )
                                    record_transaction(
                                        selected_user_id,
                                        "LOAN_CREDIT",
                                        loan["total_payable"],
                                        f"{loan['loan_type']} loan approved by "
                                        f"{st.session_state.current_admin_id}; "
                                        f"principal+interest credited",
                                    )
                                    st.success("Loan approved and amount credited!")
                                    st.rerun()
                            with b2:
                                if st.button(
                                    "❌ Reject", key=f"reject_{loan['_id']}",
                                    use_container_width=True,
                                ):
                                    loans_col().update_one(
                                        {"_id": loan["_id"]},
                                        {
                                            "$set": {
                                                "status": "REJECTED",
                                                "decided_at": datetime.datetime.utcnow(),
                                            }
                                        },
                                    )
                                    record_transaction(
                                        selected_user_id,
                                        "LOAN_REJECTED",
                                        loan["amount"],
                                        f"{loan['loan_type']} loan rejected by "
                                        f"{st.session_state.current_admin_id}",
                                    )
                                    st.warning("Loan application rejected.")
                                    st.rerun()

# ------------------------------------------------------------------
# TAB 3: FILTERED TRANSACTION REPORT
# ------------------------------------------------------------------
with tab3:
    st.subheader("Filtered Transaction Report")

    filter_choice = st.selectbox(
        "Filter transactions by", ["1 Day", "1 Week", "1 Month", "1 Year", "Custom Range", "All"]
    )

    now = datetime.datetime.utcnow()
    start_date, end_date = None, now

    if filter_choice == "1 Day":
        start_date = now - datetime.timedelta(days=1)
    elif filter_choice == "1 Week":
        start_date = now - datetime.timedelta(weeks=1)
    elif filter_choice == "1 Month":
        start_date = now - datetime.timedelta(days=30)
    elif filter_choice == "1 Year":
        start_date = now - datetime.timedelta(days=365)
    elif filter_choice == "Custom Range":
        c1, c2 = st.columns(2)
        with c1:
            sd = st.date_input("Start Date", now.date() - datetime.timedelta(days=7))
        with c2:
            ed = st.date_input("End Date", now.date())
        start_date = datetime.datetime.combine(sd, datetime.time.min)
        end_date = datetime.datetime.combine(ed, datetime.time.max)
    else:  # All
        start_date = None

    query = {}
    if start_date is not None:
        query["timestamp"] = {"$gte": start_date, "$lte": end_date}

    filtered_txns = list(transactions_col().find(query).sort("timestamp", -1))

    st.write(f"**{len(filtered_txns)}** transaction(s) found.")

    if filtered_txns:
        df = pd.DataFrame(filtered_txns)
        df = df.drop(columns=["_id"], errors="ignore")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # quick summary by type
        st.markdown("#### Summary by Transaction Type")
        summary = df.groupby("type")["amount"].agg(["count", "sum"]).reset_index()
        summary.columns = ["Transaction Type", "Count", "Total Amount"]
        st.dataframe(summary, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions found for the selected range.")
