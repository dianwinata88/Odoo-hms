from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPrescriptionDispense(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env["hms.department"].create(
            {"name": "Pharmacy Test", "code": "PHA"}
        )
        cls.practitioner = cls.env["hms.practitioner"].create(
            {
                "name": "Dr. Dispense",
                "department_id": cls.department.id,
                "role": "doctor",
            }
        )
        cls.patient = cls.env["hms.patient"].create({"name": "Jane Test"})
        cls.drug = cls.env["product.product"].create(
            {
                "name": "Test Paracetamol 500mg",
                "type": "consu",
                "is_storable": True,
                "sale_ok": True,
                "list_price": 5.0,
            }
        )
        cls.pharmacy_location = cls.env.ref("hms.stock_location_pharmacy")
        cls.env["stock.quant"]._update_available_quantity(
            cls.drug, cls.pharmacy_location, 20.0
        )

    def _make_prescription(self):
        return self.env["hms.prescription"].create(
            {
                "patient_id": self.patient.id,
                "practitioner_id": self.practitioner.id,
            }
        )

    def _make_line(self, prescription, product=None, quantity=3.0):
        return self.env["hms.prescription.line"].create(
            {
                "prescription_id": prescription.id,
                "product_id": (product or self.drug).id,
                "quantity": quantity,
                "dose": "500mg",
                "frequency": "3x daily",
            }
        )

    def _run_wizard(self, prescription):
        wizard = self.env["hms.dispense.wizard"].create(
            {"prescription_id": prescription.id}
        )
        return wizard.action_dispense()

    def test_confirm_requires_lines(self):
        prescription = self._make_prescription()
        with self.assertRaises(UserError):
            prescription.action_confirm()

    def test_dispense_creates_validated_picking(self):
        prescription = self._make_prescription()
        self._make_line(prescription, quantity=3.0)
        prescription.action_confirm()
        self._run_wizard(prescription)
        self.assertEqual(prescription.state, "dispensed")
        picking = prescription.picking_id
        self.assertTrue(picking)
        self.assertEqual(picking.state, "done")
        self.assertEqual(len(picking.move_ids), 1)
        move = picking.move_ids
        self.assertEqual(move.product_id, self.drug)
        self.assertEqual(move.product_uom_qty, 3.0)
        self.assertEqual(move.quantity, 3.0)
        self.assertEqual(move.location_id, self.pharmacy_location)

    def test_dispense_requires_confirmed_state(self):
        draft = self._make_prescription()
        self._make_line(draft)
        with self.assertRaises(UserError):
            draft.action_dispense()
        with self.assertRaises(UserError):
            self._run_wizard(draft)

    def test_double_dispense_prevented(self):
        prescription = self._make_prescription()
        self._make_line(prescription)
        prescription.action_confirm()
        self._run_wizard(prescription)
        with self.assertRaises(UserError):
            prescription.action_dispense()
        with self.assertRaises(UserError):
            self._run_wizard(prescription)

    def test_dispense_without_stock_raises(self):
        out_of_stock = self.env["product.product"].create(
            {
                "name": "Test Rare Drug",
                "type": "consu",
                "is_storable": True,
                "sale_ok": True,
                "list_price": 20.0,
            }
        )
        prescription = self._make_prescription()
        self._make_line(prescription, product=out_of_stock)
        prescription.action_confirm()
        with self.assertRaises(UserError):
            self._run_wizard(prescription)
        self.assertEqual(prescription.state, "confirmed")
        self.assertFalse(prescription.picking_id)
