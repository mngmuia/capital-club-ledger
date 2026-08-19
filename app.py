import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.set_page_config(page_title="ChamaYetu", page_icon="💰", layout="wide")

APP_ROLES = [
    "Member", "Approver", "Accountant", "Treasurer",
    "Administrator", "Admin", "Chairperson", "Auditor", "Secretary"
]

MENU_ITEMS = ["Dashboard", "My Statement", "Contributions", "Loans", "Withdrawals", "Meetings"]


@st.cache_resource
def get_supabase_client():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_ANON_KEY in Streamlit secrets.")
        st.stop()
    return create_client(url, key)


supabase = get_supabase_client()


def money(value):
    try:
        return f"KES {float(value or 0):,.2f}"
    except Exception:
        return "KES 0.00"


def safe_execute(query, fallback=None):
    try:
        return query.execute()
    except Exception as exc:
        st.error(str(exc))
        return fallback


def safe_table_df(table_name, order_col=None):
    try:
        q = supabase.table(table_name).select("*")
        if order_col:
            q = q.order(order_col, desc=True)
        res = q.execute()
        return pd.DataFrame(res.data or [])
    except Exception:
        return pd.DataFrame()


def upload_file_to_supabase(bucket_name, file, folder_name="loan-documents"):
    if file is None:
        return None
    safe_name = file.name.replace(" ", "_")
    file_path = f"{folder_name}/{date.today().isoformat()}_{safe_name}"
    supabase.storage.from_(bucket_name).upload(
        file_path,
        file.getvalue(),
        {"content-type": file.type or "application/octet-stream", "upsert": "true"}
    )
    return supabase.storage.from_(bucket_name).get_public_url(file_path)


def get_members():
    try:
        res = supabase.table("members").select("*").order("member_no").execute()
        return res.data or []
    except Exception:
        return []


def normalise_member(row):
    if not row:
        return None
    return {
        "id": row.get("id"),
        "member_no": row.get("member_no") or "",
        "full_name": row.get("full_name") or row.get("name") or row.get("email") or "Member",
        "email": row.get("email") or "",
        "role": row.get("role") or "Member",
        "current_balance": row.get("current_balance") or 0,
    }


def render_login_bar():
    members = get_members()
    if not members:
        st.warning("No members found. Run the SQL script first and add members to the members table.")
        return None, "Member"

    options = {
        f"{m.get('member_no') or ''} - {m.get('full_name') or m.get('email') or m.get('id')}": m
        for m in members
    }

    c1, c2, c3 = st.columns([2, 3, 1])
    with c1:
        selected_label = st.selectbox("Signed in as", list(options.keys()), index=0)
    selected_member = normalise_member(options[selected_label])

    user_role = selected_member.get("role") or "Member"
    default_index = APP_ROLES.index(user_role) if user_role in APP_ROLES else 0
    with c2:
        active_role = st.selectbox("Active role", APP_ROLES, index=default_index)
    with c3:
        st.write("")
        st.write("")
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.session_state["current_user"] = selected_member
    st.session_state["active_role"] = active_role
    return selected_member, active_role


def render_navigation():
    selected = st.radio("Navigation", MENU_ITEMS, horizontal=True, label_visibility="collapsed")
    st.caption("Menus are based on the active role. Member sees member screens, Approver sees queues, and Admin/Auditor sees reporting screens.")
    return selected


def render_dashboard(current_user):
    st.title("Dashboard")
    st.write(f"Welcome, **{current_user.get('full_name')}**.")
    st.info("Use the Loans tab for the new Method B loan workflow and manual reference verification.")


def render_placeholder(title):
    st.title(title)
    st.info(f"{title} module is retained as a placeholder in this replacement package. The Loans module contains the full update requested.")


