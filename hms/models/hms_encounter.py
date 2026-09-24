from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HmsEncounter(models.Model):
    _name = "hms.encounter"
    _description = "Clinical Encounter"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    patient_id = fields.Many2one("hms.patient", required=True, tracking=True, index=True)
    appointment_id = fields.Many2one("hms.appointment", ondelete="set null")
    practitioner_id = fields.Many2one("hms.practitioner", required=True, tracking=True)
    department_id = fields.Many2one("hms.department")
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        group_expand="_expand_states",
    )

    chief_complaint = fields.Text(string="Chief complaint")
    temperature = fields.Float(string="Temperature (°C)")
    heart_rate = fields.Integer(string="Heart rate (bpm)")
    bp_systolic = fields.Integer(string="BP systolic")
    bp_diastolic = fields.Integer(string="BP diastolic")
    respiratory_rate = fields.Integer(string="Respiratory rate (/min)")
    spo2 = fields.Integer(string="SpO2 (%)")
    weight = fields.Float(string="Weight (kg)")
    height = fields.Float(string="Height (cm)")
    bmi = fields.Float(string="BMI", compute="_compute_bmi", digits=(12, 1))
    diagnosis_ids = fields.Many2many("hms.diagnosis", string="Diagnoses")
    followup_date = fields.Date(string="Follow-up date")
    notes = fields.Text(string="Clinical notes")
    treatment_plan = fields.Text()

    prescription_ids = fields.One2many("hms.prescription", "encounter_id", string="Prescriptions")
    prescription_count = fields.Integer(compute="_compute_prescription_count")
    invoice_id = fields.Many2one("account.move", readonly=True, copy=False)
    invoice_count = fields.Integer(compute="_compute_invoice_count")
    user_id = fields.Many2one(
        "res.users",
        string="Practitioner user",
        related="practitioner_id.user_id",
        store=True,
    )

    @api.model
    def _expand_states(self, states, domain, order):
        return [key for key, _label in self._fields["state"].selection]

    @api.depends("weight", "height")
    def _compute_bmi(self):
        for enc in self:
            height_m = enc.height / 100.0
            enc.bmi = enc.weight / (height_m ** 2) if enc.weight and height_m else 0.0

    @api.depends("prescription_ids")
    def _compute_prescription_count(self):
        for enc in self:
            enc.prescription_count = len(enc.prescription_ids)

    @api.depends("invoice_id")
    def _compute_invoice_count(self):
        for enc in self:
            enc.invoice_count = 1 if enc.invoice_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("hms.encounter") or "New"
                )
        return super().create(vals_list)

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_schedule_followup(self):
        self.ensure_one()
        if not self.followup_date:
            raise UserError(_("Set a follow-up date before scheduling an appointment."))
        appointment = self.env["hms.appointment"].create(
            {
                "patient_id": self.patient_id.id,
                "practitioner_id": self.practitioner_id.id,
                "department_id": self.department_id.id,
                "date_start": fields.Datetime.to_datetime(self.followup_date),
                "reason": _("Follow-up for encounter %(name)s", name=self.name),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Follow-up Appointment",
            "res_model": "hms.appointment",
            "res_id": appointment.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_new_prescription(self):
        self.ensure_one()
        prescription = self.env["hms.prescription"].create(
            {
                "patient_id": self.patient_id.id,
                "encounter_id": self.id,
                "practitioner_id": self.practitioner_id.id,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Prescription",
            "res_model": "hms.prescription",
            "res_id": prescription.id,
            "view_mode": "form",
            "target": "current",
        }

    def _prepare_invoice_lines(self):
        """Return invoice line dicts for this encounter: consultation fee + drugs."""
        self.ensure_one()
        lines = []
        consultation_product = self.env.ref(
            "hms.product_consultation", raise_if_not_found=False
        )
        fee = self.practitioner_id.consultation_fee
        if consultation_product and fee:
            lines.append(
                {
                    "product_id": consultation_product.id,
                    "quantity": 1,
                    "price_unit": fee,
                    "name": _("Consultation - %(name)s", name=self.practitioner_id.name),
                }
            )
        for prescription in self.prescription_ids.filtered(
            lambda p: p.state in ("confirmed", "dispensed")
        ):
            for line in prescription.line_ids:
                lines.append(
                    {
                        "product_id": line.product_id.id,
                        "quantity": line.quantity,
                        "price_unit": line.product_id.list_price,
                        "name": line.product_id.display_name,
                    }
                )
        return lines

    def action_create_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            raise UserError(_("An invoice already exists for this encounter."))
        partner = self.patient_id.partner_id
        if not partner:
            partner = self.env["res.partner"].create(
                {
                    "name": self.patient_id.name,
                    "phone": self.patient_id.phone,
                    "email": self.patient_id.email,
                    "street": self.patient_id.street,
                    "city": self.patient_id.city,
                }
            )
            self.patient_id.partner_id = partner.id
        invoice_lines = self._prepare_invoice_lines()
        if not invoice_lines:
            raise UserError(_("Nothing to invoice on this encounter."))
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.context_today(self),
                "invoice_line_ids": [(0, 0, line) for line in invoice_lines],
            }
        )
        self.invoice_id = move.id
        return self.action_view_invoice()

    def action_view_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Invoice",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }
