# Committee Investment Vehicle

A Streamlit MVP for an investment committee or private investment group. It supports onboarding, member contributions, M-Pesa/bank payment upload, maker-checker receipting, fund valuation, investment returns, loans, withdrawals and dashboard BI.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publish free on Streamlit Community Cloud

1. Upload these files to your GitHub repository.
2. Go to Streamlit Community Cloud.
3. Create a new app.
4. Select your GitHub repository, branch and `app.py`.
5. Deploy.

## Optional Supabase setup

The app works locally or on Streamlit using SQLite for testing. For persistent online use, create a Supabase project and add this in Streamlit secrets:

```toml
DATABASE_URL = "postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres"
```

Before live use with real money, add proper authentication, Supabase Row Level Security, document storage, backups and stronger approval workflows.
