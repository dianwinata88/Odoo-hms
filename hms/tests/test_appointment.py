from datetime import datetime, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAppointment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env["hms.department"].create(
            {"name": "Test Cardiology", "code": "TCARD"}
        )
        cls.practitioner = cls.env["hms.practitioner"].create(
            {
                "name": "Dr. Alpha",
                "department_id": cls.department.id,
                "role": "doctor",
            }
        )
        cls.other_practitioner = cls.env["hms.practitioner"].create(
            {
                "name": "Dr. Beta",
                "department_id": cls.department.id,
                "role": "doctor",
            }
        )
        cls.patient = cls.env["hms.patient"].create({"name": "Test Patient"})
        cls.start = datetime.now().replace(microsecond=0) + timedelta(days=10)

    def _make_appointment(self, start, duration=30, practitioner=None, patient=None):
        return self.env["hms.appointment"].create(
            {
                "patient_id": (patient or self.patient).id,
                "practitioner_id": (practitioner or self.practitioner).id,
                "department_id": self.department.id,
                "date_start": start,
                "duration_minutes": duration,
            }
        )

    def test_sequence_and_default_state(self):
        appt = self._make_appointment(self.start)
        self.assertEqual(appt.state, "draft")
        self.assertTrue(appt.name.startswith("APT-"))
        self.assertEqual(
            appt.date_end, appt.date_start + timedelta(minutes=appt.duration_minutes)
        )

    def test_state_transitions(self):
        appt = self._make_appointment(self.start + timedelta(hours=2))
        appt.action_confirm()
        self.assertEqual(appt.state, "confirmed")
        appt.action_checkin()
        self.assertEqual(appt.state, "checkin")
        appt.action_done()
        self.assertEqual(appt.state, "done")

        appt2 = self._make_appointment(self.start + timedelta(hours=4))
        appt2.action_confirm()
        appt2.action_cancel()
        self.assertEqual(appt2.state, "cancel")

    def test_back_to_back_allowed(self):
        self._make_appointment(self.start)
        adjacent = self._make_appointment(self.start + timedelta(minutes=30))
        self.assertTrue(adjacent.exists())

    def test_exact_overlap_rejected(self):
        self._make_appointment(self.start)
        with self.assertRaises(ValidationError):
            self._make_appointment(self.start)

    def test_partial_overlap_rejected(self):
        self._make_appointment(self.start)
        with self.assertRaises(ValidationError):
            self._make_appointment(self.start + timedelta(minutes=15))

    def test_cancelled_appointment_does_not_block(self):
        appt = self._make_appointment(self.start + timedelta(days=1))
        appt.action_cancel()
        rebooked = self._make_appointment(self.start + timedelta(days=1))
        self.assertTrue(rebooked.exists())

    def test_different_practitioner_same_slot_allowed(self):
        self._make_appointment(self.start + timedelta(days=2))
        other = self._make_appointment(
            self.start + timedelta(days=2), practitioner=self.other_practitioner
        )
        self.assertTrue(other.exists())

    def test_different_patient_overlap_still_rejected(self):
        other_patient = self.env["hms.patient"].create({"name": "Other Patient"})
        self._make_appointment(self.start + timedelta(days=3))
        with self.assertRaises(ValidationError):
            self._make_appointment(
                self.start + timedelta(days=3), patient=other_patient
            )
