from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HmsPrescription(models.Model):
    _name = "hms.prescription"
    _description = "Prescription"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    patient_id = fields.Many2one("hms.patient", required=True, tracking=True, index=True)
    encounter_id = fields.Many2one("hms.encounter", ondelete="set null")
    practitioner_id = fields.Many2one("hms.practitioner", required=True, tracking=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("dispensed", "Dispensed"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        group_expand="_expand_states",
    )
    line_ids = fields.One2many("hms.prescription.line", "prescription_id", string="Lines")
    notes = fields.Text()
    picking_id = fields.Many2one("stock.picking", readonly=True, copy=False)
    user_id = fields.Many2one(
        "res.users",
        string="Practitioner user",
        related="practitioner_id.user_id",
        store=True,
    )

    @api.model
    def _expand_states(self, states, domain, order):
        return [key for key, _label in self._fields["state"].selection]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("hms.prescription") or "New"
                )
        return super().create(vals_list)

    def action_confirm(self):
        for prescription in self:
            if not prescription.line_ids:
                raise UserError(
                    _("Cannot confirm %(name)s: add at least one medication line.", name=prescription.name)
                )
        self.write({"state": "confirmed"})

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_dispense(self):
        self.ensure_one()
        if self.state != "confirmed":
            raise UserError(_("Only confirmed prescriptions can be dispensed."))
        return {
            "type": "ir.actions.act_window",
            "name": "Dispense",
            "res_model": "hms.dispense.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_prescription_id": self.id},
        }


class HmsPrescriptionLine(models.Model):
    _name = "hms.prescription.line"
    _description = "Prescription Line"
    _order = "id"

    prescription_id = fields.Many2one(
        "hms.prescription", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        domain="[('type', 'in', ['consu', 'product']), ('sale_ok', '=', True)]",
    )
    quantity = fields.Float(default=1.0, required=True)
    dose = fields.Char(help="e.g. 500 mg")
    frequency = fields.Char(help="e.g. 3x daily")
    duration_days = fields.Integer(string="Duration (days)")
    instructions = fields.Char(help="e.g. after meals")
    uom_id = fields.Many2one(
        "uom.uom",
        related="product_id.uom_id",
        readonly=True,
    )
