# Committee Investment Vehicle v3

Changes:
- Dynamic menu is based on the active role only.
- Administrator role shows administrator menus; Member role shows member-only menus.
- Member views filter strictly to the logged-in member.
- Dashboard cards have a selector to show the makeup of each amount.
- Member value falls back to actual paid contributions when historical contributions are imported but units/valuation have not yet been created.

Deploy:
1. Replace app.py and requirements.txt in GitHub.
2. Keep Streamlit secrets as DATABASE_URL, SUPABASE_URL and SUPABASE_ANON_KEY.
3. Redeploy or reboot the Streamlit app.
