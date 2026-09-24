from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPatientRegistry(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hms.patient"]
        cls.patient = cls.Patient.create({"name": "John Test", "gender": "male"})

    def test_mrn_sequence_uniqueness(self):
        self.assertTrue(self.patient.mrn.startswith("PAT-"))
        other = self.Patient.create({"name": "Jane Test"})
        self.assertTrue(other.mrn.startswith("PAT-"))
        self.assertNotEqual(self.patient.mrn, other.mrn)

    def test_mrn_not_overwritten_when_given(self):
        patient = self.Patient.create({"name": "Custom MRN", "mrn": "PAT-99999"})
        self.assertEqual(patient.mrn, "PAT-99999")

    def test_age_without_birth_date(self):
        self.assertEqual(self.patient.age, 0)

    def test_age_birthday_today(self):
        today = fields.Date.context_today(self.patient)
        born = today - relativedelta(years=40)
        self.patient.birth_date = born
        self.assertEqual(self.patient.age, 40)

    def test_age_birthday_not_yet_this_year(self):
        today = fields.Date.context_today(self.patient)
        born = today - relativedelta(years=40) + relativedelta(days=1)
        self.patient.birth_date = born
        self.assertEqual(self.patient.age, 39)

    def test_partner_linking(self):
        partner = self.env["res.partner"].create(
            {"name": "John Test", "email": "john.test@example.com"}
        )
        self.patient.partner_id = partner
        self.assertEqual(self.patient.partner_id, partner)
        # same partner may back several patient records
        sibling = self.Patient.create({"name": "John Test Jr", "partner_id": partner.id})
        self.assertEqual(sibling.partner_id, partner)

    def test_practitioner_defaults(self):
        department = self.env["hms.department"].create(
            {"name": "Test Dept", "code": "TST"}
        )
        practitioner = self.env["hms.practitioner"].create(
            {"name": "Dr. Default", "department_id": department.id}
        )
        self.assertEqual(practitioner.role, "doctor")
        self.assertTrue(practitioner.active)
        self.assertEqual(practitioner.currency_id, self.env.company.currency_id)

    def test_archive_hides_patient(self):
        self.assertIn(self.patient, self.Patient.search([("name", "=", "John Test")]))
        self.patient.active = False
        self.assertNotIn(self.patient, self.Patient.search([("name", "=", "John Test")]))
        with_context = self.Patient.with_context(active_test=False)
        self.assertIn(self.patient, with_context.search([("name", "=", "John Test")]))
