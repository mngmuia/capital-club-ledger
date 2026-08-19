# ChamaYetu V4 - Loans Method B Manual Reference Verification

This version replaces the direct Loans entry screen with a role-based Loans workspace and supports Method B manual repayment verification until Paybill/API integration is available.

## Files

- `app.py` - complete Streamlit application
- `database_update_method_b.sql` - Supabase SQL update script
- `requirements.txt` - Python dependencies
- `.streamlit/secrets.toml.example` - sample Streamlit secrets file

## Setup

1. Upload these files to GitHub.
2. Create `.streamlit/secrets.toml` in Streamlit Cloud or locally.
3. Add your Supabase URL and anon key.
4. Run `database_update_method_b.sql` in Supabase SQL Editor.
5. Create a Supabase Storage bucket named `loan-documents`.
6. Deploy the app using Streamlit Community Cloud.

## Roles Supported

- Member: own loans, entitlement, guaranteed loans, repayment reference upload, loan application
- Approver: check and approve loans with maker-checker control
- Accountant/Treasurer: liquidation, bank transfer, repayment verification
- Admin/Chairperson/Auditor/Secretary: loan book, repayment schedules, references and summaries

## Important Security Note

Do not commit `.streamlit/secrets.toml` to GitHub. If any database password was previously shared, rotate it in Supabase before publishing.
