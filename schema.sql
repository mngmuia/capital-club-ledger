-- Capital Club Ledger simplified Supabase/PostgreSQL schema reference
-- The Streamlit MVP also auto-creates compatible tables where possible.

create table if not exists groups (
  id bigserial primary key,
  name text not null,
  base_currency text default 'KES',
  opening_unit_price numeric default 100,
  created_at timestamptz default now()
);

create table if not exists members (
  id bigserial primary key,
  group_id bigint references groups(id),
  member_code text,
  full_name text not null,
  phone text,
  email text,
  status text default 'Active',
  join_date date,
  created_at timestamptz default now()
);

create table if not exists payment_uploads (
  id bigserial primary key,
  group_id bigint references groups(id),
  member_id bigint references members(id),
  amount numeric not null,
  contribution_month text,
  payment_method text,
  destination text,
  transaction_ref text unique,
  uploaded_by text,
  status text default 'Submitted',
  verified_by text,
  approved_by text,
  created_at timestamptz default now()
);

create table if not exists contributions (
  id bigserial primary key,
  group_id bigint references groups(id),
  member_id bigint references members(id),
  contribution_month text,
  expected_amount numeric default 0,
  amount_paid numeric not null,
  arrears numeric default 0,
  receipt_ref text unique,
  approved_by text,
  created_at timestamptz default now()
);

create table if not exists member_units (
  id bigserial primary key,
  group_id bigint references groups(id),
  member_id bigint references members(id),
  transaction_date date,
  transaction_type text,
  amount numeric,
  unit_price numeric,
  units numeric,
  reference text,
  created_at timestamptz default now()
);

create table if not exists investments (
  id bigserial primary key,
  group_id bigint references groups(id),
  asset_class text,
  institution text,
  description text,
  cost numeric,
  current_value numeric,
  status text default 'Active',
  created_at timestamptz default now()
);

create table if not exists investment_returns (
  id bigserial primary key,
  group_id bigint references groups(id),
  period text,
  return_type text,
  asset_class text,
  amount numeric,
  status text default 'Approved',
  created_at timestamptz default now()
);

create table if not exists loans (
  id bigserial primary key,
  group_id bigint references groups(id),
  member_id bigint references members(id),
  principal numeric,
  annual_rate numeric,
  months integer,
  outstanding_principal numeric,
  monthly_payment numeric,
  status text default 'Submitted',
  created_by text,
  approved_by text,
  created_at timestamptz default now()
);

create table if not exists loan_guarantees (
  id bigserial primary key,
  group_id bigint references groups(id),
  loan_id bigint references loans(id),
  guarantor_member_id bigint references members(id),
  guarantee_amount numeric,
  status text default 'Pending',
  created_at timestamptz default now()
);

create table if not exists withdrawals (
  id bigserial primary key,
  group_id bigint references groups(id),
  member_id bigint references members(id),
  amount numeric,
  withdrawal_type text,
  status text default 'Submitted',
  created_by text,
  approved_by text,
  created_at timestamptz default now()
);

create table if not exists fund_valuations (
  id bigserial primary key,
  group_id bigint references groups(id),
  valuation_date date,
  bank_balance numeric default 0,
  mmf_balance numeric default 0,
  investment_value numeric default 0,
  loans_receivable numeric default 0,
  liabilities numeric default 0,
  nav numeric,
  total_units numeric,
  unit_price numeric,
  status text default 'Approved',
  created_at timestamptz default now()
);

create table if not exists audit_logs (
  id bigserial primary key,
  group_id bigint references groups(id),
  action text,
  details text,
  user_name text,
  created_at timestamptz default now()
);
