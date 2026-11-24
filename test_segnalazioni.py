import unittest
from datetime import date

from prenotazioni import Centro, Laboratorio, Sessione


class TestSegnalazioni(unittest.TestCase):
    def setUp(self):
        oggi = date.today()
        self.sessione = Sessione("LAB001", oggi, "08:00", "10:00", "Giovanni", 12)

    def test_orario_di_apertura(self):
        self.sessione

    def test_postazioni(self):
        centro = Centro()
        sessione = self.sessione
        laboratorio = Laboratorio("LAB001", "Meccanica", 12, dotazioni=None)
        centro.aggiungi_laboratorio(laboratorio)
        centro.prenota(sessione)
