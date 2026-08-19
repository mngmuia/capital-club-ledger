# Capital Club Ledger MVP

Capital Club Ledger is a Streamlit MVP for a private investment group. It supports members, historical onboarding, payment upload, secretary/checker receipting, unitisation, fund valuation, loans on reducing balance, withdrawals, investments and reports.

## Files

- `app.py` - Streamlit app
- `requirements.txt` - Python dependencies
- `schema.sql` - PostgreSQL/Supabase schema reference
- `.streamlit/secrets.toml.example` - example secrets file
- `sample_data/sample_members.xlsx` - sample member upload
- `sample_data/sample_contributions.xlsx` - sample contribution upload

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

By default, the app uses local SQLite: `capital_club_ledger.db`.

## Use Supabase/PostgreSQL for free online persistence

1. Create a Supabase project.
2. Open SQL Editor and run `schema.sql` if you want to create tables manually.
3. Copy the project database connection string.
4. In Streamlit Community Cloud, add a secret named `DATABASE_URL`.

Example `.streamlit/secrets.toml`:

```toml
DATABASE_URL = "postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres"
```

## Publish free on Streamlit Community Cloud

1. Create a GitHub repository, for example `capital-club-ledger`.
2. Upload all files in this folder to the repository.
3. Go to Streamlit Community Cloud and create a new app.
4. Select your GitHub repository, branch and `app.py` as the entry file.
5. Add `DATABASE_URL` under advanced settings/secrets if using Supabase.
6. Deploy the app.

## Production cautions

This is an MVP. Before using it for serious money operations, add:

- Proper authentication
- Supabase Row Level Security
- Document upload storage
- Database backups
- Stronger approval workflows
- Regulatory/legal review if lending expands beyond a private group
