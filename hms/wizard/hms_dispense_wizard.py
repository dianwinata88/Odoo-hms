from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HmsDispenseWizard(models.TransientModel):
    _name = "hms.dispense.wizard"
    _description = "Dispense Prescription"

    prescription_id = fields.Many2one("hms.prescription", required=True, readonly=True)
    line_ids = fields.One2many(
        "hms.prescription.line",
        "prescription_id",
        string="Medications",
        related="prescription_id.line_ids",
        readonly=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        required=True,
        domain="[('usage', '=', 'internal')]",
        help="Source stock location (the pharmacy shelf).",
        default=lambda self: self.env.ref(
            "hms.stock_location_pharmacy", raise_if_not_found=False
        ),
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        default=lambda self: self._default_partner_id(),
        help="Defaults to the patient's billing contact.",
    )

    @api.model
    def _default_partner_id(self):
        prescription = self.env["hms.prescription"].browse(
            self.env.context.get("default_prescription_id")
        )
        return prescription.patient_id.partner_id.id if prescription else False

    def _check_dispensable(self, prescription):
        for line in prescription.line_ids:
            if line.product_id.type != "consu":
                raise UserError(
                    _(
                        "%(product)s is not a stockable item and cannot be dispensed.",
                        product=line.product_id.display_name,
                    )
                )
            if line.quantity <= 0:
                raise UserError(
                    _(
                        "%(product)s has no positive quantity to dispense.",
                        product=line.product_id.display_name,
                    )
                )

    def action_dispense(self):
        self.ensure_one()
        prescription = self.prescription_id
        if prescription.state != "confirmed":
            raise UserError(_("Only confirmed prescriptions can be dispensed."))
        if prescription.picking_id:
            raise UserError(
                _("%(name)s was already dispensed.", name=prescription.name)
            )
        self._check_dispensable(prescription)
        partner = self.partner_id or prescription.patient_id.partner_id
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id.company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if not picking_type:
            raise UserError(_("No outgoing picking type is configured."))
        if not picking_type.default_location_dest_id:
            raise UserError(
                _(
                    "No default destination location on the %(ptype)s picking type.",
                    ptype=picking_type.name,
                )
            )
        location_dest = picking_type.default_location_dest_id
        moves = []
        for line in prescription.line_ids:
            moves.append(
                (
                    0,
                    0,
                    {
                        "name": line.product_id.display_name,
                        "product_id": line.product_id.id,
                        "product_uom_qty": line.quantity,
                        "product_uom": line.uom_id.id,
                        "location_id": self.location_id.id,
                        "location_dest_id": location_dest.id,
                    },
                )
            )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "partner_id": partner.id if partner else False,
                "location_id": self.location_id.id,
                "location_dest_id": location_dest.id,
                "origin": prescription.name,
                "move_ids": moves,
            }
        )
        picking.action_confirm()
        picking.action_assign()
        deliverable = picking.move_ids.filtered(lambda m: m.quantity > 0)
        if not deliverable:
            picking.action_cancel()
            raise UserError(
                _(
                    "No stock could be reserved in %(location)s for %(name)s. "
                    "Nothing to dispense.",
                    location=self.location_id.display_name,
                    name=prescription.name,
                )
            )
        deliverable.picked = True
        result = picking.button_validate()
        if (
            isinstance(result, dict)
            and result.get("res_model") == "stock.backorder.confirmation"
        ):
            self.env["stock.backorder.confirmation"].browse(
                result["res_id"]
            ).process()
        prescription.write({"state": "dispensed", "picking_id": picking.id})
        return {"type": "ir.actions.act_window_close"}
