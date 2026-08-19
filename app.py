
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import streamlit as st

try:
    from supabase import create_client
except Exception:
    create_client = None

APP_NAME = "ChamaYetu"
OVERSIGHT_ROLES = ["Administrator", "Admin", "Chairperson", "Auditor", "Treasurer", "Secretary"]

st.set_page_config(page_title=APP_NAME, page_icon="💰", layout="wide")

# ---------- Styling ----------
st.markdown("""
<style>
.block-container {padding-top: 2rem;}
.metric-card {border:1px solid #e5e7eb; padding:1rem; border-radius:12px; background:#fff;}
.small-muted {color:#6b7280; font-size:0.9rem;}
.status-pill {padding:0.15rem 0.6rem; border-radius:999px; background:#eef2ff; color:#3730a3; font-size:0.8rem;}
.danger {background:#fff1f2; color:#be123c; padding:0.75rem; border-radius:8px;}
.success {background:#ecfdf5; color:#047857; padding:0.75rem; border-radius:8px;}
.warning {background:#fff7ed; color:#c2410c; padding:0.75rem; border-radius:8px;}
</style>
""", unsafe_allow_html=True)

# ---------- Supabase ----------
def get_secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.environ.get(name, default)

@st.cache_resource(show_spinner=False)
def get_supabase():
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_ANON_KEY")
    if not url or not key or create_client is None:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None

sb = get_supabase()

# ---------- Fallback demo data so the app always opens ----------
def demo_members():
    return pd.DataFrame([
        {"id": 1, "member_code": "M001", "full_name": "Peter Muia", "email": "peter.muia@example.com", "phone": "0700000001", "is_active": True, "default_role": "Member"},
        {"id": 2, "member_code": "M002", "full_name": "Member Two", "email": "member.two@example.com", "phone": "0700000002", "is_active": True, "default_role": "Member"},
        {"id": 3, "member_code": "M003", "full_name": "Member Three", "email": "member.three@example.com", "phone": "0700000003", "is_active": True, "default_role": "Member"},
        {"id": 4, "member_code": "M004", "full_name": "Member Four", "email": "member.four@example.com", "phone": "0700000004", "is_active": True, "default_role": "Member"},
        {"id": 5, "member_code": "M005", "full_name": "Member Five", "email": "member.five@example.com", "phone": "0700000005", "is_active": True, "default_role": "Member"},
    ])

def demo_member_roles():
    return pd.DataFrame([
        {"member_id":1,"role_name":"Member"},{"member_id":1,"role_name":"Administrator"},{"member_id":1,"role_name":"Chairperson"},
        {"member_id":2,"role_name":"Member"},{"member_id":2,"role_name":"Treasurer"},
        {"member_id":3,"role_name":"Member"},{"member_id":3,"role_name":"Secretary"},
        {"member_id":4,"role_name":"Member"},{"member_id":4,"role_name":"Checker"},
        {"member_id":5,"role_name":"Member"},{"member_id":5,"role_name":"Approver"},{"member_id":5,"role_name":"Accountant"},
    ])

def demo_contributions():
    rows=[]
    for m in range(1,6):
        for month in ["2026-06","2026-07","2026-08"]:
            paid = 10000 if not (m==3 and month=="2026-08") else 5000
            rows.append({"id":len(rows)+1,"group_id":1,"member_id":m,"contribution_month":month,"expected_amount":10000,"amount_paid":paid,
                         "payment_date":f"{month}-05","payment_method":"M-Pesa","receipt_ref":f"HIST-{m}-{month}","mpesa_reference":f"MPESA{m}{month.replace('-','')}",
                         "payment_status":"Paid" if paid>=10000 else "Partially Paid","verification_status":"Verified","source":"Demo"})
    return pd.DataFrame(rows)

def demo_units():
    c = demo_contributions()
    return pd.DataFrame({"group_id":c.group_id,"member_id":c.member_id,"amount":c.amount_paid,"units":c.amount_paid/100,"unit_price":100,"transaction_date":c.payment_date,"reference":c.receipt_ref})

