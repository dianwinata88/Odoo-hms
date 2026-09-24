from odoo import fields, models


class HmsDepartment(models.Model):
    _name = "hms.department"
    _description = "Hospital Department"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(help="Short code, e.g. CARD for Cardiology.")
    active = fields.Boolean(default=True)
    parent_id = fields.Many2one(
        "hms.department",
        string="Parent department",
        ondelete="restrict",
    )
    child_ids = fields.One2many("hms.department", "parent_id", string="Sub-departments")
    practitioner_ids = fields.One2many("hms.practitioner", "department_id", string="Practitioners")
    description = fields.Text()
