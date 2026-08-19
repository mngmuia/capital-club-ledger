
# ChamaYetu Working App

This zip contains a recovery-safe Streamlit app for ChamaYetu.

## What is included

- `app.py` - working Streamlit app
- `requirements.txt` - packages for Streamlit Cloud
- `.streamlit/secrets.toml.example` - template for Supabase connection
- `database/migration_chamayetu_baseline.sql` - safe bigint baseline SQL
- `database/diagnostics.sql` - checks whether key tables and rows exist

## Recommended order

1. In Supabase SQL Editor, run:
   `database/migration_chamayetu_baseline.sql`

2. In Streamlit Cloud, set secrets:

```toml
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_ANON_KEY = "your_supabase_anon_key"
```

3. Deploy with:

```bash
streamlit run app.py
```

## Important notes

- The app no longer crashes when members are missing. It opens in demo mode if Supabase is not configured or is blocked by RLS.
- The schema uses `bigint` IDs consistently for members, contributions, loans and schedules.
- `auth_user_id` remains `uuid` because Supabase Auth uses UUIDs.
- No destructive `drop table`, `truncate`, or `delete` statements are included.

## Initial login

Use:

- `M001 - Peter Muia`

M001 has the Administrator role in the baseline SQL.