def demo_loans():
    return pd.DataFrame([
        {"id":1,"group_id":1,"loan_ref":"LN-0001","borrower_id":1,"loan_amount":150000,"interest_rate":12,"repayment_months":12,"monthly_repayment":14000,"outstanding_total":98000,"status":"Active","submitted_at":"2026-08-01"},
        {"id":2,"group_id":1,"loan_ref":"LN-0002","borrower_id":2,"loan_amount":80000,"interest_rate":12,"repayment_months":10,"monthly_repayment":8500,"outstanding_total":0,"status":"Fully Repaid","submitted_at":"2026-05-02"},
        {"id":3,"group_id":1,"loan_ref":"LN-0003","borrower_id":3,"loan_amount":120000,"interest_rate":12,"repayment_months":12,"monthly_repayment":11200,"outstanding_total":134400,"status":"Submitted","submitted_at":"2026-08-18"},
    ])

def demo_guarantors():
    return pd.DataFrame([
        {"id":1,"loan_id":3,"guarantor_id":1,"guaranteed_amount":50000,"current_exposure":50000,"status":"Active"},
        {"id":2,"loan_id":3,"guarantor_id":2,"guaranteed_amount":30000,"current_exposure":30000,"status":"Active"},
    ])

def demo_schedule():
    rows=[]
    start=date(2026,9,5)
    for i in range(1,13):
        rows.append({"id":i,"loan_id":1,"borrower_id":1,"installment_no":i,"due_date":(start + pd.DateOffset(months=i-1)).date().isoformat(),
                     "principal_due":11000,"interest_due":3000,"total_due":14000,"amount_paid":14000 if i<5 else 0,"balance_due":0 if i<5 else 14000,
                     "status":"Paid" if i<5 else "Upcoming"})
    return pd.DataFrame(rows)

def fetch_table(table, fallback_df=None, select="*"):
    if sb is None:
        return fallback_df.copy() if fallback_df is not None else pd.DataFrame()
    try:
        res = sb.table(table).select(select).execute()
        return pd.DataFrame(res.data or [])
    except Exception as e:
        st.warning(f"Could not read `{table}` from Supabase. Using local demo data where available. Details: {e}")
        return fallback_df.copy() if fallback_df is not None else pd.DataFrame()

def insert_row(table, data):
    if sb is None:
        st.info("Demo mode: record was not saved to Supabase. Add SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit secrets to save data.")
        return False
    try:
        sb.table(table).insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Could not save to `{table}`: {e}")
        return False

def update_rows(table, data, col, value):
    if sb is None:
        st.info("Demo mode: update was not saved to Supabase.")
        return False
    try:
        sb.table(table).update(data).eq(col, value).execute()
        return True
    except Exception as e:
        st.error(f"Could not update `{table}`: {e}")
        return False

# ---------- Data models ----------
def load_data():
    members = fetch_table("members", demo_members())
    roles = fetch_roles(members)
    contributions = fetch_table("contributions", demo_contributions())
    schedules = fetch_table("contribution_schedules", pd.DataFrame())
    units = fetch_table("member_units", demo_units())
    loans = fetch_table("loan_applications", demo_loans())
    guarantors = fetch_table("loan_guarantors", demo_guarantors())
    repayment_schedule = fetch_table("loan_repayment_schedule", demo_schedule())
    mpesa_records = fetch_table("mpesa_payment_records", pd.DataFrame())
    return members, roles, contributions, schedules, units, loans, guarantors, repayment_schedule, mpesa_records

def fetch_roles(members):
    if sb is None:
        return demo_member_roles()
    try:
        mr = sb.table("member_roles").select("member_id, roles(role_name)").eq("status","Active").execute()
        rows=[]
        for r in mr.data or []:
            role_name = None
            if isinstance(r.get("roles"), dict):
                role_name = r["roles"].get("role_name")
            if role_name:
                rows.append({"member_id":r.get("member_id"),"role_name":role_name})
        df = pd.DataFrame(rows)
        return df if not df.empty else demo_member_roles()
    except Exception:
        if members.empty:
            return pd.DataFrame(columns=["member_id","role_name"])
        return demo_member_roles()

