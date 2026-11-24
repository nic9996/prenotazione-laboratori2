import unittest
from datetime import date

from prenotazioni import Sessione


class TestSessione(unittest.TestCase):
    def test_orari_non_ammessi(self):
        # il costruttore solleva ValueError per orari non ammessi: inizio non multiplo
        # di 30 minuti, inizio prima dell'apertura, fine dopo la chiusura, fine
        # precedente all'inizio;
        orari_non_ammessi = [
            ("07:15", "08:00"),
            ("04:00", "12:00"),
            ("12:00", "23:00"),
            ("12:00", "11:00"),
        ]
        for inizio, fine in orari_non_ammessi:
            with self.assertRaises(ValueError):
                Sessione("LAB001", date(2026, 11, 18), inizio, fine, "Giovanni", 12)

    def test_data_non_ammessa(self):
        # il costruttore solleva TypeError se il giorno	non	è un date
        with self.assertRaises(TypeError):
            Sessione("LAB001", "2026, 11, 18", "08:00", "10:00", "Giovanni", 12)

    def test_durata_in_minuti(self):
        # durata_minuti restituisce	la durata corretta
        sessione = Sessione(
            "LAB001", date(2026, 11, 18), "08:00", "10:00", "Giovanni", 12
        )
        self.assertEqual(sessione.durata_minuti(), 120)

    def test_si_sovrappone(self):
        # `si_sovrappone` restituisce `False` per laboratori diversi e per giorni
        # diversi, `True` per un intervallo contenuto in un altro;
        sessione_a = Sessione(
            "LAB001", date(2026, 11, 18), "08:00", "10:00", "Giovanni", 12
        )
        sessione_b = Sessione(
            "LAB002", date(2026, 11, 18), "08:00", "10:00", "Giovanni", 12
        )
        self.assertFalse(sessione_a.si_sovrappone(sessione_b))
        sessione_c = Sessione(
            "LAB003", date(2026, 11, 17), "09:00", "12:30", "Giovanni", 12
        )
        self.assertFalse(sessione_a.si_sovrappone(sessione_c))
        sessione_d = Sessione(
            "LAB001", date(2026, 11, 18), "09:00", "11:30", "Giovanni", 12
        )
        self.assertTrue(sessione_a.si_sovrappone(sessione_d))