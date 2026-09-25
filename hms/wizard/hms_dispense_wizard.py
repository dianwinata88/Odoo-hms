from odoo import _, fields, models
from odoo.exceptions import UserError


class HmsDispenseWizard(models.TransientModel):
    _name = "hms.dispense.wizard"
    _description = "Dispense Prescription"

    prescription_id = fields.Many2one("hms.prescription", required=True, readonly=True)
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
        help="Defaults to the patient's billing contact.",
    )

    def action_dispense(self):
        self.ensure_one()
        prescription = self.prescription_id
        prescription._check_can_dispense()
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
                        "location_dest_id": picking_type.default_location_dest_id.id,
                    },
                )
            )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "partner_id": partner.id if partner else False,
                "location_id": self.location_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "origin": prescription.name,
                "move_ids": moves,
            }
        )
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()
        prescription.write({"state": "dispensed", "picking_id": picking.id})
        return {"type": "ir.actions.act_window_close"}