members, member_roles, contributions, contribution_schedules, member_units, loans, guarantors, repayment_schedule, mpesa_records = load_data()

# ---------- Helpers ----------
def money(x):
    try:
        return f"KES {float(x):,.2f}"
    except Exception:
        return "KES 0.00"

def member_name(member_id):
    row = members[members["id"] == member_id]
    if row.empty:
        return f"Member {member_id}"
    return f"{row.iloc[0].get('member_code','')} - {row.iloc[0].get('full_name','')}"

def balance_for(member_id):
    if not member_units.empty and "member_id" in member_units:
        return float(member_units[member_units.member_id == member_id].get("amount", pd.Series(dtype=float)).sum())
    if not contributions.empty and "member_id" in contributions:
        return float(contributions[contributions.member_id == member_id].get("amount_paid", pd.Series(dtype=float)).sum())
    return 0.0

def outstanding_own(member_id):
    if loans.empty: return 0.0
    active = loans[(loans.borrower_id == member_id) & (loans.status.isin(["Disbursed","Active","Defaulted","Recovered from Balance"]))]
    return float(active.get("outstanding_total", pd.Series(dtype=float)).fillna(0).sum())

def active_guarantees(member_id):
    if guarantors.empty: return 0.0
    g = guarantors[(guarantors.guarantor_id == member_id) & (guarantors.status == "Active")]
    col = "current_exposure" if "current_exposure" in g.columns else "guaranteed_amount"
    return float(g.get(col, pd.Series(dtype=float)).fillna(0).sum())

def entitlement(member_id, multiple=3):
    bal = balance_for(member_id)
    own = outstanding_own(member_id)
    guar = active_guarantees(member_id)
    gross = bal * multiple
    return {"balance": bal, "multiple": multiple, "gross": gross, "own": own, "guarantees": guar, "available": max(0, gross-own-guar)}

def available_roles_for(member_id):
    roles = member_roles[member_roles.member_id == member_id].role_name.dropna().tolist() if not member_roles.empty else ["Member"]
    if "Member" not in roles:
        roles = ["Member"] + roles
    return list(dict.fromkeys(roles))

# ---------- Login ----------
st.title(APP_NAME)
if members.empty:
    st.error("No members are visible to the app. Run database/migration_chamayetu_baseline.sql in Supabase, then refresh.")
    st.stop()

if "member_id" not in st.session_state:
    st.session_state.member_id = int(members.iloc[0].id)

login_options = {f"{r.get('member_code','')} - {r.get('full_name','')}": int(r.get('id')) for _, r in members.sort_values('member_code').iterrows()}
selected_label = st.sidebar.selectbox("Sign in as", list(login_options.keys()), index=list(login_options.values()).index(st.session_state.member_id) if st.session_state.member_id in list(login_options.values()) else 0)
st.session_state.member_id = login_options[selected_label]
current_member = members[members.id == st.session_state.member_id].iloc[0].to_dict()
roles = available_roles_for(st.session_state.member_id)
if "active_role" not in st.session_state or st.session_state.active_role not in roles:
    st.session_state.active_role = roles[0]
st.session_state.active_role = st.sidebar.selectbox("Active role", roles, index=roles.index(st.session_state.active_role))
st.sidebar.caption("Use M001/Peter as the initial administrator in demo mode.")

active_role = st.session_state.active_role
member_id = st.session_state.member_id
st.caption(f"Signed in as **{current_member.get('full_name')}** | Active role: **{active_role}**")

menu = ["Dashboard", "My Statement", "Contributions", "Loans", "Withdrawals", "Meetings", "Admin"]
if active_role == "Member":
    menu = ["Dashboard", "My Statement", "Contributions", "Loans", "Withdrawals", "Meetings"]
page = st.radio("", menu, horizontal=True)

# ---------- Pages ----------
def page_dashboard():
    st.header("Dashboard")
    e = entitlement(member_id)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Member balance", money(e["balance"]))
    c2.metric("Loan entitlement", money(e["available"]))
    c3.metric("Own outstanding loans", money(e["own"]))
    c4.metric("Guarantees exposure", money(e["guarantees"]))
    if active_role in OVERSIGHT_ROLES:
        st.subheader("Group summary")
        total_contrib = contributions.get("amount_paid", pd.Series(dtype=float)).fillna(0).sum() if not contributions.empty else 0
        loan_book = loans[loans.status.isin(["Active","Disbursed","Defaulted"])] if not loans.empty else pd.DataFrame()
        st.write({"total_members": len(members), "total_contributions": money(total_contrib), "active_loan_book": money(loan_book.get('outstanding_total', pd.Series(dtype=float)).sum() if not loan_book.empty else 0)})


def page_statement():
    st.header("My Statement")
    c = contributions[contributions.member_id == member_id].copy() if not contributions.empty else pd.DataFrame()
    if c.empty:
        st.info("No contribution records found for this member.")
    else:
        st.dataframe(c[[col for col in ["contribution_month","expected_amount","amount_paid","payment_status","verification_status","receipt_ref","mpesa_reference"] if col in c.columns]], use_container_width=True)


def page_contributions():
    st.header("Contributions")
    if active_role == "Member":
        st.subheader("My contributions")
        c = contributions[contributions.member_id == member_id].copy() if not contributions.empty else pd.DataFrame()
        st.dataframe(c, use_container_width=True)
        with st.expander("Submit M-Pesa contribution reference"):
            with st.form("contribution_ref"):
                month = st.text_input("Contribution month", value=date.today().strftime("%Y-%m"))
                amount = st.number_input("Amount paid", min_value=0.0, value=10000.0, step=500.0)
                ref = st.text_input("M-Pesa reference")
                phone = st.text_input("Phone used")
                submitted = st.form_submit_button("Submit reference")
            if submitted and ref:
                data = {"group_id":1,"member_id":member_id,"contribution_month":month,"expected_amount":amount,"amount_paid":amount,"payment_method":"M-Pesa","mpesa_reference":ref,"receipt_ref":ref,"payment_status":"Pending","verification_status":"Pending Verification","source":"Member"}
                if insert_row("contributions", data):
                    st.success("Contribution reference submitted.")
    else:
        st.subheader("All contributions")
        st.dataframe(contributions, use_container_width=True)
        with st.expander("Add or upload verified contribution manually"):
            with st.form("manual_contribution"):
                borrower = st.selectbox("Member", members.apply(lambda r: f"{r.member_code} - {r.full_name}", axis=1).tolist())
                mid = int(members.iloc[members.apply(lambda r: f"{r.member_code} - {r.full_name}", axis=1).tolist().index(borrower)].id)
                month = st.text_input("Month", value=date.today().strftime("%Y-%m"))
                expected = st.number_input("Expected amount", min_value=0.0, value=10000.0, step=500.0)
                paid = st.number_input("Actual amount", min_value=0.0, value=10000.0, step=500.0)
                ref = st.text_input("Receipt / M-Pesa reference")
                ok = st.form_submit_button("Save contribution")
            if ok:
                status = "Paid" if paid >= expected else "Partially Paid"
                data = {"group_id":1,"member_id":mid,"contribution_month":month,"expected_amount":expected,"amount_paid":paid,"payment_method":"M-Pesa","receipt_ref":ref,"mpesa_reference":ref,"payment_status":status,"verification_status":"Verified","source":"Manual"}
                if insert_row("contributions", data): st.success("Contribution saved.")


