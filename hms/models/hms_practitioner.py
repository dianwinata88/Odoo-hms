from odoo import fields, models


class HmsPractitioner(models.Model):
    _name = "hms.practitioner"
    _description = "Medical Practitioner"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        help="HR record backing this practitioner.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Related user",
        related="employee_id.user_id",
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one("hms.department", required=True, tracking=True)
    role = fields.Selection(
        [
            ("doctor", "Doctor"),
            ("nurse", "Nurse"),
            ("other", "Other staff"),
        ],
        default="doctor",
        required=True,
    )
    specialization = fields.Char()
    license_number = fields.Char()
    consultation_fee = fields.Monetary(currency_field="currency_id", default=0.0)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(default=True)
    image_1920 = fields.Image("Photo", max_width=1920, max_height=1920)
