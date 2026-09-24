# Odoo HMS — Hospital Management System

A Hospital Management System built as a custom addon for **Odoo 18 Community**.
Pure addon architecture — no Odoo core modifications.

## Module

`hms/` — the addon. Covers the outpatient journey:

| Context | Models |
|---|---|
| Hospital core | `hms.department`, `hms.practitioner` |
| Patient registry | `hms.patient` (MRN sequences, allergies, linked `res.partner`) |
| Appointments | `hms.appointment` (calendar/kanban, state flow, overlap check) |
| Encounters | `hms.encounter` (vitals, diagnoses, treatment plan) |
| Prescriptions | `hms.prescription` + lines, dispense wizard → `stock.picking` |
| Billing | Encounter → `account.move` invoice (consultation fee + drugs) |

## Install

```bash
# addons path must include this repo root
./odoo-bin -d hmsdb --addons-path=addons,/path/to/Odoo-hms -i hms
```

## Security groups

Receptionist → Practitioner → Pharmacist / Billing → Manager (cumulative).
Practitioners are limited to their own appointments, encounters and
prescriptions via record rules.

## Layout

```
hms/
├── models/      business objects
├── views/       form / list / kanban / calendar / search
├── wizard/      dispense wizard
├── report/      QWeb prescription PDF
├── security/    groups, ir.model.access.csv, record rules
├── data/        sequences, pharmacy location, consultation product
└── tests/       TransactionCase suite
```