def page_loans():
    st.header("Loans")
    if active_role == "Member":
        e = entitlement(member_id)
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Member balance", money(e["balance"]))
        c2.metric("Loan multiple", f"{e['multiple']}x")
        c3.metric("Gross entitlement", money(e["gross"]))
        c4.metric("Less loans/guarantees", money(e["own"] + e["guarantees"]))
        c5.metric("Available entitlement", money(e["available"]))
        tabs = st.tabs(["Current loans", "Historical loans", "Guaranteed loans", "Apply for loan", "Repay by M-Pesa"])
        with tabs[0]:
            df = loans[(loans.borrower_id == member_id) & (loans.status.isin(["Submitted","Checked","Approved","Disbursed","Active","Defaulted"]))] if not loans.empty else pd.DataFrame()
            st.dataframe(df, use_container_width=True)
        with tabs[1]:
            df = loans[(loans.borrower_id == member_id) & (loans.status.isin(["Fully Repaid","Cancelled","Rejected"]))] if not loans.empty else pd.DataFrame()
            st.dataframe(df, use_container_width=True)
        with tabs[2]:
            if guarantors.empty:
                st.info("No guaranteed loans found.")
            else:
                g = guarantors[guarantors.guarantor_id == member_id].merge(loans, left_on="loan_id", right_on="id", suffixes=("_guarantee","_loan"), how="left")
                st.dataframe(g, use_container_width=True)
        with tabs[3]:
            with st.form("loan_application"):
                amount = st.number_input("Loan amount", min_value=0.0, max_value=float(e["available"]), value=min(50000.0, float(e["available"])), step=5000.0)
                months = st.number_input("Repayment months", min_value=1, max_value=36, value=12, step=1)
                purpose = st.text_area("Purpose")
                bank = st.text_input("Preferred bank")
                acc = st.text_input("Account number")
                submit = st.form_submit_button("Submit loan application")
            if submit:
                loan_ref = "LN-" + datetime.now().strftime("%Y%m%d%H%M%S")
                data = {"group_id":1,"loan_ref":loan_ref,"borrower_id":member_id,"loan_amount":amount,"interest_rate":12,"repayment_months":int(months),"loan_purpose":purpose,"preferred_bank_name":bank,"preferred_account_number":acc,"status":"Submitted","available_entitlement_at_application":e['available']}
                if insert_row("loan_applications", data): st.success(f"Loan application {loan_ref} submitted.")
        with tabs[4]:
            member_loans = loans[(loans.borrower_id == member_id) & (loans.status.isin(["Active","Disbursed","Defaulted"]))] if not loans.empty else pd.DataFrame()
            if member_loans.empty:
                st.info("No active loan for repayment.")
            else:
                with st.form("loan_mpesa"):
                    loan_label = st.selectbox("Loan", member_loans.apply(lambda r: f"{r.loan_ref} - {money(r.outstanding_total)}", axis=1).tolist())
                    loan = member_loans.iloc[member_loans.apply(lambda r: f"{r.loan_ref} - {money(r.outstanding_total)}", axis=1).tolist().index(loan_label)]
                    amount = st.number_input("Amount paid", min_value=0.0, value=float(loan.get("monthly_repayment",0) or 0), step=500.0)
                    ref = st.text_input("M-Pesa reference")
                    phone = st.text_input("Phone used")
                    ok = st.form_submit_button("Submit M-Pesa reference")
                if ok and ref:
                    data={"group_id":1,"member_id":member_id,"loan_id":int(loan.id),"payment_purpose":"Loan Repayment","expected_amount":amount,"paid_amount":amount,"mpesa_reference":ref,"payer_phone":phone,"verification_status":"Pending Verification"}
                    if insert_row("mpesa_payment_records", data): st.success("M-Pesa reference submitted for verification.")
    elif active_role in ["Checker", "Approver"]:
        st.subheader("Loans waiting to be checked or approved")
        df = loans[loans.status.isin(["Submitted","Checked"])] if not loans.empty else pd.DataFrame()
        st.dataframe(df, use_container_width=True)
        if not df.empty:
            selected = st.selectbox("Select loan", df.apply(lambda r: f"{r.id} - {r.loan_ref} - {member_name(r.borrower_id)}", axis=1).tolist())
            loan_id = int(selected.split(" - ")[0])
            lrow = df[df.id == loan_id].iloc[0]
            if lrow.status == "Submitted" and active_role == "Checker":
                if st.button("Check loan"):
                    update_rows("loan_applications", {"status":"Checked","checked_by_member_id":member_id,"checked_at":datetime.now().isoformat()}, "id", loan_id)
                    st.success("Loan checked.")
            elif lrow.status == "Checked" and active_role == "Approver":
                if int(lrow.get("checked_by_member_id") or 0) == member_id:
                    st.error("You cannot approve this loan because you already checked it.")
                elif st.button("Approve loan"):
                    update_rows("loan_applications", {"status":"Approved","approved_by_member_id":member_id,"approved_at":datetime.now().isoformat()}, "id", loan_id)
                    st.success("Loan approved.")
    elif active_role == "Accountant":
        st.subheader("Approved loans awaiting liquidation/disbursement")
        df = loans[loans.status.isin(["Approved","Linked to Asset","Liquidation Initiated","Liquidation Completed","Bank Transfer Initiated","Bank Transfer Document Uploaded"])] if not loans.empty else pd.DataFrame()
        st.dataframe(df, use_container_width=True)
        st.info("Use the database migration functions for detailed liquidation and disbursement. This screen keeps the workflow visible and safe.")
    elif active_role in OVERSIGHT_ROLES:
        tabs = st.tabs(["All loans", "Repayment schedule", "Loan balances", "Current loan book", "M-Pesa verification"])
        with tabs[0]: st.dataframe(loans, use_container_width=True)
        with tabs[1]: st.dataframe(repayment_schedule, use_container_width=True)
        with tabs[2]:
            if loans.empty: st.info("No loans found.")
            else:
                summary = loans.groupby("borrower_id", as_index=False).agg(total_loan_amount=("loan_amount","sum"), outstanding_total=("outstanding_total","sum"))
                summary["member"] = summary.borrower_id.apply(member_name)
                st.dataframe(summary[["member","total_loan_amount","outstanding_total"]], use_container_width=True)
        with tabs[3]:
            active = loans[loans.status.isin(["Active","Disbursed","Defaulted"])] if not loans.empty else pd.DataFrame()
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Active loans", len(active))
            c2.metric("Current loan book", money(active.get("outstanding_total", pd.Series(dtype=float)).sum() if not active.empty else 0))
            c3.metric("Pending approval", len(loans[loans.status.isin(["Submitted","Checked"])]) if not loans.empty else 0)
            c4.metric("Fully repaid", len(loans[loans.status=="Fully Repaid"]) if not loans.empty else 0)
        with tabs[4]:
            st.dataframe(mpesa_records, use_container_width=True)


def page_admin():
    st.header("Admin")
    if active_role not in OVERSIGHT_ROLES:
        st.error("Admin page is restricted.")
        return
    st.subheader("Members")
    st.dataframe(members, use_container_width=True)
    with st.expander("Add member"):
        with st.form("add_member"):
            code = st.text_input("Member code")
            name = st.text_input("Full name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            ok = st.form_submit_button("Add member")
        if ok:
            if insert_row("members", {"member_code":code,"full_name":name,"email":email,"phone":phone,"is_active":True,"default_role":"Member"}): st.success("Member added.")

if page == "Dashboard": page_dashboard()
elif page == "My Statement": page_statement()
elif page == "Contributions": page_contributions()
elif page == "Loans": page_loans()
elif page == "Withdrawals": st.info("Withdrawals module placeholder. Add withdrawal table when ready.")
elif page == "Meetings": st.info("Meetings module placeholder. The v2 SQL already includes meetings, attendance and AGM tables.")
elif page == "Admin": page_admin()

st.divider()
st.caption("ChamaYetu working recovery build. If Supabase secrets are missing or tables are blocked by RLS, the app opens in demo mode rather than failing.")
