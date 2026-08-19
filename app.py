
import streamlit as st
import pandas as pd
from datetime import date, datetime
from sqlalchemy import create_engine, text
try:
    from supabase import create_client
except Exception:
    create_client = None

APP_TITLE = "Committee Investment Vehicle v3"
APP_SUBTITLE = "Role-aware menus, member-scoped access, drill-down dashboards and corrected balance display"
DEFAULT_DB = "sqlite:///committee_investment_vehicle_v3.db"

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
[data-testid="stSidebar"]{display:none}.block-container{padding-top:1.0rem;max-width:1320px}.hero{background:linear-gradient(120deg,#0B1F3A 0%,#1F4E79 62%,#0E7C7B 100%);color:white;border-radius:22px;padding:1.25rem 1.55rem;box-shadow:0 12px 28px rgba(11,31,58,.16);margin-bottom:1rem}.hero h1{font-size:2.0rem;margin:0}.hero p{margin:.35rem 0 0;color:#E5EEF7}.stRadio>div{display:flex;gap:.3rem;flex-wrap:wrap;background:#EEF2F7;padding:.35rem;border-radius:16px}.stRadio [role="radiogroup"] label{background:#fff;border:1px solid #D7DEE8;border-radius:999px;padding:.45rem .85rem;margin:.15rem}.stRadio [role="radiogroup"] label:hover{border-color:#1F4E79}div[data-testid="stMetric"]{background:#fff;border:1px solid #E5E7EB;border-radius:16px;padding:1rem;box-shadow:0 6px 18px rgba(15,23,42,.06)}div[data-testid="stMetric"] label{color:#6B7280!important}.note{color:#6B7280;font-size:.9rem}.danger{background:#FEE2E2;border:1px solid #FCA5A5;border-radius:12px;padding:.8rem}.ok{background:#ECFDF5;border:1px solid #86EFAC;border-radius:12px;padding:.8rem}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_engine():
    db_url = st.secrets.get("DATABASE_URL", DEFAULT_DB) if hasattr(st, "secrets") else DEFAULT_DB
    return create_engine(db_url, future=True)
engine=get_engine()

def run(sql, params=None):
    with engine.begin() as conn: conn.execute(text(sql), params or {})
def df(sql, params=None):
    with engine.begin() as conn: return pd.read_sql(text(sql), conn, params=params or {})
def scalar(sql, params=None, default=0):
    d=df(sql, params)
    if d.empty: return default
    v=d.iloc[0,0]
    return default if pd.isna(v) else v

def table_exists(t):
    try: return int(scalar("select count(*) from information_schema.tables where table_schema='public' and table_name=:t", {"t":t}, 0))>0
    except Exception: return False

def ensure_local_tables():
    # Only for local demo. Supabase should already have the v2 tables.
    stmts=[
    "create table if not exists groups(id integer primary key, name text, base_currency text, opening_unit_price real, created_at text)",
    "create table if not exists members(id integer primary key, group_id integer default 1, member_code text, full_name text, phone text, email text, status text default 'Active', join_date text, created_at text, auth_user_id text, is_active boolean default 1, default_role text default 'Member')",
    "create table if not exists contributions(id integer primary key, group_id integer default 1, member_id integer, contribution_month text, expected_amount real, amount_paid real, arrears real, receipt_ref text unique, approved_by text, created_at text)",
    "create table if not exists member_units(id integer primary key, group_id integer default 1, member_id integer, transaction_date text, transaction_type text, amount real, unit_price real, units real, reference text, created_at text)",
    "create table if not exists investment_returns(id integer primary key, group_id integer default 1, period text, return_type text, asset_class text, amount real, status text, created_at text)",
    "create table if not exists investments(id integer primary key, group_id integer default 1, asset_class text, institution text, description text, cost real, current_value real, status text, created_at text)",
    "create table if not exists fund_valuations(id integer primary key, group_id integer default 1, valuation_date text, bank_balance real, mmf_balance real, investment_value real, loans_receivable real, liabilities real, nav real, total_units real, unit_price real, status text, created_at text)",
    "create table if not exists loans(id integer primary key, group_id integer default 1, member_id integer, principal real, annual_rate real, months integer, outstanding_principal real, monthly_payment real, status text, created_by text, approved_by text, created_at text)",
    "create table if not exists withdrawals(id integer primary key, group_id integer default 1, member_id integer, amount real, withdrawal_type text, status text, created_by text, approved_by text, created_at text)",
    "create table if not exists meetings(id integer primary key, group_id integer default 1, meeting_type text, meeting_title text, meeting_date text, venue text, host_member_id integer, status text, agenda text, minutes text, resolutions text, created_by text, created_at text)",
    "create table if not exists roles(id integer primary key, role_name text unique, description text, is_system_role boolean, status text, created_at text)",
    "create table if not exists member_roles(id integer primary key, group_id integer default 1, member_id integer, role_id integer, start_date text, end_date text, status text, assigned_by text, assignment_reason text, remarks text, created_at text)",
    "create table if not exists financial_schedules(id integer primary key, group_id integer default 1, schedule_type text, period_start text, period_end text, prepared_by text, approved_by text, status text, notes text, created_at text)",
    "create table if not exists agm_records(id integer primary key, group_id integer default 1, agm_year integer, venue text, budgeted_cost real, actual_cost real, additional_contribution_required real, status text, created_at text)",
    "create table if not exists group_compliance(id integer primary key, group_id integer default 1, registration_status text, registration_type text, registration_number text, kra_pin_status text, kra_pin_number text, bank_account_status text, tax_status text, remarks text, created_at text)",
    "create table if not exists audit_logs(id integer primary key, group_id integer default 1, action text, details text, user_name text, created_at text)"
    ]
    for s in stmts: run(s)
ensure_local_tables()

def log(action, details, user):
    try: run("insert into audit_logs(action,details,user_name,created_at) values(:a,:d,:u,:n)", {"a":action,"d":details,"u":user,"n":datetime.now().isoformat()})
    except Exception: pass

def supabase_client():
    if create_client is None: return None
    url=st.secrets.get("SUPABASE_URL", None) if hasattr(st,"secrets") else None
    key=st.secrets.get("SUPABASE_ANON_KEY", None) if hasattr(st,"secrets") else None
    if not url or not key: return None
    return create_client(url,key)

def send_otp(email):
    sb=supabase_client()
    if not sb:
        st.error("SUPABASE_URL and SUPABASE_ANON_KEY are missing in Streamlit secrets."); return
    sb.auth.sign_in_with_otp({"email":email, "options":{"should_create_user":True}})
    st.success("OTP or magic link sent to the member email address.")

def verify_otp(email, token):
    sb=supabase_client()
    if not sb: return False
    res=sb.auth.verify_otp({"email":email,"token":token,"type":"email"})
    if not res.user: return False
    st.session_state.auth_email=email.lower().strip(); st.session_state.auth_user_id=str(res.user.id)
    return True

def get_member_by_email(email):
    d=df("select * from members where lower(email)=lower(:e) and coalesce(status,'Active')='Active' limit 1", {"e":email})
    return None if d.empty else d.iloc[0]

def roles_for_member(member_id):
    try:
        d=df("select r.role_name from member_roles mr join roles r on r.id=mr.role_id where mr.member_id=:m and mr.status='Active' and (mr.end_date is null or mr.end_date>=current_date) order by r.role_name", {"m":int(member_id)})
        roles=d['role_name'].tolist() if not d.empty else ['Member']
    except Exception: roles=['Member']
    if 'Member' not in roles: roles.insert(0,'Member')
    return roles

def current_unit_price():
    return float(scalar("select unit_price from fund_valuations where status='Approved' order by valuation_date desc, id desc limit 1", default=100))

def member_paid(member_id):
    return float(scalar("select coalesce(sum(amount_paid),0) from contributions where member_id=:m", {"m":int(member_id)}, 0))
def member_arrears(member_id):
    return float(scalar("select coalesce(sum(arrears),0) from contributions where member_id=:m", {"m":int(member_id)}, 0))
def total_paid():
    return float(scalar("select coalesce(sum(amount_paid),0) from contributions", default=0))
def total_arrears():
    return float(scalar("select coalesce(sum(arrears),0) from contributions", default=0))
def total_returns():
    return float(scalar("select coalesce(sum(amount),0) from investment_returns", default=0))
def total_units(member_id=None):
    if member_id: return float(scalar("select coalesce(sum(units),0) from member_units where member_id=:m", {"m":int(member_id)}, 0))
    return float(scalar("select coalesce(sum(units),0) from member_units", default=0))
def member_value(member_id):
    # Primary: units x current unit price. Fallback: actual paid, for pre-unitisation imports.
    units=total_units(member_id); value=units*current_unit_price()
    return value if value>0 else member_paid(member_id)
def fund_nav():
    nav=float(scalar("select nav from fund_valuations where status='Approved' order by valuation_date desc,id desc limit 1", default=0))
    return nav if nav>0 else (total_paid()+total_returns())

def menu_for_role(role):
    # Important: menus are based on the ACTIVE role, not all assigned roles.
    menus={
        'Member':['Dashboard','My Statement','Contributions','Loans','Withdrawals','Meetings'],
        'Administrator':['Admin Dashboard','Members','Contributions','Investments','Loans','Withdrawals','Meetings','Financial Schedules','Governance','AGM & Compliance','Admin'],
        'Chairperson':['Admin Dashboard','Contributions','Loans','Withdrawals','Meetings','Governance','AGM & Compliance'],
        'Secretary':['Secretary Dashboard','Members','Contributions','Meetings','Governance','AGM & Compliance'],
        'Organising Secretary':['Meetings','AGM & Compliance'],
        'Treasurer':['Treasurer Dashboard','Contributions','Investments','Loans','Withdrawals','Financial Schedules'],
        'Accountant':['Accountant Dashboard','Contributions','Investments','Loans','Financial Schedules'],
        'Investment Analyst':['Investments','Admin Dashboard'],
        'Maker':['Contributions','Loans','Withdrawals'],
        'Checker':['Contributions','Loans','Withdrawals'],
        'Approver':['Contributions','Loans','Withdrawals'],
        'Auditor':['Admin Dashboard','Financial Schedules','Meetings']
    }
    return menus.get(role, menus['Member'])

def member_options(all_members=False, own_id=None):
    if all_members:
        d=df("select id, member_code, full_name from members where coalesce(status,'Active')='Active' order by member_code")
    else:
        d=df("select id, member_code, full_name from members where id=:id", {"id":int(own_id)})
    return {f"{r.member_code} - {r.full_name}":int(r.id) for _,r in d.iterrows()}

def show_dataframe(title, data):
    st.markdown(f"#### {title}")
    st.dataframe(data, use_container_width=True, hide_index=True)

st.markdown(f"<div class='hero'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p></div>", unsafe_allow_html=True)

# Login
if 'auth_email' not in st.session_state:
    st.subheader('Member login')
    email=st.text_input('Email address')
    col1,col2=st.columns(2)
    with col1:
        if st.button('Send OTP / magic link') and email: send_otp(email.strip().lower())
    with col2:
        token=st.text_input('OTP code')
        if st.button('Verify OTP') and email and token:
            if verify_otp(email.strip().lower(), token.strip()): st.rerun()
            else: st.error('OTP verification failed.')
    with st.expander('Temporary fallback for pilot testing'):
        fb=st.text_input('Use member email already in members table')
        if st.button('Continue') and fb:
            st.session_state.auth_email=fb.strip().lower(); st.session_state.auth_user_id=None; st.rerun()
    st.stop()

m=get_member_by_email(st.session_state.auth_email)
if m is None:
    st.error('This email is not linked to an active member record. Ask the administrator to update the members table.')
    if st.button('Logout'): st.session_state.clear(); st.rerun()
    st.stop()
member_id=int(m['id']); member_name=m['full_name']; roles=roles_for_member(member_id)
if 'active_role' not in st.session_state or st.session_state.active_role not in roles: st.session_state.active_role='Member' if 'Member' in roles else roles[0]
col1,col2,col3=st.columns([2,2,1])
with col1: st.write(f"Signed in as **{member_name}**")
with col2: st.session_state.active_role=st.selectbox('Active role', roles, index=roles.index(st.session_state.active_role))
with col3:
    if st.button('Logout'): st.session_state.clear(); st.rerun()
role=st.session_state.active_role
menus=menu_for_role(role)
menu=st.radio('Menu', menus, horizontal=True, label_visibility='collapsed')
st.caption('Menus are based on the active role only. Switch to Member to see member-only screens, or Administrator to see administrator screens.')

# Dashboards
if menu in ['Dashboard','Admin Dashboard','Secretary Dashboard','Treasurer Dashboard','Accountant Dashboard']:
    admin_view = menu != 'Dashboard'
    st.subheader(menu)
    c1,c2,c3,c4,c5=st.columns(5)
    if admin_view:
        c1.metric('Fund NAV', f"KES {fund_nav():,.0f}")
        c2.metric('Contributions', f"KES {total_paid():,.0f}")
        c3.metric('Returns', f"KES {total_returns():,.0f}")
        c4.metric('Arrears', f"KES {total_arrears():,.0f}")
        c5.metric('Members', int(scalar("select count(*) from members where coalesce(status,'Active')='Active'", default=0)))
        detail=st.selectbox('Click/select a card to view the makeup', ['Fund NAV','Contributions','Returns','Arrears','Members'])
        if detail=='Fund NAV':
            st.info('If no approved valuation exists, Fund NAV is shown as paid contributions plus recorded returns. Create a valuation under Investments to replace this fallback.')
            show_dataframe('Latest valuations', df("select * from fund_valuations order by id desc limit 20"))
        elif detail=='Contributions':
            show_dataframe('Contribution makeup by member', df("select m.member_code,m.full_name,sum(c.expected_amount) expected_total,sum(c.amount_paid) actual_paid,sum(c.arrears) arrears from contributions c join members m on m.id=c.member_id group by m.member_code,m.full_name order by m.member_code"))
            show_dataframe('Contribution makeup by month', df("select contribution_month,sum(expected_amount) expected_total,sum(amount_paid) actual_paid,sum(arrears) arrears from contributions group by contribution_month order by contribution_month"))
        elif detail=='Returns':
            show_dataframe('Return details', df("select * from investment_returns order by period desc,id desc"))
        elif detail=='Arrears':
            show_dataframe('Arrears by member', df("select m.member_code,m.full_name,sum(c.arrears) arrears from contributions c join members m on m.id=c.member_id group by m.member_code,m.full_name having sum(c.arrears)>0 order by arrears desc"))
            show_dataframe('Arrears by month', df("select contribution_month,sum(arrears) arrears from contributions group by contribution_month having sum(arrears)>0 order by contribution_month"))
        elif detail=='Members':
            show_dataframe('Members', df("select member_code,full_name,phone,email,status,join_date from members order by member_code"))
        st.markdown('---')
        left,right=st.columns(2)
        with left:
            d=df("select contribution_month,sum(amount_paid) actual_paid from contributions group by contribution_month order by contribution_month")
            if not d.empty:
                d['cumulative']=d['actual_paid'].cumsum(); st.markdown('#### Contribution Growth'); st.line_chart(d.set_index('contribution_month'))
        with right:
            a=df("select m.full_name,sum(c.arrears) arrears from contributions c join members m on m.id=c.member_id group by m.full_name having sum(c.arrears)>0 order by arrears desc")
            st.markdown('#### Arrears Makeup'); st.dataframe(a, use_container_width=True, hide_index=True)
    else:
        c1.metric('My Value', f"KES {member_value(member_id):,.0f}")
        c2.metric('My Contributions', f"KES {member_paid(member_id):,.0f}")
        c3.metric('My Arrears', f"KES {member_arrears(member_id):,.0f}")
        c4.metric('My Units', f"{total_units(member_id):,.2f}")
        c5.metric('Unit Price', f"KES {current_unit_price():,.2f}")
        detail=st.selectbox('Click/select a card to view the makeup', ['My Value','My Contributions','My Arrears','My Units'])
        if detail in ['My Value','My Contributions','My Arrears']:
            show_dataframe('My contribution details', df("select contribution_month,expected_amount,amount_paid,arrears,receipt_ref,created_at from contributions where member_id=:m order by contribution_month", {"m":member_id}))
        if detail=='My Units':
            show_dataframe('My unit details', df("select transaction_date,transaction_type,amount,unit_price,units,reference from member_units where member_id=:m order by transaction_date", {"m":member_id}))

elif menu=='My Statement':
    st.header('My Statement')
    st.metric('Current displayed value', f"KES {member_value(member_id):,.0f}")
    show_dataframe('My contributions', df("select contribution_month,expected_amount,amount_paid,arrears,receipt_ref from contributions where member_id=:m order by contribution_month", {"m":member_id}))
    show_dataframe('My loans', df("select * from loans where member_id=:m order by id desc", {"m":member_id}))
    show_dataframe('My withdrawals', df("select * from withdrawals where member_id=:m order by id desc", {"m":member_id}))

elif menu=='Members':
    st.header('Members')
    show_dataframe('All members', df("select id,member_code,full_name,phone,email,status,join_date,auth_user_id,is_active from members order by member_code"))

elif menu=='Contributions':
    st.header('Contributions')
    can_all=role in ['Administrator','Secretary','Treasurer','Accountant','Maker','Checker','Approver']
    opts=member_options(can_all, member_id)
    tab1,tab2,tab3=st.tabs(['Upload Proof','Review/Approve','Reports'])
    with tab1:
        st.info('Member role can submit only own proof. Admin/finance roles can submit for any member.')
        with st.form('proof'):
            ml=st.selectbox('Member', list(opts.keys())); amount=st.number_input('Amount paid', min_value=0.0, step=500.0); month=st.text_input('Contribution month', value=date.today().strftime('%Y-%m')); ref=st.text_input('Transaction reference')
            if st.form_submit_button('Submit proof') and amount>0 and ref:
                run("insert into payment_uploads(member_id,amount,contribution_month,payment_method,destination,transaction_ref,uploaded_by,status,created_at) values(:m,:a,:mo,'Manual','Bank/MMF',:r,:u,'Submitted',:n)", {"m":opts[ml],"a":amount,"mo":month,"r":ref,"u":member_name,"n":datetime.now().isoformat()}); st.success('Submitted'); st.rerun()
    with tab2:
        if can_all:
            q=df("select p.id,m.member_code,m.full_name,p.amount,p.contribution_month,p.transaction_ref,p.uploaded_by,p.verified_by,p.status from payment_uploads p join members m on m.id=p.member_id where p.status in ('Submitted','Verified') order by p.id desc")
            show_dataframe('Pending queue', q)
            pid=st.number_input('Payment ID', min_value=1, step=1); action=st.selectbox('Action',['Verify','Approve and Post','Reject'])
            if st.button('Process'):
                p=df('select * from payment_uploads where id=:id', {'id':pid})
                if p.empty: st.error('Not found')
                else:
                    rec=p.iloc[0]
                    if action=='Verify': run("update payment_uploads set status='Verified',verified_by=:u where id=:id", {"u":member_name,"id":pid}); st.success('Verified'); st.rerun()
                    elif action=='Approve and Post':
                        if rec.get('uploaded_by')==member_name or rec.get('verified_by')==member_name: st.error('Maker/verifier cannot approve own transaction.')
                        else:
                            run("insert into contributions(member_id,contribution_month,expected_amount,amount_paid,arrears,receipt_ref,approved_by,created_at) values(:m,:mo,:e,:a,0,:r,:u,:n) on conflict(receipt_ref) do update set amount_paid=excluded.amount_paid", {"m":int(rec['member_id']),"mo":rec['contribution_month'],"e":float(rec['amount']),"a":float(rec['amount']),"r":rec['transaction_ref'],"u":member_name,"n":datetime.now().isoformat()})
                            run("update payment_uploads set status='Approved',approved_by=:u where id=:id", {"u":member_name,"id":pid}); st.success('Posted'); st.rerun()
                    else: run("update payment_uploads set status='Rejected',approved_by=:u where id=:id", {"u":member_name,"id":pid}); st.warning('Rejected'); st.rerun()
        else: st.info('Only finance/approval roles can view approval queues.')
    with tab3:
        if can_all:
            show_dataframe('All contribution totals', df("select m.member_code,m.full_name,sum(c.expected_amount) expected_total,sum(c.amount_paid) actual_paid,sum(c.arrears) arrears from contributions c join members m on m.id=c.member_id group by m.member_code,m.full_name order by m.member_code"))
        else:
            show_dataframe('My contribution totals', df("select contribution_month,expected_amount,amount_paid,arrears,receipt_ref from contributions where member_id=:m order by contribution_month", {"m":member_id}))

elif menu=='Investments':
    st.header('Investments')
    tab1,tab2,tab3=st.tabs(['Register','Returns','Valuation'])
    with tab1:
        with st.form('investment'):
            asset=st.selectbox('Asset class',['Bank','MMF','Treasury Bond','Corporate Bond','Equity','REIT','Private Equity','Venture Capital','Other']); inst=st.text_input('Institution'); desc=st.text_input('Description'); cost=st.number_input('Cost', min_value=0.0); value=st.number_input('Current value', min_value=0.0)
            if st.form_submit_button('Save'): run("insert into investments(asset_class,institution,description,cost,current_value,status,created_at) values(:a,:i,:d,:c,:v,'Active',:n)", {"a":asset,"i":inst,"d":desc,"c":cost,"v":value,"n":datetime.now().isoformat()}); st.success('Saved'); st.rerun()
        show_dataframe('Investments', df('select * from investments order by id desc'))
    with tab2:
        with st.form('returns'):
            period=st.text_input('Period', value=date.today().strftime('%Y-%m')); amount=st.number_input('Return amount', step=1000.0); rt=st.selectbox('Type',['MMF Interest','Bond Coupon','Dividend','Fair Value Gain','Fair Value Loss','Other'])
            if st.form_submit_button('Record return'): run("insert into investment_returns(period,return_type,amount,status,created_at) values(:p,:t,:a,'Approved',:n)", {"p":period,"t":rt,"a":amount,"n":datetime.now().isoformat()}); st.success('Recorded'); st.rerun()
        show_dataframe('Returns', df('select * from investment_returns order by id desc'))
    with tab3:
        inv=float(scalar('select coalesce(sum(current_value),0) from investments', default=0)); bank=st.number_input('Bank balance',min_value=0.0); mmf=st.number_input('MMF balance',min_value=0.0); liab=st.number_input('Liabilities',min_value=0.0); nav=bank+mmf+inv-liab; units=total_units(); price=100 if units==0 else nav/units
        st.metric('Calculated NAV', f"KES {nav:,.0f}"); st.metric('Calculated unit price', f"KES {price:,.4f}")
        if st.button('Approve valuation'): run("insert into fund_valuations(valuation_date,bank_balance,mmf_balance,investment_value,loans_receivable,liabilities,nav,total_units,unit_price,status,created_at) values(:d,:b,:m,:i,0,:l,:nav,:u,:p,'Approved',:n)", {"d":str(date.today()),"b":bank,"m":mmf,"i":inv,"l":liab,"nav":nav,"u":units,"p":price,"n":datetime.now().isoformat()}); st.success('Valuation approved'); st.rerun()

elif menu=='Loans':
    st.header('Loans')
    all_allowed=role in ['Administrator','Treasurer','Accountant','Approver','Checker']
    opts=member_options(all_allowed, member_id)
    with st.form('loan'):
        ml=st.selectbox('Borrower', list(opts.keys())); amount=st.number_input('Loan amount', min_value=0.0, step=1000.0); months=st.number_input('Months', min_value=1,value=12)
        if st.form_submit_button('Submit loan'): run("insert into loans(member_id,principal,months,outstanding_principal,status,created_by,created_at) values(:m,:a,:mo,:a,'Submitted',:u,:n)", {"m":opts[ml],"a":amount,"mo":months,"u":member_name,"n":datetime.now().isoformat()}); st.success('Submitted'); st.rerun()
    q='select l.*,m.full_name from loans l join members m on m.id=l.member_id order by l.id desc' if all_allowed else 'select l.*,m.full_name from loans l join members m on m.id=l.member_id where l.member_id=:m order by l.id desc'
    show_dataframe('Loans', df(q, {} if all_allowed else {"m":member_id}))

elif menu=='Withdrawals':
    st.header('Withdrawals')
    all_allowed=role in ['Administrator','Treasurer','Accountant','Approver','Checker']
    opts=member_options(all_allowed, member_id)
    with st.form('withdrawal'):
        ml=st.selectbox('Member', list(opts.keys())); amount=st.number_input('Withdrawal amount', min_value=0.0, step=1000.0)
        if st.form_submit_button('Submit withdrawal'): run("insert into withdrawals(member_id,amount,withdrawal_type,status,created_by,created_at) values(:m,:a,'Partial','Submitted',:u,:n)", {"m":opts[ml],"a":amount,"u":member_name,"n":datetime.now().isoformat()}); st.success('Submitted'); st.rerun()
    q='select w.*,m.full_name from withdrawals w join members m on m.id=w.member_id order by w.id desc' if all_allowed else 'select w.*,m.full_name from withdrawals w join members m on m.id=w.member_id where w.member_id=:m order by w.id desc'
    show_dataframe('Withdrawals', df(q, {} if all_allowed else {"m":member_id}))

elif menu=='Meetings':
    st.header('Meetings')
    can_manage=role in ['Administrator','Secretary','Organising Secretary','Chairperson']
    if can_manage:
        with st.form('meeting'):
            mt=st.selectbox('Type',['Monthly meeting','Investment committee meeting','Special meeting','AGM']); title=st.text_input('Title'); d=st.date_input('Date'); venue=st.text_input('Venue')
            opts=member_options(True); host=st.selectbox('Host',['None']+list(opts.keys()))
            if st.form_submit_button('Create meeting'): run("insert into meetings(meeting_type,meeting_title,meeting_date,venue,host_member_id,status,created_by,created_at) values(:mt,:t,:d,:v,:h,'Planned',:u,:n)", {"mt":mt,"t":title,"d":str(d),"v":venue,"h":None if host=='None' else opts[host],"u":member_name,"n":datetime.now().isoformat()}); st.success('Created'); st.rerun()
    show_dataframe('Meetings', df('select me.*,m.full_name host_name from meetings me left join members m on m.id=me.host_member_id order by meeting_date desc'))

elif menu=='Financial Schedules':
    st.header('Financial Schedules')
    with st.form('schedule'):
        stype=st.selectbox('Schedule type',['Member contribution schedule','Member arrears schedule','Member units schedule','Investment register','Cashbook','Trial balance','Statement of financial position','Statement of changes in member funds','AGM cost schedule','Role assignment history']); ps=st.date_input('Period start'); pe=st.date_input('Period end'); notes=st.text_area('Notes')
        if st.form_submit_button('Create schedule task'): run("insert into financial_schedules(schedule_type,period_start,period_end,prepared_by,status,notes,created_at) values(:s,:ps,:pe,:p,'Pending',:notes,:n)", {"s":stype,"ps":str(ps),"pe":str(pe),"p":member_name,"notes":notes,"n":datetime.now().isoformat()}); st.success('Created'); st.rerun()
    show_dataframe('Schedules', df('select * from financial_schedules order by id desc'))

elif menu=='Governance':
    st.header('Governance & Roles')
    opts=member_options(True); roles_df=df("select id,role_name from roles where coalesce(status,'Active')='Active' order by role_name")
    ropts={r.role_name:int(r.id) for _,r in roles_df.iterrows()}
    with st.form('assign'):
        ml=st.selectbox('Member', list(opts.keys())); rl=st.selectbox('Role', list(ropts.keys())); reason=st.selectbox('Reason',['Elected at AGM','Temporary delegation','Incapacitation','Term expiry','Other']); remarks=st.text_area('Remarks')
        if st.form_submit_button('Assign role'): run("insert into member_roles(member_id,role_id,start_date,status,assigned_by,assignment_reason,remarks,created_at) values(:m,:r,current_date,'Active',:u,:reason,:remarks,:n) on conflict do nothing", {"m":opts[ml],"r":ropts[rl],"u":member_name,"reason":reason,"remarks":remarks,"n":datetime.now().isoformat()}); st.success('Assigned'); st.rerun()
    show_dataframe('Role history', df('select mr.*,m.full_name,r.role_name from member_roles mr join members m on m.id=mr.member_id join roles r on r.id=mr.role_id order by mr.created_at desc'))

elif menu=='AGM & Compliance':
    st.header('AGM & Compliance')
    with st.form('agm'):
        y=st.number_input('AGM year', min_value=2024, value=date.today().year); venue=st.text_input('Venue'); budget=st.number_input('Budgeted cost', min_value=0.0); actual=st.number_input('Actual cost', min_value=0.0)
        if st.form_submit_button('Save AGM'): run("insert into agm_records(agm_year,venue,budgeted_cost,actual_cost,status,created_at) values(:y,:v,:b,:a,'Planned',:n) on conflict do nothing", {"y":int(y),"v":venue,"b":budget,"a":actual,"n":datetime.now().isoformat()}); st.success('Saved'); st.rerun()
    show_dataframe('AGM records', df('select * from agm_records order by agm_year desc'))
    show_dataframe('Compliance', df('select * from group_compliance order by id desc'))

elif menu=='Admin':
    st.header('Admin')
    for t in ['members','roles','member_roles','contributions','member_units','payment_uploads','investments','investment_returns','fund_valuations','loans','withdrawals','meetings','financial_schedules','agm_records','audit_logs']:
        with st.expander(t):
            try: st.dataframe(df(f'select * from {t} order by id desc'), use_container_width=True, hide_index=True)
            except Exception as e: st.warning(str(e))
