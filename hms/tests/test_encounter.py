from datetime import date, datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEncounter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env["hms.department"].create(
            {"name": "Test Internal Medicine", "code": "TIM"}
        )
        cls.practitioner = cls.env["hms.practitioner"].create(
            {
                "name": "Dr. Gamma",
                "department_id": cls.department.id,
                "role": "doctor",
            }
        )
        cls.patient = cls.env["hms.patient"].create({"name": "Test Patient"})

    def _make_encounter(self, **extra):
        vals = {
            "patient_id": self.patient.id,
            "practitioner_id": self.practitioner.id,
            "department_id": self.department.id,
        }
        vals.update(extra)
        return self.env["hms.encounter"].create(vals)

    def _make_appointment(self, start):
        return self.env["hms.appointment"].create(
            {
                "patient_id": self.patient.id,
                "practitioner_id": self.practitioner.id,
                "department_id": self.department.id,
                "date_start": start,
                "duration_minutes": 30,
                "reason": "Headache and nausea",
            }
        )

    def test_sequence_and_default_state(self):
        enc = self._make_encounter()
        self.assertEqual(enc.state, "draft")
        self.assertTrue(enc.name.startswith("ENC-"))

    def test_state_flow(self):
        enc = self._make_encounter()
        enc.action_start()
        self.assertEqual(enc.state, "in_progress")
        enc.action_done()
        self.assertEqual(enc.state, "done")

        enc2 = self._make_encounter()
        enc2.action_start()
        enc2.action_cancel()
        self.assertEqual(enc2.state, "cancel")

    def test_create_from_appointment(self):
        appt = self._make_appointment(
            datetime.now().replace(microsecond=0) + timedelta(days=5)
        )
        appt.action_confirm()
        appt.action_checkin()
        action = appt.action_create_encounter()

        self.assertEqual(appt.state, "checkin")
        self.assertTrue(appt.encounter_id)
        encounter = appt.encounter_id
        self.assertEqual(action["res_model"], "hms.encounter")
        self.assertEqual(action["res_id"], encounter.id)
        self.assertEqual(encounter.patient_id, self.patient)
        self.assertEqual(encounter.practitioner_id, self.practitioner)
        self.assertEqual(encounter.department_id, self.department)
        self.assertEqual(encounter.appointment_id, appt)
        self.assertEqual(encounter.chief_complaint, "Headache and nausea")
        self.assertEqual(encounter.state, "draft")

    def test_bmi_computation(self):
        enc = self._make_encounter(weight=70.0, height=175.0)
        # digits=(12, 1) rounds the read value: 70 / 1.75^2 = 22.857 -> 22.9
        self.assertAlmostEqual(enc.bmi, 22.9)

    def test_bmi_without_vitals_is_zero(self):
        enc = self._make_encounter()
        self.assertEqual(enc.bmi, 0.0)
        enc.weight = 80.0
        self.assertEqual(enc.bmi, 0.0)

    def test_schedule_followup_creates_draft_appointment(self):
        enc = self._make_encounter()
        enc.followup_date = date(2026, 12, 15)
        action = enc.action_schedule_followup()

        self.assertEqual(action["res_model"], "hms.appointment")
        appointment = self.env["hms.appointment"].browse(action["res_id"])
        self.assertTrue(appointment.exists())
        self.assertEqual(appointment.state, "draft")
        self.assertEqual(appointment.patient_id, self.patient)
        self.assertEqual(appointment.practitioner_id, self.practitioner)
        self.assertEqual(appointment.department_id, self.department)
        self.assertEqual(appointment.date_start.date(), enc.followup_date)

    def test_schedule_followup_requires_date(self):
        enc = self._make_encounter()
        with self.assertRaises(UserError):
            enc.action_schedule_followup()
