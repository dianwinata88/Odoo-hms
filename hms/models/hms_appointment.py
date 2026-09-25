from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HmsAppointment(models.Model):
    _name = "hms.appointment"
    _description = "Appointment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    patient_id = fields.Many2one("hms.patient", required=True, tracking=True, index=True)
    practitioner_id = fields.Many2one(
        "hms.practitioner",
        required=True,
        tracking=True,
        index=True,
        domain="[('role', '=', 'doctor'), ('department_id', '=', department_id)]",
    )
    department_id = fields.Many2one("hms.department", tracking=True)
    date_start = fields.Datetime(required=True, tracking=True, default=fields.Datetime.now)
    date_end = fields.Datetime(compute="_compute_date_end", store=True)
    duration_minutes = fields.Integer(default=30, required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("checkin", "Checked in"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        group_expand="_expand_states",
    )
    reason = fields.Text(string="Reason for visit")
    notes = fields.Text()
    encounter_id = fields.Many2one("hms.encounter", readonly=True, copy=False)
    user_id = fields.Many2one(
        "res.users",
        string="Practitioner user",
        related="practitioner_id.user_id",
        store=True,
    )

    @api.depends("date_start", "duration_minutes")
    def _compute_date_end(self):
        for appt in self:
            if appt.date_start and appt.duration_minutes:
                appt.date_end = fields.Datetime.add(
                    appt.date_start, minutes=appt.duration_minutes
                )
            else:
                appt.date_end = appt.date_start

    @api.model
    def _expand_states(self, states, domain, order):
        return [key for key, _label in self._fields["state"].selection]

    @api.constrains("date_start", "duration_minutes", "practitioner_id", "state")
    def _check_practitioner_overlap(self):
        for appt in self.filtered(lambda a: a.state not in ("cancel",) and a.date_start and a.date_end):
            overlap = self.search(
                [
                    ("id", "!=", appt.id),
                    ("practitioner_id", "=", appt.practitioner_id.id),
                    ("state", "not in", ("cancel",)),
                    ("date_start", "<", appt.date_end),
                    ("date_end", ">", appt.date_start),
                ],
                limit=1,
            )
            if overlap:
                raise ValidationError(
                    _(
                        "%(name)s already has an appointment overlapping this time slot.",
                        name=appt.practitioner_id.name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("hms.appointment") or "New"
                )
        return super().create(vals_list)

    def _check_transition(self, allowed_states, target_state):
        for appt in self:
            if appt.state not in allowed_states:
                raise UserError(
                    _(
                        "Appointment %(name)s cannot be moved from %(state)s to %(target)s.",
                        name=appt.name,
                        state=dict(self._fields["state"].selection).get(appt.state),
                        target=dict(self._fields["state"].selection).get(target_state),
                    )
                )

    def action_confirm(self):
        self._check_transition(("draft",), "confirmed")
        self.write({"state": "confirmed"})

    def action_checkin(self):
        self._check_transition(("confirmed",), "checkin")
        self.write({"state": "checkin"})

    def action_done(self):
        self._check_transition(("confirmed", "checkin"), "done")
        self.write({"state": "done"})

    def action_cancel(self):
        self._check_transition(("draft", "confirmed", "checkin"), "cancel")
        self.write({"state": "cancel"})

    def action_create_encounter(self):
        self.ensure_one()
        self._check_transition(("checkin",), "checkin")
        if self.encounter_id:
            raise UserError(_("An encounter already exists for this appointment."))
        encounter = self.env["hms.encounter"].create(
            {
                "patient_id": self.patient_id.id,
                "appointment_id": self.id,
                "practitioner_id": self.practitioner_id.id,
                "department_id": self.department_id.id,
                "chief_complaint": self.reason,
            }
        )
        self.encounter_id = encounter.id
        self.state = "checkin"
        return {
            "type": "ir.actions.act_window",
            "name": "Encounter",
            "res_model": "hms.encounter",
            "res_id": encounter.id,
            "view_mode": "form",
            "target": "current",
        }
