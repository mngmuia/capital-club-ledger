import streamlit as st
import pandas as pd
from datetime import date, datetime
from sqlalchemy import create_engine, text
try:
    from supabase import create_client
except Exception:
    create_client = None

APP_TITLE = "Committee Investment Vehicle v2"
APP_SUBTITLE = "Governance, roles, meetings, schedules, member access and investment analytics"
DEFAULT_DB = "sqlite:///committee_investment_vehicle_v2.db"

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
[data-testid="stSidebar"]{display:none}.block-container{padding-top:1.1rem;max-width:1320px}.civ-hero{background:linear-gradient(120deg,#0B1F3A 0%,#1F4E79 62%,#0E7C7B 100%);color:white;border-radius:22px;padding:1.35rem 1.55rem;box-shadow:0 12px 28px rgba(11,31,58,.16);margin-bottom:1rem}.civ-hero h1{font-size:2.05rem;margin:0;letter-spacing:-.02em}.civ-hero p{margin:.35rem 0 0;color:#E5EEF7}div[data-testid="stMetric"]{background:#fff;border:1px solid #E5E7EB;border-radius:16px;padding:1rem;box-shadow:0 6px 18px rgba(15,23,42,.06)}div[data-testid="stMetric"] label{color:#6B7280!important}.stRadio>div{display:flex;gap:.3rem;flex-wrap:wrap;background:#EEF2F7;padding:.35rem;border-radius:16px}.stRadio [role="radiogroup"] label{background:#fff;border:1px solid #D7DEE8;border-radius:999px;padding:.45rem .85rem;margin:.15rem}.stRadio [role="radiogroup"] label:hover{border-color:#1F4E79}hr{margin:1rem 0}.small-note{font-size:.9rem;color:#6B7280}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_engine():
    db_url = st.secrets.get("DATABASE_URL", DEFAULT_DB) if hasattr(st, "secrets") else DEFAULT_DB
    return create_engine(db_url, future=True)
engine = get_engine()

def run(sql, params=None):
    with engine.begin() as conn: conn.execute(text(sql), params or {})
def df(sql, params=None):
    with engine.begin() as conn: return pd.read_sql(text(sql), conn, params=params or {})
def scalar(sql, params=None, default=0):
    d = df(sql, params)
    if d.empty: return default
    v=d.iloc[0,0]
    return default if pd.isna(v) else v

def has_table(name):
    try:
        return int(scalar("select count(*) from information_schema.tables where table_schema='public' and table_name=:t", {"t":name}, 0)) > 0
    except Exception:
        return False

def log(action, details, user):
    try:
        run("insert into audit_logs(action, details, user_name, created_at) values(:a,:d,:u,:n)", {"a":action,"d":details,"u":user,"n":datetime.now().isoformat()})
    except Exception: pass

def supabase_client():
    if create_client is None: return None
    url = st.secrets.get("SUPABASE_URL", None) if hasattr(st, "secrets") else None
    key = st.secrets.get("SUPABASE_ANON_KEY", None) if hasattr(st, "secrets") else None
    if not url or not key: return None
    return create_client(url, key)

def send_otp(email):
    sb = supabase_client()
    if not sb:
        st.error("SUPABASE_URL and SUPABASE_ANON_KEY are not configured in Streamlit secrets.")
        return
    sb.auth.sign_in_with_otp({"email": email, "options": {"should_create_user": True}})
    st.session_state.pending_email = email
    st.success("OTP or magic link sent. Check the member email address.")

def verify_otp(email, token):
    sb = supabase_client()
    if not sb:
        return False
    res = sb.auth.verify_otp({"email": email, "token": token, "type": "email"})
    user = res.user
    if not user:
        return False
    st.session_state.auth_email = email.lower().strip()
    st.session_state.auth_user_id = str(user.id)
    return True

def get_member_by_email(email):
    d = df("select * from members where lower(email)=lower(:e) limit 1", {"e": email})
    return None if d.empty else d.iloc[0]

def get_roles(member_id):
    if not has_table('member_roles'):
        return ['Member']
    d = df("""
        select r.role_name from member_roles mr join roles r on r.id=mr.role_id
        where mr.member_id=:m and mr.status='Active' and (mr.end_date is null or mr.end_date>=current_date)
        order by r.role_name
    """, {"m": int(member_id)})
    roles = d['role_name'].tolist() if not d.empty else ['Member']
    return roles

def member_id_from_user():
    email = st.session_state.get('auth_email')
    if not email: return None, None
    m = get_member_by_email(email)
    if m is None: return None, email
    try:
        if st.session_state.get('auth_user_id') and not m.get('auth_user_id'):
            run("update members set auth_user_id=:u where id=:id", {"u": st.session_state.auth_user_id, "id": int(m['id'])})
    except Exception: pass
    return int(m['id']), email

def current_unit_price():
    return float(scalar("select unit_price from fund_valuations where status='Approved' order by valuation_date desc, id desc limit 1", default=100))
def total_units(member_id=None):
    if member_id:
        return float(scalar("select coalesce(sum(units),0) from member_units where member_id=:m", {"m":member_id}, 0))
    return float(scalar("select coalesce(sum(units),0) from member_units", default=0))
def member_value(member_id):
    return total_units(member_id)*current_unit_price()
def member_options(scope_all=True, own_id=None):
    if scope_all:
        d = df("select id, full_name from members where status='Active' order by full_name")
    else:
        d = df("select id, full_name from members where id=:id", {"id": own_id})
    return {f"{r.full_name} (ID {r.id})": int(r.id) for _,r in d.iterrows()}

def has_any(role, list_roles): return role in list_roles or 'Administrator' in list_roles

def filtered_menu(active_role, roles):
    admin = 'Administrator' in roles
    items = ['Dashboard','My Statement','Contributions','Loans','Withdrawals','Meetings']
    if active_role in ['Administrator','Treasurer','Investment Analyst','Accountant'] or admin: items.append('Investments')
    if active_role in ['Administrator','Accountant','Treasurer','Auditor'] or admin: items.append('Financial Schedules')
    if active_role in ['Administrator','Secretary','Organising Secretary','Chairperson'] or admin: items.append('Governance')
    if active_role in ['Administrator','Secretary','Organising Secretary','Chairperson'] or admin: items.append('AGM & Compliance')
    if admin: items.append('Admin')
    return items

st.markdown(f"<div class='civ-hero'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p></div>", unsafe_allow_html=True)

# Login panel
if 'auth_email' not in st.session_state:
    st.subheader('Member login')
    st.write('Use the email address already captured in the members table. The system sends an OTP or magic link through Supabase Auth.')
    email = st.text_input('Email address')
    col1,col2 = st.columns(2)
    with col1:
        if st.button('Send OTP / magic link') and email:
            send_otp(email.strip().lower())
    with col2:
        token = st.text_input('OTP code, if your email template sends a code')
        if st.button('Verify OTP') and email and token:
            if verify_otp(email.strip().lower(), token.strip()): st.rerun()
            else: st.error('OTP verification failed.')
    st.info('For pilot testing without Supabase Auth secrets, an administrator can temporarily use the fallback below.')
    with st.expander('Temporary pilot fallback'):
        fb_email = st.text_input('Fallback email in members table')
        if st.button('Continue as this member') and fb_email:
            st.session_state.auth_email = fb_email.strip().lower()
            st.session_state.auth_user_id = None
            st.rerun()
    st.stop()

member_id, user_email = member_id_from_user()
if member_id is None:
    st.error(f"The logged-in email {user_email} is not linked to an active member. Add this email in the members table or ask an administrator to update the member record.")
    if st.button('Logout'):
        st.session_state.clear(); st.rerun()
    st.stop()

member = df('select * from members where id=:id', {'id':member_id}).iloc[0]
roles = get_roles(member_id)
if 'active_role' not in st.session_state or st.session_state.active_role not in roles:
    st.session_state.active_role = roles[0]

c1,c2,c3 = st.columns([2,2,1])
with c1: st.write(f"Signed in as **{member['full_name']}**  ")
with c2: st.session_state.active_role = st.selectbox('Active role', roles, index=roles.index(st.session_state.active_role))
with c3:
    if st.button('Logout'):
        st.session_state.clear(); st.rerun()
active_role = st.session_state.active_role
admin = 'Administrator' in roles
menu = st.radio('Main menu', filtered_menu(active_role, roles), horizontal=True, label_visibility='collapsed')
st.caption('Access is filtered by assigned role. A member with several roles may switch only between assigned roles.')

# Dashboard
if menu == 'Dashboard':
    latest_nav = float(scalar("select nav from fund_valuations where status='Approved' order by valuation_date desc, id desc limit 1", default=0))
    total_contrib = float(scalar("select coalesce(sum(amount_paid),0) from contributions", default=0)) if admin else float(scalar("select coalesce(sum(amount_paid),0) from contributions where member_id=:m", {"m":member_id}, 0))
    total_returns = float(scalar("select coalesce(sum(amount),0) from investment_returns", default=0))
    roi = 0 if total_contrib == 0 else (total_returns/total_contrib)*100
    arrears = float(scalar("select coalesce(sum(arrears),0) from contributions", default=0)) if admin else float(scalar("select coalesce(sum(arrears),0) from contributions where member_id=:m", {"m":member_id}, 0))
    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric('Fund NAV', f"KES {latest_nav:,.2f}")
    k2.metric('My Value' if not admin else 'Member Values', f"KES {member_value(member_id):,.2f}" if not admin else f"KES {latest_nav:,.2f}")
    k3.metric('Contributions', f"KES {total_contrib:,.2f}")
    k4.metric('Returns ROI', f"{roi:,.2f}%")
    k5.metric('Arrears', f"KES {arrears:,.2f}")
    left,right = st.columns(2)
    with left:
        st.markdown('#### Contribution Growth')
        if admin:
            d = df("select contribution_month, coalesce(sum(amount_paid),0) contributions from contributions group by contribution_month order by contribution_month")
        else:
            d = df("select contribution_month, coalesce(sum(amount_paid),0) contributions from contributions where member_id=:m group by contribution_month order by contribution_month", {"m":member_id})
        if not d.empty:
            d['cumulative'] = d['contributions'].cumsum(); st.line_chart(d.set_index('contribution_month'))
        else: st.info('No contributions yet.')
    with right:
        st.markdown('#### Return Growth')
        r = df("select period, coalesce(sum(amount),0) returns from investment_returns group by period order by period")
        if not r.empty:
            r['cumulative'] = r['returns'].cumsum(); st.line_chart(r.set_index('period'))
        else: st.info('No returns recorded yet.')

elif menu == 'My Statement':
    st.header('My Statement')
    st.metric('Current member value', f"KES {member_value(member_id):,.2f}")
    st.subheader('My Contributions')
    st.dataframe(df('select * from contributions where member_id=:m order by created_at desc', {'m':member_id}), use_container_width=True, hide_index=True)
    st.subheader('My Units')
    st.dataframe(df('select * from member_units where member_id=:m order by created_at desc', {'m':member_id}), use_container_width=True, hide_index=True)
    st.subheader('My Loans')
    st.dataframe(df('select * from loans where member_id=:m order by created_at desc', {'m':member_id}), use_container_width=True, hide_index=True)

elif menu == 'Contributions':
    st.header('Contributions')
    can_all = active_role in ['Administrator','Secretary','Treasurer','Accountant'] or admin
    scope = member_options(can_all, member_id)
    tab1,tab2 = st.tabs(['Upload Payment Proof','Contribution Schedule'])
    with tab1:
        with st.form('payment_upload'):
            ml = st.selectbox('Member', list(scope.keys()))
            amount = st.number_input('Amount paid', min_value=0.0, step=500.0)
            month = st.text_input('Contribution month', value=date.today().strftime('%Y-%m'))
            method = st.selectbox('Payment method', ['M-Pesa','Bank Transfer','MMF Direct','Cash Deposit'])
            destination = st.selectbox('Destination', ['MMF Account','Bank Account'])
            ref = st.text_input('Transaction reference')
            if st.form_submit_button('Submit proof') and ref and amount>0:
                run("insert into payment_uploads(member_id, amount, contribution_month, payment_method, destination, transaction_ref, uploaded_by, created_at) values(:m,:a,:mo,:pm,:d,:r,:u,:n)", {"m":scope[ml],"a":amount,"mo":month,"pm":method,"d":destination,"r":ref,"u":member['full_name'],"n":datetime.now().isoformat()})
                log('Payment proof uploaded', ref, member['full_name']); st.success('Submitted.'); st.rerun()
        if can_all:
            st.subheader('Verification Queue')
            q = df("select p.id,m.full_name,p.amount,p.contribution_month,p.transaction_ref,p.uploaded_by,p.verified_by,p.status from payment_uploads p join members m on m.id=p.member_id where p.status in ('Submitted','Verified') order by p.id desc")
            st.dataframe(q, use_container_width=True, hide_index=True)
            pid = st.number_input('Payment ID', min_value=1, step=1)
            action = st.selectbox('Action', ['Verify','Approve and Post Receipt','Reject'])
            if st.button('Process payment'):
                p = df('select * from payment_uploads where id=:id', {'id':pid})
                if p.empty: st.error('Not found')
                else:
                    rec = p.iloc[0]
                    if action == 'Verify':
                        run("update payment_uploads set status='Verified', verified_by=:u where id=:id", {"u":member['full_name'],"id":pid}); st.success('Verified'); st.rerun()
                    elif action == 'Approve and Post Receipt':
                        if rec.get('verified_by') == member['full_name'] or rec.get('uploaded_by') == member['full_name']:
                            st.error('Maker/verifier cannot approve own transaction.')
                        else:
                            run("insert into contributions(member_id, contribution_month, expected_amount, amount_paid, arrears, receipt_ref, approved_by, created_at) values(:m,:mo,:e,:a,0,:r,:u,:n)", {"m":int(rec['member_id']),"mo":rec['contribution_month'],"e":float(rec['amount']),"a":float(rec['amount']),"r":rec['transaction_ref'],"u":member['full_name'],"n":datetime.now().isoformat()})
                            price = current_unit_price(); units = float(rec['amount'])/price if price else 0
                            run("insert into member_units(member_id,transaction_date,transaction_type,amount,unit_price,units,reference,created_at) values(:m,:d,'Contribution',:a,:p,:u,:r,:n)", {"m":int(rec['member_id']),"d":str(date.today()),"a":float(rec['amount']),"p":price,"u":units,"r":rec['transaction_ref'],"n":datetime.now().isoformat()})
                            run("update payment_uploads set status='Approved', approved_by=:u where id=:id", {"u":member['full_name'],"id":pid}); st.success('Posted'); st.rerun()
                    else:
                        run("update payment_uploads set status='Rejected', approved_by=:u where id=:id", {"u":member['full_name'],"id":pid}); st.warning('Rejected'); st.rerun()
    with tab2:
        if can_all:
            st.write('Upload contribution schedule with columns: member_code, schedule_month, expected_amount')
            f = st.file_uploader('Upload schedule Excel/CSV', type=['xlsx','csv'])
            if f:
                data = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                st.dataframe(data, use_container_width=True)
                if st.button('Import contribution schedule'):
                    imported=0
                    for _,row in data.iterrows():
                        mm = df('select id from members where member_code=:c', {'c':str(row.get('member_code',''))})
                        if mm.empty: continue
                        run("insert into contribution_schedules(member_id,schedule_month,expected_amount,source,created_at) values(:m,:mo,:a,'Upload',:n) on conflict(group_id, member_id, schedule_month) do update set expected_amount=excluded.expected_amount", {"m":int(mm.iloc[0,0]),"mo":str(row.get('schedule_month','')),"a":float(row.get('expected_amount',0) or 0),"n":datetime.now().isoformat()})
                        imported+=1
                    st.success(f'Imported {imported} schedule rows'); st.rerun()
        st.dataframe(df('select cs.*,m.full_name from contribution_schedules cs join members m on m.id=cs.member_id order by schedule_month,m.full_name'), use_container_width=True, hide_index=True)

elif menu == 'Investments':
    st.header('Investments')
    tab1,tab2,tab3 = st.tabs(['Register','Returns','Valuation'])
    with tab1:
        with st.form('investment'):
            asset = st.selectbox('Asset class',['Bank','MMF','Treasury Bond','Corporate Bond','Equity','REIT','Private Equity','Venture Capital','Special Fund','Other'])
            inst = st.text_input('Institution/Fund/Issuer'); desc=st.text_input('Description')
            cost=st.number_input('Cost', min_value=0.0, step=1000.0); val=st.number_input('Current value', min_value=0.0, step=1000.0)
            if st.form_submit_button('Save investment'):
                run('insert into investments(asset_class,institution,description,cost,current_value,created_at) values(:a,:i,:d,:c,:v,:n)', {"a":asset,"i":inst,"d":desc,"c":cost,"v":val,"n":datetime.now().isoformat()}); st.success('Saved'); st.rerun()
        st.dataframe(df('select * from investments order by id desc'), use_container_width=True, hide_index=True)
    with tab2:
        with st.form('return'):
            period=st.text_input('Period', value=date.today().strftime('%Y-%m')); rt=st.selectbox('Return type',['MMF Interest','Bond Coupon','Dividend','Fair Value Gain','Fair Value Loss','Loan Interest','Other']); amount=st.number_input('Amount', value=0.0, step=1000.0)
            if st.form_submit_button('Record return'):
                run('insert into investment_returns(period,return_type,asset_class,amount,created_at) values(:p,:t,:a,:m,:n)', {"p":period,"t":rt,"a":"","m":amount,"n":datetime.now().isoformat()}); st.success('Recorded'); st.rerun()
        st.dataframe(df('select * from investment_returns order by id desc'), use_container_width=True, hide_index=True)
    with tab3:
        inv=float(scalar('select coalesce(sum(current_value),0) from investments', default=0)); loans=float(scalar("select coalesce(sum(outstanding_principal),0) from loans where status in ('Approved','Active')", default=0))
        bank=st.number_input('Bank balance', min_value=0.0, step=1000.0); mmf=st.number_input('MMF balance', min_value=0.0, step=1000.0); liab=st.number_input('Liabilities', min_value=0.0, step=1000.0)
        nav=bank+mmf+inv+loans-liab; units=total_units(); price=100 if units==0 else nav/units
        st.metric('NAV', f'KES {nav:,.2f}'); st.metric('Unit price', f'KES {price:,.4f}')
        if st.button('Approve valuation'):
            run("insert into fund_valuations(valuation_date,bank_balance,mmf_balance,investment_value,loans_receivable,liabilities,nav,total_units,unit_price,status,created_at) values(:d,:b,:m,:i,:l,:li,:nav,:u,:p,'Approved',:n)", {"d":str(date.today()),"b":bank,"m":mmf,"i":inv,"l":loans,"li":liab,"nav":nav,"u":units,"p":price,"n":datetime.now().isoformat()}); st.success('Valuation approved'); st.rerun()

elif menu == 'Loans':
    st.header('Loans')
    can_all = active_role in ['Administrator','Treasurer','Accountant','Approver','Checker'] or admin
    opts=member_options(can_all, member_id)
    annual=st.number_input('Annual interest rate (%)', min_value=0.0, value=12.0, step=.5)/100; multiple=st.number_input('Loan multiple', min_value=1.0,value=3.0,step=.5)
    if opts:
        ml=st.selectbox('Borrower', list(opts.keys())); mid=opts[ml]; avail=member_value(mid); maxloan=avail*multiple
        st.info(f'Available value KES {avail:,.2f}; maximum at {multiple}x is KES {maxloan:,.2f}')
        amount=st.number_input('Loan amount', min_value=0.0, step=1000.0); months=st.number_input('Months', min_value=1,value=12,step=1)
        if st.button('Submit loan'):
            if amount>maxloan: st.error('Amount exceeds allowed multiple')
            else:
                mr=annual/12; pmt=amount/months if mr==0 else amount*mr/(1-(1+mr)**(-months))
                run("insert into loans(member_id,principal,annual_rate,months,outstanding_principal,monthly_payment,status,created_by,created_at) values(:m,:p,:r,:mo,:o,:pm,'Submitted',:u,:n)", {"m":mid,"p":amount,"r":annual,"mo":months,"o":amount,"pm":pmt,"u":member['full_name'],"n":datetime.now().isoformat()}); st.success('Submitted'); st.rerun()
    q = 'select l.*,m.full_name from loans l join members m on m.id=l.member_id order by l.id desc' if can_all else 'select l.*,m.full_name from loans l join members m on m.id=l.member_id where l.member_id=:m order by l.id desc'
    st.dataframe(df(q, {} if can_all else {"m":member_id}), use_container_width=True, hide_index=True)

elif menu == 'Withdrawals':
    st.header('Withdrawals')
    opts=member_options(admin, member_id)
    if opts:
        ml=st.selectbox('Member', list(opts.keys())); mid=opts[ml]
        out=float(scalar("select coalesce(sum(outstanding_principal),0) from loans where member_id=:m and status in ('Approved','Active')", {"m":mid}, 0)); val=member_value(mid); w=max(val-out,0)
        st.info(f'Member value KES {val:,.2f}; outstanding loan KES {out:,.2f}; withdrawable KES {w:,.2f}')
        amount=st.number_input('Withdrawal amount', min_value=0.0, step=1000.0)
        if st.button('Submit withdrawal'):
            if amount>w: st.error('Amount exceeds withdrawable balance')
            else:
                run("insert into withdrawals(member_id,amount,withdrawal_type,status,created_by,created_at) values(:m,:a,'Partial','Submitted',:u,:n)", {"m":mid,"a":amount,"u":member['full_name'],"n":datetime.now().isoformat()}); st.success('Submitted'); st.rerun()
    q='select w.*,m.full_name from withdrawals w join members m on m.id=w.member_id order by w.id desc' if admin else 'select w.*,m.full_name from withdrawals w join members m on m.id=w.member_id where w.member_id=:m order by w.id desc'
    st.dataframe(df(q, {} if admin else {"m":member_id}), use_container_width=True, hide_index=True)

elif menu == 'Meetings':
    st.header('Meetings & Hosting Cycle')
    can_manage = active_role in ['Administrator','Secretary','Organising Secretary','Chairperson'] or admin
    tab1,tab2,tab3 = st.tabs(['Calendar','Hosting Cycle','Attendance'])
    with tab1:
        if can_manage:
            with st.form('meeting'):
                mt=st.selectbox('Meeting type',['Monthly meeting','Investment committee meeting','Loan approval meeting','Special meeting','AGM','Emergency meeting'])
                title=st.text_input('Title'); d=st.date_input('Meeting date'); venue=st.text_input('Venue')
                opts=member_options(True); host_label=st.selectbox('Host', ['None']+list(opts.keys()))
                host=None if host_label=='None' else opts[host_label]
                if st.form_submit_button('Create meeting'):
                    run('insert into meetings(meeting_type,meeting_title,meeting_date,venue,host_member_id,created_by,created_at) values(:mt,:t,:d,:v,:h,:u,:n)', {"mt":mt,"t":title,"d":str(d),"v":venue,"h":host,"u":member['full_name'],"n":datetime.now().isoformat()}); st.success('Meeting created'); st.rerun()
        st.dataframe(df('select me.*,m.full_name host_name from meetings me left join members m on m.id=me.host_member_id order by meeting_date desc'), use_container_width=True, hide_index=True)
    with tab2:
        if can_manage:
            if st.button('Create new hosting cycle from active members'):
                run("insert into meeting_cycles(cycle_name,start_date,status,created_at) values(:n,:d,'Active',:now)", {"n":f"Cycle {date.today()}","d":str(date.today()),"now":datetime.now().isoformat()})
                cid=int(scalar('select id from meeting_cycles order by id desc limit 1'))
                members=df("select id from members where status='Active' order by id")
                for i,row in members.iterrows():
                    run('insert into meeting_cycle_hosts(cycle_id,member_id,host_order,created_at) values(:c,:m,:o,:n)', {"c":cid,"m":int(row['id']),"o":int(i+1),"n":datetime.now().isoformat()})
                st.success('Hosting cycle created'); st.rerun()
        st.dataframe(df('select h.*,c.cycle_name,m.full_name from meeting_cycle_hosts h join meeting_cycles c on c.id=h.cycle_id join members m on m.id=h.member_id order by c.id,h.host_order'), use_container_width=True, hide_index=True)
    with tab3:
        st.dataframe(df('select * from meeting_attendance order by id desc'), use_container_width=True, hide_index=True)

elif menu == 'Financial Schedules':
    st.header('Financial Schedules')
    schedule_types=['Member contribution schedule','Member arrears schedule','Member units schedule','Member fund value schedule','Loan balance schedule','Guarantee exposure schedule','Investment register','Investment income schedule','Bond amortisation schedule','Cashbook','Trial balance','General ledger','Statement of financial position','Statement of changes in member funds','AGM cost schedule','Role assignment history']
    with st.form('schedule'):
        stype=st.selectbox('Schedule type', schedule_types); ps=st.date_input('Period start'); pe=st.date_input('Period end'); notes=st.text_area('Notes')
        if st.form_submit_button('Create schedule task'):
            run("insert into financial_schedules(schedule_type,period_start,period_end,prepared_by,status,notes,created_at) values(:s,:ps,:pe,:p,'Pending',:notes,:n)", {"s":stype,"ps":str(ps),"pe":str(pe),"p":member['full_name'],"notes":notes,"n":datetime.now().isoformat()}); st.success('Schedule task created'); st.rerun()
    st.dataframe(df('select * from financial_schedules order by id desc'), use_container_width=True, hide_index=True)

elif menu == 'Governance':
    st.header('Governance & Roles')
    tab1,tab2 = st.tabs(['Assign Roles','Role History'])
    with tab1:
        mopts=member_options(True); roles_df=df("select id,role_name from roles where status='Active' order by role_name"); ropts={r.role_name:int(r.id) for _,r in roles_df.iterrows()}
        with st.form('assign_role'):
            ml=st.selectbox('Member', list(mopts.keys())); rl=st.selectbox('Role', list(ropts.keys())); reason=st.selectbox('Reason',['Elected at AGM','Temporary delegation','Incapacitation','Resignation replacement','Term expiry','Other']); remarks=st.text_area('Remarks')
            if st.form_submit_button('Assign role'):
                run("insert into member_roles(member_id,role_id,start_date,status,assigned_by,assignment_reason,remarks,created_at) values(:m,:r,current_date,'Active',:u,:reason,:remarks,:n) on conflict do nothing", {"m":mopts[ml],"r":ropts[rl],"u":member['full_name'],"reason":reason,"remarks":remarks,"n":datetime.now().isoformat()}); st.success('Role assigned'); st.rerun()
        st.write('To end a role, set status to Ended in Supabase for now. The next build can add an end-role button.')
    with tab2:
        st.dataframe(df('select mr.*,m.full_name,r.role_name from member_roles mr join members m on m.id=mr.member_id join roles r on r.id=mr.role_id order by mr.created_at desc'), use_container_width=True, hide_index=True)

elif menu == 'AGM & Compliance':
    st.header('AGM & Compliance')
    tab1,tab2=st.tabs(['AGM','Registration & KRA'])
    with tab1:
        with st.form('agm'):
            year=st.number_input('AGM year', min_value=2024, value=date.today().year, step=1); venue=st.text_input('Venue'); budget=st.number_input('Budgeted cost', min_value=0.0, step=1000.0); actual=st.number_input('Actual cost', min_value=0.0, step=1000.0); add=st.number_input('Additional contribution required', min_value=0.0, step=1000.0)
            if st.form_submit_button('Save AGM record'):
                run("insert into agm_records(agm_year,venue,budgeted_cost,actual_cost,additional_contribution_required,status,created_at) values(:y,:v,:b,:a,:ad,'Planned',:n) on conflict(group_id,agm_year) do update set venue=excluded.venue,budgeted_cost=excluded.budgeted_cost,actual_cost=excluded.actual_cost,additional_contribution_required=excluded.additional_contribution_required", {"y":int(year),"v":venue,"b":budget,"a":actual,"ad":add,"n":datetime.now().isoformat()}); st.success('AGM saved'); st.rerun()
        st.dataframe(df('select * from agm_records order by agm_year desc'), use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(df('select * from group_compliance order by id desc'), use_container_width=True, hide_index=True)

elif menu == 'Admin':
    st.header('Admin')
    for table in ['members','roles','member_roles','groups','payment_uploads','contributions','member_units','investments','investment_returns','loans','withdrawals','meetings','meeting_cycles','meeting_cycle_hosts','agm_records','financial_schedules','group_compliance','audit_logs']:
        with st.expander(table):
            try: st.dataframe(df(f'select * from {table} order by id desc'), use_container_width=True, hide_index=True)
            except Exception as e: st.warning(str(e))
