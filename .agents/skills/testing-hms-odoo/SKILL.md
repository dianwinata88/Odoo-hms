---
name: testing-hms-odoo
description: How to set up and end-to-end test the hms Hospital Management addon on a local Odoo 18 dev DB (groups, record rules, accounting fixture, known environment pitfalls)
---

# Testing the `hms` addon on Odoo 18 (local dev DB)

## Starting the server
```
cd /home/ubuntu/odoo && /home/ubuntu/odoo-venv/bin/python odoo-bin -d odoodb \
  --addons-path=/home/ubuntu/odoo/addons,/home/ubuntu/repos/Odoo-hms \
  --db_host=localhost --db_user=odoo --db_password=odoo
```
Then http://localhost:8069, login admin/admin. Log tail: run with `> /tmp/odoo.log 2>&1`.
When restarting, kill the werkzeug worker pid (from `pgrep -af odoo-bin`), not just the nohup wrapper — a zombie worker keeps the old registry/views cached on :8069.

## Access / groups (required for full menu visibility)
- Pharmacy, Billing and Configuration menus need `hms.group_hms_manager` (or pharmacist/billing). Grant admin via SQL:
  `insert into res_groups_users_rel (uid,gid) select 2,<gid> ...` (find gid via ir_model_data where module='hms').
- WARNING: being in `group_hms_practitioner` activates record rules `('user_id','=',user.id)` on appointment/encounter/prescription — records become INVISIBLE unless the practitioner is linked to an `hr.employee` whose `user_id` is the test user. Create the practitioner with Employee = "Administrator" (auto-created employee for admin user_id=2).
- The "Billing" top menu has no child menu items (nothing defined in the module), so it never renders — billing is reached only via the encounter "Create invoice" button / Invoices stat button.

## Accounting fixture needed for "Create invoice" (empty dev DB)
A fresh odoodb has NO chart of accounts — `action_create_invoice` fails with "No journal could be found ... types: sale". Mirror the fixture in `hms/tests/test_hms.py` setUpClass via `odoo-bin shell` piped stdin:
- create `account.account` income/asset_receivable/liability_payable
- create `account.journal` type=sale with default_account_id=income
- set `property_account_receivable_id`/`property_account_payable_id` directly on the patient's `res.partner` (company_dependent fields — `ir.property` model does NOT exist in Odoo 18; write the field on the partner record via ORM) and link `hms_patient.partner_id`.

## Known environment pitfall: stale views after module uninstall
If the invoice form crashes with `OwlError: "account.move"."authorized_transaction_ids" field is undefined`, a leftover extension view from an uninstalled module (e.g. `account_payment.account_invoice_view_form_inherit_payment`) is still active in ir_ui_view. Find it with
`select id,active from ir_ui_view where arch_db::text like '%authorized_transaction_ids%';`
and set `active=false`, then restart the server (combined-view cache isn't invalidated by direct SQL).

## UI interaction quirks
- Do NOT press Ctrl+S to save Odoo forms — Chrome opens Save File dialog. Click the "Save manually" (cloud) icon in the control panel, or just navigate away (autosave).
- many2many_tags inputs (e.g. encounter Diagnoses) render nearly invisible when empty — click the field below the "Assessment" separator or Tab into it from the last vitals field, then type. `hms.diagnosis` has no menu/views: create via "Create and edit..." (code is required — plain "Create" name_create fails on NOT NULL).
- Prescription line product domain is `type='consu'`; quick "Create 'X'" works because product.template defaults type to consu.
- Dispense wizard Location defaults to `WH/Stock/Pharmacy` (hms.stock_location_pharmacy); picking is force-validated (`move.quantity = product_uom_qty`) so no stock levels needed.
- "Create invoice" button only appears once the encounter state is Done.

## Devin Secrets Needed
None — local postgres credentials are plain (odoo/odoo@localhost:5432, db odoodb).