def render_loans_page():
    st.title("Loans")
    current_user = st.session_state.get("current_user")
    active_role = st.session_state.get("active_role", "Member")
    if not current_user:
        st.error("No logged-in member found.")
        return

    if active_role == "Member":
        render_member_loans_workspace(current_user)
    elif active_role in ["Approver", "Loan Approver"]:
        render_approver_loans_workspace(current_user)
    elif active_role in ["Accountant", "Treasurer"]:
        render_accountant_loans_workspace(current_user)
    elif active_role in ["Administrator", "Admin", "Chairperson", "Auditor", "Secretary"]:
        render_loan_book_workspace(current_user, read_only=(active_role == "Auditor"))
    else:
        st.warning("You do not have access to the loan module.")


# =====================================================
# MEMBER LOANS
# =====================================================

def render_member_loans_workspace(current_user):
    st.subheader("My Loans")
    member_id = current_user["id"]
    show_member_entitlement(member_id)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Current Loans", use_container_width=True):
            st.session_state["member_loan_view"] = "current"
    with c2:
        if st.button("Historical Loans", use_container_width=True):
            st.session_state["member_loan_view"] = "historical"
    with c3:
        if st.button("Guaranteed Loans", use_container_width=True):
            st.session_state["member_loan_view"] = "guaranteed"
    with c4:
        if st.button("Apply for Loan", use_container_width=True):
            st.session_state["member_loan_view"] = "apply"

    st.divider()
    selected_view = st.session_state.get("member_loan_view", "current")
    if selected_view == "current":
        show_member_current_loans(member_id)
    elif selected_view == "historical":
        show_member_historical_loans(member_id)
    elif selected_view == "guaranteed":
        show_member_guaranteed_loans(member_id)
    elif selected_view == "apply":
        show_loan_application_form(current_user)


def show_member_entitlement(member_id):
    try:
        res = supabase.table("member_loan_entitlement").select("*").eq("member_id", member_id).execute()
        rows = res.data or []
    except Exception as exc:
        st.error(f"Loan entitlement view not available: {exc}")
        return
    if not rows:
        st.info("Loan entitlement is not available for this member.")
        return
    e = rows[0]
    st.markdown("### My Current Loan Entitlement")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Member Balance", money(e.get("member_balance")))
    c2.metric("Loan Multiple", f"{e.get('loan_multiple', 3)}x")
    c3.metric("Gross Entitlement", money(e.get("gross_entitlement")))
    c4.metric("Less Loans/Guarantees", money(float(e.get("outstanding_own_loans") or 0) + float(e.get("active_guarantees") or 0)))
    c5.metric("Available Entitlement", money(e.get("available_entitlement")))


def show_member_current_loans(member_id):
    st.markdown("### My Current Loans")
    res = supabase.table("current_loan_book").select("*").eq("member_id", member_id).in_("status", ["Disbursed", "Active", "Defaulted"]).execute()
    loans = res.data or []
    if not loans:
        st.info("You have no current loans.")
        return
    for loan in loans:
        with st.expander(f"{loan['loan_ref']} - {money(loan.get('outstanding_total'))} outstanding"):
            display_loan_details(loan)
            show_member_loan_schedule(loan["id"])
            show_manual_repayment_upload_form(loan, member_id)


def show_member_historical_loans(member_id):
    st.markdown("### My Historical Loans")
    res = supabase.table("current_loan_book").select("*").eq("member_id", member_id).in_("status", ["Fully Repaid", "Cancelled"]).execute()
    loans = res.data or []
    if not loans:
        st.info("No historical loans found.")
        return
    st.dataframe(pd.DataFrame(loans), use_container_width=True)


