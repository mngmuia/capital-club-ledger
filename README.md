# Committee Investment Vehicle v2

This package adds:
- Supabase Auth OTP/magic link login option
- Member to auth email mapping
- Role assignment and role switching
- Member-only and admin-level filtering
- Meetings and member hosting cycle
- AGM and compliance readiness
- Accountant financial schedules
- Contribution schedule upload

## Required Streamlit secrets

```toml
DATABASE_URL = "postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres"
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY"
```

## Supabase steps

1. Run `sql/committee_investment_vehicle_v2_migration.sql` in Supabase SQL Editor.
2. Configure Supabase Auth email provider.
3. Add the above secrets to Streamlit Cloud.
4. Reboot the Streamlit app.
5. Members should log in using the same email already stored in the `members` table.

## Important

The migration creates broad pilot RLS policies for authenticated users. Replace them with strict `auth.uid()` and `group_id` policies before live use with real money.
