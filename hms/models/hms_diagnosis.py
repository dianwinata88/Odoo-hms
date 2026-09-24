from odoo import api, fields, models


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

    @api.depends("code", "name")
    def _compute_display_name(self):
        for diagnosis in self:
            diagnosis.display_name = f"[{diagnosis.code}] {diagnosis.name}"
