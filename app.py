import streamlit as st
import pandas as pd
from datetime import date, datetime
from sqlalchemy import create_engine, text

APP_TITLE = "Committee Investment Vehicle"
APP_SUBTITLE = "Contributions, investment returns, lending, withdrawals and member fund value analytics"
DEFAULT_DB = "sqlite:///committee_investment_vehicle.db"

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
[data-testid="stSidebar"] {display: none;}
.block-container {padding-top: 1.1rem; max-width: 1280px;}
.civ-hero {background: linear-gradient(120deg,#0B1F3A 0%,#1F4E79 62%,#0E7C7B 100%); color:white; border-radius:22px; padding:1.35rem 1.55rem; box-shadow:0 12px 28px rgba(11,31,58,.16); margin-bottom:1rem;}
.civ-hero h1 {font-size:2.05rem; margin:0; letter-spacing:-0.02em;}
.civ-hero p {margin:.35rem 0 0; color:#E5EEF7;}
div[data-testid="stMetric"] {background:#fff; border:1px solid #E5E7EB; border-radius:16px; padding:1rem; box-shadow:0 6px 18px rgba(15,23,42,.06);}
div[data-testid="stMetric"] label {color:#6B7280 !important;}
.stRadio > div {display:flex; gap:.3rem; flex-wrap:wrap; background:#EEF2F7; padding:.35rem; border-radius:16px;}
.stRadio [role="radiogroup"] label {background:#fff; border:1px solid #D7DEE8; border-radius:999px; padding:.45rem .85rem; margin:.15rem;}
.stRadio [role="radiogroup"] label:hover {border-color:#1F4E79;}
hr {margin:1rem 0;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_engine():
    db_url = st.secrets.get("DATABASE_URL", DEFAULT_DB) if hasattr(st, "secrets") else DEFAULT_DB
    return create_engine(db_url, future=True)

engine = get_engine()

def run(sql, params=None):
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})

def df(sql, params=None):
    with engine.begin() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})

def scalar(sql, params=None, default=0):
    data = df(sql, params)
    if data.empty:
        return default
    value = data.iloc[0, 0]
    return default if pd.isna(value) else value

def init_db():
    statements = [
        """CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, name TEXT NOT NULL, base_currency TEXT DEFAULT 'KES', opening_unit_price REAL DEFAULT 100, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS members (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, member_code TEXT, full_name TEXT NOT NULL, phone TEXT, email TEXT, status TEXT DEFAULT 'Active', join_date TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS payment_uploads (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, member_id INTEGER, amount REAL, contribution_month TEXT, payment_method TEXT, destination TEXT, transaction_ref TEXT UNIQUE, uploaded_by TEXT, status TEXT DEFAULT 'Submitted', verified_by TEXT, approved_by TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS contributions (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, member_id INTEGER, contribution_month TEXT, expected_amount REAL DEFAULT 0, amount_paid REAL, arrears REAL DEFAULT 0, receipt_ref TEXT UNIQUE, approved_by TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS member_units (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, member_id INTEGER, transaction_date TEXT, transaction_type TEXT, amount REAL, unit_price REAL, units REAL, reference TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS investments (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, asset_class TEXT, institution TEXT, description TEXT, cost REAL, current_value REAL, status TEXT DEFAULT 'Active', created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS investment_returns (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, period TEXT, return_type TEXT, asset_class TEXT, amount REAL, status TEXT DEFAULT 'Approved', created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS loans (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, member_id INTEGER, principal REAL, annual_rate REAL, months INTEGER, outstanding_principal REAL, monthly_payment REAL, status TEXT DEFAULT 'Submitted', created_by TEXT, approved_by TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, member_id INTEGER, amount REAL, withdrawal_type TEXT, status TEXT DEFAULT 'Submitted', created_by TEXT, approved_by TEXT, created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS fund_valuations (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, valuation_date TEXT, bank_balance REAL DEFAULT 0, mmf_balance REAL DEFAULT 0, investment_value REAL DEFAULT 0, loans_receivable REAL DEFAULT 0, liabilities REAL DEFAULT 0, nav REAL, total_units REAL, unit_price REAL, status TEXT DEFAULT 'Approved', created_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, group_id INTEGER DEFAULT 1, action TEXT, details TEXT, user_name TEXT, created_at TEXT)""",
    ]
    for statement in statements:
        run(statement)
    if scalar("SELECT COUNT(*) FROM groups") == 0:
        run("INSERT INTO groups (id, name, base_currency, opening_unit_price, created_at) VALUES (1, 'Committee Investment Vehicle', 'KES', 100, :now)", {"now": datetime.now().isoformat()})

def log(action, details, user):
    run("INSERT INTO audit_logs (action, details, user_name, created_at) VALUES (:a, :d, :u, :n)", {"a": action, "d": details, "u": user, "n": datetime.now().isoformat()})

def current_unit_price():
    return float(scalar("SELECT unit_price FROM fund_valuations WHERE status='Approved' ORDER BY valuation_date DESC, id DESC LIMIT 1", default=100))

def total_units():
    return float(scalar("SELECT COALESCE(SUM(units),0) FROM member_units", default=0))

def member_value(member_id):
    units = float(scalar("SELECT COALESCE(SUM(units),0) FROM member_units WHERE member_id=:m", {"m": member_id}, 0))
    return units * current_unit_price()

def member_options():
    members = df("SELECT id, full_name FROM members WHERE status='Active' ORDER BY full_name")
    return {f"{r.full_name} (ID {r.id})": int(r.id) for _, r in members.iterrows()}

def add_units(member_id, amount, reference, user, transaction_type="Contribution"):
    price = current_unit_price()
    units = 0 if price <= 0 else amount / price
    run("INSERT INTO member_units (member_id, transaction_date, transaction_type, amount, unit_price, units, reference, created_at) VALUES (:m,:d,:t,:a,:p,:u,:r,:n)", {"m": member_id, "d": str(date.today()), "t": transaction_type, "a": amount, "p": price, "u": units, "r": reference, "n": datetime.now().isoformat()})
    log("Units allocated", f"{transaction_type}: member={member_id}, amount={amount}, units={units:.4f}, ref={reference}", user)

def redeem_units(member_id, amount, reference, user):
    price = current_unit_price()
    units = 0 if price <= 0 else -(amount / price)
    run("INSERT INTO member_units (member_id, transaction_date, transaction_type, amount, unit_price, units, reference, created_at) VALUES (:m,:d,'Withdrawal',:a,:p,:u,:r,:n)", {"m": member_id, "d": str(date.today()), "a": -amount, "p": price, "u": units, "r": reference, "n": datetime.now().isoformat()})
    log("Units redeemed", f"Withdrawal: member={member_id}, amount={amount}, units={units:.4f}, ref={reference}", user)

init_db()

st.markdown(f"""<div class="civ-hero"><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p></div>""", unsafe_allow_html=True)

user_col, role_col = st.columns([2, 1])
with user_col:
    user = st.text_input("Current user name", value="Peter", label_visibility="collapsed", placeholder="Current user name")
with role_col:
    role = st.selectbox("Role", ["Member", "Secretary", "Treasurer", "Checker", "Chairperson", "Admin"], label_visibility="collapsed")

menu = st.radio("Main menu", ["Dashboard", "Onboarding", "Members", "Payments & Receipts", "Investments & Valuation", "Loans", "Withdrawals", "Reports", "Admin"], horizontal=True, label_visibility="collapsed")
st.caption("Pilot mode: role selection is for testing. Add Supabase Auth and Row Level Security before live use.")

if menu == "Dashboard":
    latest_nav = float(scalar("SELECT nav FROM fund_valuations WHERE status='Approved' ORDER BY valuation_date DESC, id DESC LIMIT 1", default=0))
    latest_price = current_unit_price()
    total_contributions = float(scalar("SELECT COALESCE(SUM(amount_paid),0) FROM contributions", default=0))
    total_returns = float(scalar("SELECT COALESCE(SUM(amount),0) FROM investment_returns", default=0))
    roi = 0 if total_contributions == 0 else (total_returns / total_contributions) * 100
    arrears = float(scalar("SELECT COALESCE(SUM(arrears),0) FROM contributions", default=0))

    st.subheader("Executive Dashboard")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Fund Value / NAV", f"KES {latest_nav:,.2f}")
    c2.metric("Total Contributions", f"KES {total_contributions:,.2f}")
    c3.metric("Total Returns", f"KES {total_returns:,.2f}")
    c4.metric("ROI on Contributions", f"{roi:,.2f}%")
    c5.metric("Total Arrears", f"KES {arrears:,.2f}")

    st.markdown("---")
    contributions = df("SELECT contribution_month, COALESCE(SUM(amount_paid),0) AS contributions FROM contributions GROUP BY contribution_month ORDER BY contribution_month")
    returns = df("SELECT period, COALESCE(SUM(amount),0) AS returns FROM investment_returns GROUP BY period ORDER BY period")
    left_chart, right_chart = st.columns(2)
    with left_chart:
        st.markdown("#### Contribution Growth")
        if not contributions.empty:
            contributions["cumulative_contributions"] = contributions["contributions"].cumsum()
            st.line_chart(contributions.set_index("contribution_month")[["contributions", "cumulative_contributions"]])
        else:
            st.info("No contribution data yet. Use Onboarding or Payments & Receipts to post approved contributions.")
    with right_chart:
        st.markdown("#### Return Growth")
        if not returns.empty:
            returns["cumulative_returns"] = returns["returns"].cumsum()
            st.line_chart(returns.set_index("period")[["returns", "cumulative_returns"]])
        else:
            st.info("No return data yet. Use Investments & Valuation to record approved returns.")

    st.markdown("---")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Member Value Distribution")
        members = df("SELECT m.id, m.full_name, COALESCE(SUM(u.units),0) AS units FROM members m LEFT JOIN member_units u ON m.id=u.member_id GROUP BY m.id,m.full_name ORDER BY m.full_name")
        if not members.empty:
            members["unit_price"] = latest_price
            members["member_value"] = members["units"] * members["unit_price"]
            display = members[["full_name", "units", "unit_price", "member_value"]].copy()
            st.dataframe(display, use_container_width=True, hide_index=True)
            if display["member_value"].sum() > 0:
                st.bar_chart(display.set_index("full_name")[["member_value"]])
        else:
            st.info("Add members and onboarding balances to see member values.")
    with right:
        st.markdown("#### Portfolio Summary")
        investments = df("SELECT asset_class, SUM(current_value) AS value FROM investments GROUP BY asset_class")
        if not investments.empty:
            st.bar_chart(investments.set_index("asset_class"))
            st.dataframe(investments, use_container_width=True, hide_index=True)
        else:
            st.info("No investments recorded yet.")

elif menu == "Onboarding":
    st.header("Onboarding & Historical Migration")
    tab1, tab2, tab3 = st.tabs(["Upload Members", "Upload Contributions", "Allocate Historical Returns"])
    with tab1:
        file = st.file_uploader("Upload members Excel/CSV with columns: member_code, full_name, phone, email", type=["xlsx", "csv"], key="members_upload")
        if file:
            data = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
            st.dataframe(data, use_container_width=True)
            if st.button("Import members"):
                for _, row in data.iterrows():
                    run("INSERT INTO members (member_code, full_name, phone, email, join_date, created_at) VALUES (:c,:n,:p,:e,:j,:now)", {"c": row.get("member_code", ""), "n": row.get("full_name", ""), "p": row.get("phone", ""), "e": row.get("email", ""), "j": str(date.today()), "now": datetime.now().isoformat()})
                log("Onboarding members import", f"Rows imported: {len(data)}", user)
                st.success("Members imported.")
                st.rerun()
    with tab2:
        file = st.file_uploader("Upload contributions Excel/CSV with columns: member_code, contribution_month, expected_amount, amount_paid, receipt_ref", type=["xlsx", "csv"], key="contrib_upload")
        if file:
            data = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
            st.dataframe(data, use_container_width=True)
            if st.button("Import approved historical contributions and create opening units"):
                imported = 0
                for _, row in data.iterrows():
                    member_lookup = df("SELECT id FROM members WHERE member_code=:code", {"code": str(row.get("member_code", ""))})
                    if member_lookup.empty:
                        continue
                    member_id = int(member_lookup.iloc[0, 0])
                    expected = float(row.get("expected_amount", 0) or 0)
                    paid = float(row.get("amount_paid", 0) or 0)
                    arrears_amount = max(expected - paid, 0)
                    receipt_ref = str(row.get("receipt_ref", f"OPEN-{member_id}-{imported}"))
                    run("INSERT INTO contributions (member_id, contribution_month, expected_amount, amount_paid, arrears, receipt_ref, approved_by, created_at) VALUES (:m,:mo,:e,:a,:ar,:r,:u,:n)", {"m": member_id, "mo": str(row.get("contribution_month", "Opening")), "e": expected, "a": paid, "ar": arrears_amount, "r": receipt_ref, "u": user, "n": datetime.now().isoformat()})
                    add_units(member_id, paid, receipt_ref, user, "Opening Contribution")
                    imported += 1
                st.success(f"Imported {imported} contribution records and created units.")
                st.rerun()
    with tab3:
        total_return = st.number_input("Historical unallocated return amount", min_value=0.0, step=1000.0)
        basis = df("SELECT m.id, m.full_name, COALESCE(SUM(c.amount_paid),0) AS eligible_balance FROM members m LEFT JOIN contributions c ON m.id=c.member_id GROUP BY m.id,m.full_name ORDER BY m.full_name")
        if not basis.empty:
            total_basis = basis["eligible_balance"].sum()
            basis["weight"] = basis["eligible_balance"].apply(lambda x: 0 if total_basis == 0 else x / total_basis)
            basis["allocated_return"] = basis["weight"] * total_return
            st.dataframe(basis, use_container_width=True, hide_index=True)
            if st.button("Approve and allocate historical returns as opening units"):
                for _, row in basis.iterrows():
                    if row["allocated_return"] > 0:
                        add_units(int(row["id"]), float(row["allocated_return"]), f"HIST-RETURN-{date.today()}", user, "Historical Return Allocation")
                log("Historical returns allocated", f"Amount={total_return}", user)
                st.success("Historical returns allocated as opening units.")
                st.rerun()

elif menu == "Members":
    st.header("Members")
    with st.form("add_member"):
        col1, col2 = st.columns(2)
        member_code = col1.text_input("Member code")
        full_name = col2.text_input("Full name")
        phone = col1.text_input("Phone")
        email = col2.text_input("Email")
        if st.form_submit_button("Add member") and full_name:
            run("INSERT INTO members (member_code, full_name, phone, email, join_date, created_at) VALUES (:c,:n,:p,:e,:j,:now)", {"c": member_code, "n": full_name, "p": phone, "e": email, "j": str(date.today()), "now": datetime.now().isoformat()})
            log("Member added", full_name, user)
            st.success("Member added.")
            st.rerun()
    st.dataframe(df("SELECT * FROM members ORDER BY full_name"), use_container_width=True, hide_index=True)

elif menu == "Payments & Receipts":
    st.header("Payments & Receipts")
    members_dict = member_options()
    tab1, tab2 = st.tabs(["Member Payment Upload", "Secretary/Checker Receipt Queue"])
    with tab1:
        with st.form("payment_upload"):
            member_label = st.selectbox("Member", list(members_dict.keys())) if members_dict else None
            amount = st.number_input("Amount paid", min_value=0.0, step=500.0)
            month = st.text_input("Contribution month", value=date.today().strftime("%Y-%m"))
            method = st.selectbox("Payment method", ["M-Pesa", "Bank Transfer", "MMF Direct", "Cash Deposit"])
            destination = st.selectbox("Destination", ["MMF Account", "Bank Account"])
            transaction_ref = st.text_input("Transaction reference")
            if st.form_submit_button("Submit payment proof") and member_label and amount > 0 and transaction_ref:
                try:
                    run("INSERT INTO payment_uploads (member_id, amount, contribution_month, payment_method, destination, transaction_ref, uploaded_by, created_at) VALUES (:m,:a,:mo,:pm,:d,:r,:u,:n)", {"m": members_dict[member_label], "a": amount, "mo": month, "pm": method, "d": destination, "r": transaction_ref, "u": user, "n": datetime.now().isoformat()})
                    log("Payment proof uploaded", transaction_ref, user)
                    st.success("Payment submitted for verification.")
                    st.rerun()
                except Exception as err:
                    st.error(f"Could not save. Check duplicate reference. {err}")
    with tab2:
        queue = df("SELECT p.id, m.full_name, p.amount, p.contribution_month, p.payment_method, p.destination, p.transaction_ref, p.uploaded_by, p.status FROM payment_uploads p JOIN members m ON p.member_id=m.id WHERE p.status IN ('Submitted','Verified') ORDER BY p.id DESC")
        st.dataframe(queue, use_container_width=True, hide_index=True)
        if not queue.empty:
            payment_id = st.number_input("Payment ID to process", min_value=1, step=1)
            action = st.selectbox("Action", ["Verify", "Approve and Post Receipt", "Reject"])
            if st.button("Process"):
                payment = df("SELECT * FROM payment_uploads WHERE id=:id", {"id": payment_id})
                if payment.empty:
                    st.error("Payment not found.")
                else:
                    record = payment.iloc[0]
                    if action == "Verify":
                        if role not in ["Secretary", "Treasurer", "Admin"]:
                            st.error("Only secretary, treasurer or admin can verify.")
                        else:
                            run("UPDATE payment_uploads SET status='Verified', verified_by=:u WHERE id=:id", {"u": user, "id": payment_id})
                            log("Payment verified", str(payment_id), user)
                            st.success("Payment verified.")
                            st.rerun()
                    elif action == "Approve and Post Receipt":
                        if role not in ["Checker", "Chairperson", "Admin"]:
                            st.error("Only checker, chairperson or admin can approve.")
                        elif record["uploaded_by"] == user or record.get("verified_by", "") == user:
                            st.error("Maker or verifier cannot approve own transaction.")
                        elif record["status"] != "Verified":
                            st.error("Payment must first be verified.")
                        else:
                            run("INSERT INTO contributions (member_id, contribution_month, expected_amount, amount_paid, arrears, receipt_ref, approved_by, created_at) VALUES (:m,:mo,:e,:a,0,:r,:u,:n)", {"m": int(record["member_id"]), "mo": record["contribution_month"], "e": float(record["amount"]), "a": float(record["amount"]), "r": record["transaction_ref"], "u": user, "n": datetime.now().isoformat()})
                            add_units(int(record["member_id"]), float(record["amount"]), record["transaction_ref"], user)
                            run("UPDATE payment_uploads SET status='Approved', approved_by=:u WHERE id=:id", {"u": user, "id": payment_id})
                            st.success("Receipt approved, contribution posted and units allocated.")
                            st.rerun()
                    else:
                        run("UPDATE payment_uploads SET status='Rejected', approved_by=:u WHERE id=:id", {"u": user, "id": payment_id})
                        log("Payment rejected", str(payment_id), user)
                        st.warning("Payment rejected.")
                        st.rerun()

elif menu == "Investments & Valuation":
    st.header("Investments & Valuation")
    tab1, tab2, tab3 = st.tabs(["Investment Register", "Record Return", "Approve Valuation"])
    with tab1:
        with st.form("investment"):
            asset_class = st.selectbox("Asset class", ["Bank", "MMF", "Treasury Bond", "Corporate Bond", "Equity", "REIT", "Private Equity", "Venture Capital", "Special Fund", "Other"])
            institution = st.text_input("Institution/Fund/Issuer")
            description = st.text_input("Description")
            cost = st.number_input("Cost", min_value=0.0, step=1000.0)
            current_value = st.number_input("Current value", min_value=0.0, step=1000.0)
            if st.form_submit_button("Save investment"):
                run("INSERT INTO investments (asset_class, institution, description, cost, current_value, created_at) VALUES (:a,:i,:d,:c,:v,:n)", {"a": asset_class, "i": institution, "d": description, "c": cost, "v": current_value, "n": datetime.now().isoformat()})
                log("Investment saved", f"{asset_class} {current_value}", user)
                st.success("Investment saved.")
                st.rerun()
        st.dataframe(df("SELECT * FROM investments ORDER BY id DESC"), use_container_width=True, hide_index=True)
    with tab2:
        with st.form("return"):
            period = st.text_input("Period", value=date.today().strftime("%Y-%m"))
            return_type = st.selectbox("Return type", ["MMF Interest", "Bond Coupon", "Dividend", "Fair Value Gain", "Fair Value Loss", "Loan Interest", "Other"])
            asset_class = st.text_input("Asset class")
            amount = st.number_input("Amount", value=0.0, step=1000.0)
            if st.form_submit_button("Record approved return"):
                run("INSERT INTO investment_returns (period, return_type, asset_class, amount, created_at) VALUES (:p,:t,:a,:m,:n)", {"p": period, "t": return_type, "a": asset_class, "m": amount, "n": datetime.now().isoformat()})
                log("Investment return recorded", f"{return_type} {amount}", user)
                st.success("Return recorded.")
                st.rerun()
        st.dataframe(df("SELECT * FROM investment_returns ORDER BY id DESC"), use_container_width=True, hide_index=True)
    with tab3:
        investment_value = float(scalar("SELECT COALESCE(SUM(current_value),0) FROM investments", default=0))
        loans_receivable = float(scalar("SELECT COALESCE(SUM(outstanding_principal),0) FROM loans WHERE status IN ('Approved','Disbursed','Active')", default=0))
        bank_balance = st.number_input("Bank balance", min_value=0.0, step=1000.0)
        mmf_balance = st.number_input("MMF balance", min_value=0.0, step=1000.0)
        liabilities = st.number_input("Liabilities/payables", min_value=0.0, step=1000.0)
        nav = bank_balance + mmf_balance + investment_value + loans_receivable - liabilities
        units = total_units()
        unit_price = 100 if units == 0 else nav / units
        col1, col2 = st.columns(2)
        col1.metric("Calculated NAV", f"KES {nav:,.2f}")
        col2.metric("Calculated Unit Price", f"KES {unit_price:,.4f}")
        if st.button("Approve official valuation / period close"):
            run("INSERT INTO fund_valuations (valuation_date, bank_balance, mmf_balance, investment_value, loans_receivable, liabilities, nav, total_units, unit_price, status, created_at) VALUES (:d,:b,:m,:i,:l,:li,:nav,:tu,:up,'Approved',:n)", {"d": str(date.today()), "b": bank_balance, "m": mmf_balance, "i": investment_value, "l": loans_receivable, "li": liabilities, "nav": nav, "tu": units, "up": unit_price, "n": datetime.now().isoformat()})
            log("Fund valuation approved", f"NAV={nav}, unit_price={unit_price}", user)
            st.success("Valuation approved and unit price updated.")
            st.rerun()

elif menu == "Loans":
    st.header("Loans")
    members_dict = member_options()
    annual_rate = st.number_input("Default annual interest rate (%)", min_value=0.0, value=12.0, step=0.5) / 100
    loan_multiple = st.number_input("Loan multiple on available member balance", min_value=1.0, value=3.0, step=0.5)
    tab1, tab2 = st.tabs(["Apply/Approve Loan", "Repayment Schedule Preview"])
    with tab1:
        if members_dict:
            borrower_label = st.selectbox("Borrower", list(members_dict.keys()))
            borrower_id = members_dict[borrower_label]
            available_value = member_value(borrower_id)
            maximum_loan = available_value * loan_multiple
            st.info(f"Estimated member value: KES {available_value:,.2f}. Maximum loan at {loan_multiple}x: KES {maximum_loan:,.2f}")
            loan_amount = st.number_input("Loan amount", min_value=0.0, step=1000.0)
            months = st.number_input("Repayment months", min_value=1, value=12, step=1)
            if st.button("Submit loan request"):
                if loan_amount > maximum_loan:
                    st.error("Loan exceeds allowed multiple. Add guarantors or reduce amount.")
                else:
                    monthly_rate = annual_rate / 12
                    monthly_payment = loan_amount / months if monthly_rate == 0 else loan_amount * monthly_rate / (1 - (1 + monthly_rate) ** (-months))
                    run("INSERT INTO loans (member_id, principal, annual_rate, months, outstanding_principal, monthly_payment, status, created_by, created_at) VALUES (:m,:p,:r,:mo,:o,:pm,'Submitted',:u,:n)", {"m": borrower_id, "p": loan_amount, "r": annual_rate, "mo": months, "o": loan_amount, "pm": monthly_payment, "u": user, "n": datetime.now().isoformat()})
                    log("Loan submitted", f"member={borrower_id}, amount={loan_amount}", user)
                    st.success("Loan submitted.")
                    st.rerun()
        loans = df("SELECT l.*, m.full_name FROM loans l JOIN members m ON l.member_id=m.id ORDER BY l.id DESC")
        st.dataframe(loans, use_container_width=True, hide_index=True)
        loan_id = st.number_input("Loan ID to approve", min_value=1, step=1)
        if st.button("Approve selected loan"):
            selected = df("SELECT * FROM loans WHERE id=:id", {"id": loan_id})
            if selected.empty:
                st.error("Loan not found.")
            elif selected.iloc[0]["created_by"] == user:
                st.error("Maker cannot approve own loan.")
            elif role not in ["Checker", "Chairperson", "Admin"]:
                st.error("Only checker, chairperson or admin can approve loans.")
            else:
                run("UPDATE loans SET status='Approved', approved_by=:u WHERE id=:id", {"u": user, "id": loan_id})
                log("Loan approved", str(loan_id), user)
                st.success("Loan approved.")
                st.rerun()
    with tab2:
        principal = st.number_input("Principal for preview", min_value=0.0, value=100000.0, step=1000.0)
        months = st.number_input("Months for preview", min_value=1, value=12, step=1, key="preview_months")
        monthly_rate = annual_rate / 12
        monthly_payment = principal / months if monthly_rate == 0 else principal * monthly_rate / (1 - (1 + monthly_rate) ** (-months))
        balance = principal
        rows = []
        for period in range(1, int(months) + 1):
            opening = balance
            interest = balance * monthly_rate
            principal_part = max(monthly_payment - interest, 0)
            balance = max(balance - principal_part, 0)
            rows.append({"Month": period, "Opening Balance": opening, "Interest": interest, "Principal": principal_part, "Payment": monthly_payment, "Closing Balance": balance})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif menu == "Withdrawals":
    st.header("Withdrawals")
    members_dict = member_options()
    if members_dict:
        member_label = st.selectbox("Member", list(members_dict.keys()))
        member_id = members_dict[member_label]
        value = member_value(member_id)
        outstanding_loans = float(scalar("SELECT COALESCE(SUM(outstanding_principal),0) FROM loans WHERE member_id=:m AND status IN ('Approved','Disbursed','Active')", {"m": member_id}, 0))
        withdrawable = max(value - outstanding_loans, 0)
        st.info(f"Estimated member value: KES {value:,.2f}; outstanding loans: KES {outstanding_loans:,.2f}; withdrawable: KES {withdrawable:,.2f}")
        withdrawal_amount = st.number_input("Withdrawal amount", min_value=0.0, step=1000.0)
        withdrawal_type = st.selectbox("Withdrawal type", ["Partial", "Full Exit"])
        if st.button("Submit withdrawal request"):
            if withdrawal_amount > withdrawable:
                st.error("Amount exceeds withdrawable balance.")
            else:
                run("INSERT INTO withdrawals (member_id, amount, withdrawal_type, status, created_by, created_at) VALUES (:m,:a,:t,'Submitted',:u,:n)", {"m": member_id, "a": withdrawal_amount, "t": withdrawal_type, "u": user, "n": datetime.now().isoformat()})
                log("Withdrawal submitted", f"member={member_id}, amount={withdrawal_amount}", user)
                st.success("Withdrawal submitted.")
                st.rerun()
    withdrawals = df("SELECT w.*, m.full_name FROM withdrawals w JOIN members m ON w.member_id=m.id ORDER BY w.id DESC")
    st.dataframe(withdrawals, use_container_width=True, hide_index=True)
    withdrawal_id = st.number_input("Withdrawal ID to approve/pay", min_value=1, step=1)
    if st.button("Approve and redeem units"):
        selected = df("SELECT * FROM withdrawals WHERE id=:id", {"id": withdrawal_id})
        if selected.empty:
            st.error("Withdrawal not found.")
        elif selected.iloc[0]["created_by"] == user:
            st.error("Maker cannot approve own withdrawal.")
        elif role not in ["Checker", "Chairperson", "Admin"]:
            st.error("Only checker, chairperson or admin can approve.")
        else:
            record = selected.iloc[0]
            redeem_units(int(record["member_id"]), float(record["amount"]), f"WDR-{withdrawal_id}", user)
            run("UPDATE withdrawals SET status='Approved/Paid', approved_by=:u WHERE id=:id", {"u": user, "id": withdrawal_id})
            log("Withdrawal approved", str(withdrawal_id), user)
            st.success("Withdrawal approved and units redeemed.")
            st.rerun()

elif menu == "Reports":
    st.header("Reports")
    report = st.selectbox("Select report", ["Audit", "Contributions", "Member Units", "Loans", "Withdrawals", "Fund Valuations"])
    queries = {
        "Audit": "SELECT * FROM audit_logs ORDER BY id DESC",
        "Contributions": "SELECT c.*, m.full_name FROM contributions c JOIN members m ON c.member_id=m.id ORDER BY c.id DESC",
        "Member Units": "SELECT u.*, m.full_name FROM member_units u JOIN members m ON u.member_id=m.id ORDER BY u.id DESC",
        "Loans": "SELECT l.*, m.full_name FROM loans l JOIN members m ON l.member_id=m.id ORDER BY l.id DESC",
        "Withdrawals": "SELECT w.*, m.full_name FROM withdrawals w JOIN members m ON w.member_id=m.id ORDER BY w.id DESC",
        "Fund Valuations": "SELECT * FROM fund_valuations ORDER BY id DESC",
    }
    report_data = df(queries[report])
    st.dataframe(report_data, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", report_data.to_csv(index=False).encode("utf-8"), file_name=f"{report.lower().replace(' ', '_')}.csv", mime="text/csv")

elif menu == "Admin":
    st.header("Admin")
    st.warning("For live use, enable Supabase Auth, Row Level Security, backups and secure document storage.")
    for table in ["groups", "members", "contributions", "member_units", "payment_uploads", "investments", "investment_returns", "loans", "withdrawals", "fund_valuations", "audit_logs"]:
        with st.expander(table):
            st.dataframe(df(f"SELECT * FROM {table}"), use_container_width=True, hide_index=True)
