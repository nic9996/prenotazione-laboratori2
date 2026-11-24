import unittest
from datetime import date

from prenotazioni import Sessione


class TestSegnalazioni(unittest.TestCase):
    def setUp(self):
        self.sessione = Sessione(
            "LAB001", date(2026, 11, 23), "08:00", "10:00", "Giovanni", 12
        )

    def test_orario_di_apertura(self):
        self.sessione