def show_member_guaranteed_loans(member_id):
    st.markdown("### Loans I Have Guaranteed")
    res = supabase.table("loan_guarantors").select("*, loan_applications(loan_ref, loan_amount, status, outstanding_total)").eq("guarantor_id", member_id).execute()
    rows = res.data or []
    if not rows:
        st.info("You have not guaranteed any loans.")
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def show_loan_application_form(current_user):
    st.markdown("### Apply for Loan")
    member_id = current_user["id"]
    available_entitlement = 0.0
    try:
        ent = supabase.table("member_loan_entitlement").select("available_entitlement").eq("member_id", member_id).execute()
        if ent.data:
            available_entitlement = float(ent.data[0].get("available_entitlement") or 0)
    except Exception:
        pass
    st.info(f"Current available loan entitlement: {money(available_entitlement)}")

    with st.form("loan_application_form"):
        loan_amount = st.number_input("Loan Amount", min_value=0.0, step=1000.0)
        repayment_months = st.number_input("Repayment Months", min_value=1, max_value=60, value=12)
        interest_rate = st.number_input("Interest Rate (%)", min_value=0.0, max_value=100.0, value=12.0)
        loan_purpose = st.text_area("Purpose of Loan")
        submitted = st.form_submit_button("Submit Loan Application")

    if submitted:
        if loan_amount <= 0:
            st.error("Loan amount must be greater than zero.")
            return
        if available_entitlement > 0 and loan_amount > available_entitlement:
            st.error("The requested loan amount exceeds your available entitlement.")
            return
        loan_ref = f"LN-{date.today().strftime('%Y%m%d')}-{str(member_id)[:8]}"
        try:
            supabase.table("loan_applications").insert({
                "loan_ref": loan_ref,
                "borrower_id": member_id,
                "loan_amount": loan_amount,
                "interest_rate": interest_rate,
                "repayment_months": repayment_months,
                "loan_purpose": loan_purpose,
                "status": "Submitted",
                "created_by": member_id
            }).execute()
            st.success(f"Loan application submitted successfully. Reference: {loan_ref}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def display_loan_details(loan):
    c1, c2, c3 = st.columns(3)
    c1.write(f"Loan Amount: **{money(loan.get('loan_amount'))}**")
    c1.write(f"Status: **{loan.get('status')}**")
    c2.write(f"Interest Rate: **{loan.get('interest_rate')}%**")
    c2.write(f"Months: **{loan.get('repayment_months')}**")
    c3.write(f"Monthly Repayment: **{money(loan.get('monthly_repayment'))}**")
    c3.write(f"Outstanding Total: **{money(loan.get('outstanding_total'))}**")


def show_member_loan_schedule(loan_id):
    st.markdown("#### Repayment Schedule")
    res = supabase.table("loan_repayment_schedule").select("*").eq("loan_id", loan_id).order("installment_no").execute()
    schedule = res.data or []
    if not schedule:
        st.info("Repayment schedule is not yet available.")
        return
    st.dataframe(pd.DataFrame(schedule), use_container_width=True)


def show_manual_repayment_upload_form(loan, member_id):
    st.markdown("#### Upload Repayment Reference")
    schedule_res = supabase.table("loan_repayment_schedule").select("*").eq("loan_id", loan["id"]).in_("status", ["Upcoming", "Due", "Partially Paid", "Overdue"]).order("installment_no").execute()
    schedules = schedule_res.data or []
    if not schedules:
        st.info("There are no unpaid schedule lines for this loan.")
        return
    schedule_options = {f"Installment {s['installment_no']} - Due {s['due_date']} - {money(s['balance_due'])}": s["id"] for s in schedules}
    with st.form(f"manual_repayment_form_{loan['id']}"):
        selected_schedule_label = st.selectbox("Select Repayment Instalment", list(schedule_options.keys()))
        amount_paid = st.number_input("Amount Paid", min_value=0.0, step=100.0)
        payment_method = st.selectbox("Payment Method", ["M-Pesa", "Bank Transfer", "Cash Deposit", "Other"])
        reference_no = st.text_input("Payment Reference Number")
        reference_file = st.file_uploader("Upload Payment Evidence", type=["pdf", "png", "jpg", "jpeg"])
        submitted = st.form_submit_button("Submit Reference for Verification")
    if submitted:
        if amount_paid <= 0:
            st.error("Amount paid must be greater than zero.")
            return
        if not reference_no.strip():
            st.error("Payment reference number is required.")
            return
        document_url = upload_file_to_supabase("loan-documents", reference_file, "repayment-references") if reference_file else None
        try:
            supabase.table("loan_repayment_references").insert({
                "loan_id": loan["id"],
                "schedule_id": schedule_options[selected_schedule_label],
                "member_id": member_id,
                "amount_paid": amount_paid,
                "payment_method": payment_method,
                "reference_no": reference_no.strip(),
                "reference_document_url": document_url,
                "verification_status": "Pending Verification",
                "submitted_by": member_id
            }).execute()
            st.success("Payment reference submitted successfully and is awaiting verification.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not submit reference. It may already exist. Details: {exc}")


# =====================================================
# APPROVER WORKSPACE
# =====================================================

def render_approver_loans_workspace(current_user):
    st.subheader("Loans Pending Checking and Approval")
    res = supabase.table("current_loan_book").select("*").in_("status", ["Submitted", "Checked"]).order("created_at", desc=True).execute()
    loans = res.data or []
    if not loans:
        st.info("No loans are currently pending checking or approval.")
        return
    for loan in loans:
        with st.expander(f"{loan['loan_ref']} - {loan['borrower_name']} - {money(loan['loan_amount'])}"):
            display_loan_details(loan)
            st.write(f"Current status: **{loan['status']}**")
            if loan["status"] == "Submitted":
                if st.button("Check Loan", key=f"check_{loan['id']}"):
                    supabase.rpc("check_loan", {"p_loan_id": loan["id"], "p_checked_by": current_user["id"]}).execute()
                    st.success("Loan checked successfully.")
                    st.rerun()
            elif loan["status"] == "Checked":
                if loan.get("checked_by") == current_user["id"]:
                    st.warning("You checked this loan. You cannot approve the same loan.")
                else:
                    if st.button("Approve Loan", key=f"approve_{loan['id']}"):
                        try:
                            supabase.rpc("approve_loan", {"p_loan_id": loan["id"], "p_approved_by": current_user["id"]}).execute()
                            st.success("Loan approved successfully.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))


# =====================================================
# ACCOUNTANT WORKSPACE
# =====================================================

def render_accountant_loans_workspace(current_user):
    st.subheader("Loan Liquidation, Disbursement and Repayment Verification")
    tab1, tab2 = st.tabs(["Approved Loans for Disbursement", "Manual Repayment References"])
    with tab1:
        show_approved_loans_for_disbursement(current_user)
    with tab2:
        show_manual_repayment_verification_queue(current_user)


def show_approved_loans_for_disbursement(current_user):
    statuses = ["Approved", "Linked to Asset", "Liquidation Initiated", "Liquidation Completed", "Bank Transfer Initiated", "Bank Transfer Document Uploaded", "Bank Transfer Confirmed"]
    res = supabase.table("current_loan_book").select("*").in_("status", statuses).order("approved_at", desc=True).execute()
    loans = res.data or []
    if not loans:
        st.info("No approved loans are awaiting liquidation or disbursement.")
        return
    for loan in loans:
        with st.expander(f"{loan['loan_ref']} - {loan['borrower_name']} - {loan['status']}"):
            display_loan_details(loan)
            if loan["status"] == "Approved":
                show_asset_linking_form(loan)
            elif loan["status"] == "Linked to Asset":
                if st.button("Initiate Liquidation", key=f"start_liq_{loan['id']}"):
                    supabase.table("loan_applications").update({"status": "Liquidation Initiated", "updated_at": "now()"}).eq("id", loan["id"]).execute()
                    st.success("Liquidation initiated.")
                    st.rerun()
            elif loan["status"] == "Liquidation Initiated":
                show_liquidation_completion_form(loan, current_user)
            elif loan["status"] == "Liquidation Completed":
                show_bank_transfer_upload_form(loan)
            elif loan["status"] == "Bank Transfer Document Uploaded":
                show_bank_transfer_confirmation(loan, current_user)


def show_asset_linking_form(loan):
    with st.form(f"asset_link_form_{loan['id']}"):
        asset_name = st.text_input("Asset Name")
        submitted = st.form_submit_button("Link Loan to Asset")
    if submitted:
        supabase.table("loan_applications").update({"asset_name": asset_name, "status": "Linked to Asset"}).eq("id", loan["id"]).execute()
        st.success("Loan linked to asset.")
        st.rerun()


def show_liquidation_completion_form(loan, current_user):
    with st.form(f"liq_complete_form_{loan['id']}"):
        liquidation_reference = st.text_input("Liquidation Reference")
        liquidation_file = st.file_uploader("Upload Liquidation Evidence", type=["pdf", "png", "jpg", "jpeg"])
        submitted = st.form_submit_button("Confirm Liquidation Completed")
    if submitted:
        document_url = upload_file_to_supabase("loan-documents", liquidation_file, "liquidation-documents") if liquidation_file else None
        supabase.table("loan_applications").update({
            "liquidation_reference": liquidation_reference,
            "liquidation_document_url": document_url,
            "liquidation_confirmed_by": current_user["id"],
            "liquidation_confirmed_at": date.today().isoformat(),
            "status": "Liquidation Completed"
        }).eq("id", loan["id"]).execute()
        st.success("Liquidation completed.")
        st.rerun()


def show_bank_transfer_upload_form(loan):
    with st.form(f"bank_transfer_form_{loan['id']}"):
        transfer_reference = st.text_input("Bank Transfer Reference")
        transfer_file = st.file_uploader("Upload Bank Transfer Evidence", type=["pdf", "png", "jpg", "jpeg"])
        submitted = st.form_submit_button("Upload Bank Transfer Document")
    if submitted:
        document_url = upload_file_to_supabase("loan-documents", transfer_file, "bank-transfer-documents") if transfer_file else None
        supabase.table("loan_applications").update({
            "bank_transfer_reference": transfer_reference,
            "bank_transfer_document_url": document_url,
            "status": "Bank Transfer Document Uploaded"
        }).eq("id", loan["id"]).execute()
        st.success("Bank transfer document uploaded.")
        st.rerun()


def show_bank_transfer_confirmation(loan, current_user):
    first_due_date = st.date_input("First Repayment Due Date", value=date.today(), key=f"first_due_{loan['id']}")
    if st.button("Confirm Bank Transfer and Generate Schedule", key=f"confirm_disb_{loan['id']}"):
        supabase.table("loan_applications").update({
            "bank_transfer_confirmed_by": current_user["id"],
            "bank_transfer_confirmed_at": date.today().isoformat(),
            "status": "Bank Transfer Confirmed"
        }).eq("id", loan["id"]).execute()
        supabase.rpc("generate_loan_schedule", {"p_loan_id": loan["id"], "p_first_due_date": first_due_date.isoformat()}).execute()
        st.success("Bank transfer confirmed, loan disbursed, and repayment schedule generated.")
        st.rerun()


def show_manual_repayment_verification_queue(current_user):
    st.markdown("### Manual Repayment References Awaiting Verification")
    res = supabase.table("loan_repayment_references").select("*, loan_applications(loan_ref), members(full_name, member_no)").eq("verification_status", "Pending Verification").order("submitted_at", desc=True).execute()
    refs = res.data or []
    if not refs:
        st.info("No repayment references are awaiting verification.")
        return
    for ref in refs:
        member = ref.get("members") or {}
        loan = ref.get("loan_applications") or {}
        with st.expander(f"{loan.get('loan_ref')} - {member.get('full_name')} - {money(ref.get('amount_paid'))}"):
            st.write(f"Member: {member.get('member_no')} - {member.get('full_name')}")
            st.write(f"Amount Paid: {money(ref.get('amount_paid'))}")
            st.write(f"Payment Method: {ref.get('payment_method')}")
            st.write(f"Reference Number: {ref.get('reference_no')}")
            st.write(f"Submitted At: {ref.get('submitted_at')}")
            if ref.get("reference_document_url"):
                st.markdown(f"[Open uploaded evidence]({ref.get('reference_document_url')})")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verify and Post Repayment", key=f"verify_ref_{ref['id']}"):
                    try:
                        supabase.rpc("verify_loan_repayment_reference", {"p_reference_id": ref["id"], "p_verified_by": current_user["id"]}).execute()
                        st.success("Repayment reference verified and posted successfully.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            with col2:
                rejection_reason = st.text_input("Rejection Reason", key=f"reject_reason_{ref['id']}")
                if st.button("Reject Reference", key=f"reject_ref_{ref['id']}"):
                    supabase.rpc("reject_loan_repayment_reference", {
                        "p_reference_id": ref["id"],
                        "p_rejected_by": current_user["id"],
                        "p_rejection_reason": rejection_reason or "Reference rejected after manual verification."
                    }).execute()
                    st.warning("Reference rejected.")
                    st.rerun()


# =====================================================
# ADMIN / AUDITOR REPORTING
# =====================================================

def render_loan_book_workspace(current_user, read_only=False):
    st.subheader("Loan Book")
    if read_only:
        st.info("Auditor mode is read-only.")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["All Loans", "Repayment Schedule", "Repayment References", "Loan Book Summary", "Notifications"])
    with tab1:
        show_all_loans()
    with tab2:
        show_all_repayment_schedules()
    with tab3:
        show_all_repayment_references()
    with tab4:
        show_loan_book_summary()
    with tab5:
        show_notifications()


def show_all_loans():
    df = safe_table_df("current_loan_book", "created_at")
    if df.empty:
        st.info("No loans found.")
    else:
        st.dataframe(df, use_container_width=True)


def show_all_repayment_schedules():
    try:
        res = supabase.table("loan_repayment_schedule").select("*, loan_applications(loan_ref, borrower_id)").order("due_date").execute()
        rows = res.data or []
    except Exception as exc:
        st.error(str(exc))
        rows = []
    if not rows:
        st.info("No repayment schedules found.")
    else:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


def show_all_repayment_references():
    try:
        res = supabase.table("loan_repayment_references").select("*, loan_applications(loan_ref), members(full_name, member_no)").order("submitted_at", desc=True).execute()
        rows = res.data or []
    except Exception as exc:
        st.error(str(exc))
        rows = []
    if not rows:
        st.info("No repayment references found.")
    else:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


def show_loan_book_summary():
    try:
        res = supabase.table("current_loan_book").select("*").execute()
        loans = res.data or []
    except Exception as exc:
        st.error(str(exc))
        loans = []
    total_active = len([x for x in loans if x.get("status") in ["Disbursed", "Active", "Defaulted"]])
    total_loan_book = sum(float(x.get("outstanding_total") or 0) for x in loans)
    total_principal = sum(float(x.get("outstanding_principal") or 0) for x in loans)
    total_interest = sum(float(x.get("outstanding_interest") or 0) for x in loans)
    pending_approval = len([x for x in loans if x.get("status") in ["Submitted", "Checked"]])
    pending_disbursement = len([x for x in loans if x.get("status") in ["Approved", "Linked to Asset", "Liquidation Initiated", "Liquidation Completed", "Bank Transfer Initiated", "Bank Transfer Document Uploaded"]])
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Loans", total_active)
    c2.metric("Current Loan Book", money(total_loan_book))
    c3.metric("Outstanding Principal", money(total_principal))
    c4, c5, c6 = st.columns(3)
    c4.metric("Outstanding Interest", money(total_interest))
    c5.metric("Pending Approval", pending_approval)
    c6.metric("Pending Disbursement", pending_disbursement)


def show_notifications():
    df = safe_table_df("loan_notification_queue", "created_at")
    if df.empty:
        st.info("No notification queue records found.")
    else:
        st.dataframe(df, use_container_width=True)
    if st.button("Create repayment reminders for today"):
        try:
            supabase.rpc("create_loan_repayment_reminders", {}).execute()
            st.success("Reminder queue updated.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


# =====================================================
# MAIN APP
# =====================================================

def main():
    st.markdown("## ChamaYetu")
    current_user, active_role = render_login_bar()
    if not current_user:
        return
    selected_menu = render_navigation()
    if selected_menu == "Dashboard":
        render_dashboard(current_user)
    elif selected_menu == "Loans":
        render_loans_page()
    else:
        render_placeholder(selected_menu)


if __name__ == "__main__":
    main()
