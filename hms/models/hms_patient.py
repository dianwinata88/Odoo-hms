from odoo import api, fields, models


class HmsPatient(models.Model):
    _name = "hms.patient"
    _description = "Patient"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    title = fields.Selection(
        [("mr", "Mr."), ("mrs", "Mrs."), ("ms", "Ms.")],
    )
    identification_number = fields.Char(
        string="National ID",
        index=True,
        copy=False,
    )
    mrn = fields.Char(
        string="Medical record no.",
        readonly=True,
        copy=False,
        index=True,
        default="New",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        help="Partner used for invoicing and contact details.",
        ondelete="restrict",
    )
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        tracking=True,
    )
    birth_date = fields.Date(tracking=True)
    age = fields.Integer(compute="_compute_age", store=True)
    blood_type = fields.Selection(
        [
            ("a+", "A+"), ("a-", "A-"),
            ("b+", "B+"), ("b-", "B-"),
            ("ab+", "AB+"), ("ab-", "AB-"),
            ("o+", "O+"), ("o-", "O-"),
        ],
    )
    phone = fields.Char()
    email = fields.Char()
    street = fields.Char()
    city = fields.Char()
    emergency_contact_name = fields.Char(string="Emergency contact")
    emergency_contact_phone = fields.Char(string="Emergency phone")
    allergies = fields.Text()
    chronic_conditions = fields.Text(string="Chronic conditions")
    notes = fields.Text()
    active = fields.Boolean(default=True)
    image_1920 = fields.Image("Photo", max_width=1920, max_height=1920)

    appointment_ids = fields.One2many("hms.appointment", "patient_id", string="Appointments")
    encounter_ids = fields.One2many("hms.encounter", "patient_id", string="Encounters")
    prescription_ids = fields.One2many("hms.prescription", "patient_id", string="Prescriptions")

    appointment_count = fields.Integer(compute="_compute_counts")
    encounter_count = fields.Integer(compute="_compute_counts")
    prescription_count = fields.Integer(compute="_compute_counts")

    _sql_constraints = [
        ("mrn_unique", "unique(mrn)", "The medical record number must be unique."),
    ]

    @api.depends("birth_date")
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for patient in self:
            if patient.birth_date:
                born = patient.birth_date
                patient.age = (
                    today.year
                    - born.year
                    - ((today.month, today.day) < (born.month, born.day))
                )
            else:
                patient.age = 0

    @api.depends("appointment_ids", "encounter_ids", "prescription_ids")
    def _compute_counts(self):
        for patient in self:
            patient.appointment_count = len(patient.appointment_ids)
            patient.encounter_count = len(patient.encounter_ids)
            patient.prescription_count = len(patient.prescription_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("mrn") or vals["mrn"] == "New":
                vals["mrn"] = self.env["ir.sequence"].next_by_code("hms.patient") or "New"
        return super().create(vals_list)

    def action_view_appointments(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Appointments",
            "res_model": "hms.appointment",
            "view_mode": "list,form,calendar",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }

    def action_view_encounters(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Encounters",
            "res_model": "hms.encounter",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }

    def action_view_prescriptions(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Prescriptions",
            "res_model": "hms.prescription",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }
