{
    "name": "Hospital Management System",
    "version": "18.0.1.0.0",
    "category": "Healthcare",
    "summary": "Patients, appointments, encounters, prescriptions, pharmacy and billing",
    "description": """
Hospital Management System for Odoo Community.

Covers the outpatient journey: patient registry, appointment scheduling,
clinical encounters with vitals and diagnoses, prescriptions with pharmacy
dispensing, and invoicing via account.
""",
    "author": "dianwinata88",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "hr",
        "product",
        "stock",
        "account",
    ],
    "data": [
        "security/hms_security.xml",
        "security/ir.model.access.csv",
        "data/hms_sequences.xml",
        "data/hms_data.xml",
        "data/hms_diagnosis_data.xml",
        "views/hms_menus.xml",
        "views/hms_department_views.xml",
        "views/hms_practitioner_views.xml",
        "views/hms_diagnosis_views.xml",
        "views/hms_patient_views.xml",
        "views/hms_appointment_views.xml",
        "views/hms_encounter_views.xml",
        "views/hms_prescription_views.xml",
        "wizard/hms_dispense_wizard_views.xml",
        "report/hms_reports.xml",
    ],
    "demo": [
        "data/hms_demo.xml",
        "data/hms_appointment_demo.xml",
        "data/hms_pharmacy_demo.xml",
    ],
    "application": True,
    "installable": True,
}
