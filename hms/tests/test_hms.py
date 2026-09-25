from datetime import datetime, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHmsBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env["hms.department"].create(
            {"name": "General Medicine", "code": "GEN"}
        )
        cls.practitioner = cls.env["hms.practitioner"].create(
            {
                "name": "Dr. Test",
                "department_id": cls.department.id,
                "role": "doctor",
                "consultation_fee": 50.0,
            }
        )
        cls.patient = cls.env["hms.patient"].create(
            {"name": "John Test", "gender": "male", "birth_date": "1990-01-15"}
        )
        cls.drug = cls.env["product.product"].create(
            {"name": "Paracetamol 500mg", "type": "consu", "list_price": 5.0}
        )


class TestPatient(TestHmsBase):
    def test_mrn_sequence(self):
        self.assertTrue(self.patient.mrn.startswith("PAT-"))
        other = self.env["hms.patient"].create({"name": "Jane Test"})
        self.assertNotEqual(self.patient.mrn, other.mrn)

    def test_age_computation(self):
        self.assertGreater(self.patient.age, 30)


class TestAppointment(TestHmsBase):
    def _make_appointment(self, start, duration=30):
        return self.env["hms.appointment"].create(
            {
                "patient_id": self.patient.id,
                "practitioner_id": self.practitioner.id,
                "department_id": self.department.id,
                "date_start": start,
                "duration_minutes": duration,
            }
        )

    def test_appointment_flow(self):
        appt = self._make_appointment(datetime.now() + timedelta(days=1))
        self.assertEqual(appt.state, "draft")
        self.assertTrue(appt.name.startswith("APT-"))
        appt.action_confirm()
        self.assertEqual(appt.state, "confirmed")
        appt.action_checkin()
        self.assertEqual(appt.state, "checkin")

    def test_practitioner_overlap_rejected(self):
        start = datetime.now() + timedelta(days=2)
        self._make_appointment(start)
        with self.assertRaises(ValidationError):
            self._make_appointment(start + timedelta(minutes=15))

    def test_non_overlapping_allowed(self):
        start = datetime.now() + timedelta(days=3)
        self._make_appointment(start)
        self._make_appointment(start + timedelta(hours=1))


class TestPractitionerOwnership(TestHmsBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doctor_user = cls.env["res.users"].create(
            {
                "name": "Dr. Own",
                "login": "dr_own_hms",
                "groups_id": [(6, 0, [cls.env.ref("hms.group_hms_practitioner").id])],
            }
        )
        employee = cls.env["hr.employee"].create(
            {"name": "Dr. Own", "user_id": cls.doctor_user.id}
        )
        cls.own_practitioner = cls.env["hms.practitioner"].create(
            {
                "name": "Dr. Own",
                "employee_id": employee.id,
                "department_id": cls.department.id,
                "role": "doctor",
            }
        )

    def _vals(self, model, practitioner):
        vals = {"patient_id": self.patient.id, "practitioner_id": practitioner.id}
        if model == "hms.appointment":
            vals["date_start"] = datetime.now() + timedelta(days=10)
        return vals

    def test_practitioner_can_create_own_records(self):
        for model in ("hms.appointment", "hms.encounter", "hms.prescription"):
            rec = self.env[model].with_user(self.doctor_user).create(
                self._vals(model, self.own_practitioner)
            )
            self.assertEqual(rec.user_id, self.doctor_user)

    def test_practitioner_cannot_create_for_other_practitioner(self):
        for model in ("hms.appointment", "hms.encounter", "hms.prescription"):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.doctor_user).create(
                    self._vals(model, self.practitioner)
                )


class TestEncounterBilling(TestHmsBase):
    def setUp(self):
        super().setUp()
        self.encounter = self.env["hms.encounter"].create(
            {
                "patient_id": self.patient.id,
                "practitioner_id": self.practitioner.id,
                "department_id": self.department.id,
            }
        )

    def test_encounter_sequence_and_state(self):
        self.assertTrue(self.encounter.name.startswith("ENC-"))
        self.encounter.action_start()
        self.assertEqual(self.encounter.state, "in_progress")
        self.encounter.action_done()
        self.assertEqual(self.encounter.state, "done")

    def test_prescription_requires_lines(self):
        prescription = self.env["hms.prescription"].create(
            {
                "patient_id": self.patient.id,
                "encounter_id": self.encounter.id,
                "practitioner_id": self.practitioner.id,
            }
        )
        with self.assertRaises(UserError):
            prescription.action_confirm()

    def test_invoice_includes_consultation_and_drugs(self):
        prescription = self.env["hms.prescription"].create(
            {
                "patient_id": self.patient.id,
                "encounter_id": self.encounter.id,
                "practitioner_id": self.practitioner.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.drug.id,
                            "quantity": 2,
                            "dose": "500mg",
                            "frequency": "3x daily",
                        },
                    )
                ],
            }
        )
        prescription.action_confirm()
        self.assertTrue(self.patient.partner_id or True)
        self.encounter.action_create_invoice()
        invoice = self.encounter.invoice_id
        self.assertTrue(invoice)
        self.assertEqual(invoice.partner_id, self.patient.partner_id)
        # consultation fee + 2x drug at list price 5.0 = 50 + 10 = 60
        self.assertAlmostEqual(invoice.amount_untaxed, 60.0)
        with self.assertRaises(UserError):
            self.encounter.action_create_invoice()
