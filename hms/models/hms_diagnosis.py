from odoo import fields, models


class HmsDiagnosis(models.Model):
    _name = "hms.diagnosis"
    _description = "Diagnosis Catalog"
    _order = "code, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Diagnostic code, e.g. ICD-10.")
    description = fields.Text()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "The diagnosis code must be unique."),
    ]

    def name_get(self):
        return [(d.id, f"[{d.code}] {d.name}") for d in self]
