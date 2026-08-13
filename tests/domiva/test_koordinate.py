"""
Koordinate poslovnica.

Bez njih poslovnica ne ulazi ni u jedan radijus, a to je greška koja se ne vidi:
korisniku samo izgleda kao da mu u blizini nema nijedne trgovine tog lanca.
"""

import pytest

from domiva.koordinate import _ucitaj, pokrivenost, za_poslovnicu


class TestUcitavanje:
    def test_popis_nije_prazan(self):
        assert len(_ucitaj()) > 500

    def test_svaka_koordinata_je_u_hrvatskoj(self):
        # Hvata (0, 0) i zamijenjene stupce — dvije najčešće greške u
        # geokodiranim popisima.
        for lat, lng in _ucitaj().values():
            assert 42.0 <= lat <= 47.0
            assert 13.0 <= lng <= 20.0


class TestTrazenje:
    def test_nalazi_poznatu_poslovnicu(self):
        lat, lng = za_poslovnicu("konzum", "3222")

        assert lat == pytest.approx(45.59, abs=0.05)
        assert lng == pytest.approx(17.22, abs=0.05)

    def test_vodece_nule_ne_smetaju(self):
        # Lanac objavljuje `0463`, popis nosi `463`. Ista poslovnica.
        s_nulom = za_poslovnicu("konzum", "0463")
        bez_nule = za_poslovnicu("konzum", "463")

        assert s_nulom == bez_nule
        assert s_nulom[0] is not None

    def test_velika_slova_u_nazivu_lanca_ne_smetaju(self):
        assert za_poslovnicu("KONZUM", "3222") == za_poslovnicu("konzum", "3222")

    def test_nepoznata_poslovnica_daje_prazno(self):
        assert za_poslovnicu("lidl", "ne-postoji") == (None, None)

    def test_ista_sifra_u_drugom_lancu_ne_daje_tudu_poslovnicu(self):
        # Ključ mora biti (lanac, šifra). Sama šifra nije jedinstvena — dva
        # lanca lako imaju poslovnicu „100", a zamjena bi korisnika poslala u
        # drugi grad.
        konzum = za_poslovnicu("konzum", "3222")
        drugi = za_poslovnicu("lidl", "3222")

        assert konzum[0] is not None
        assert drugi != konzum


class TestPokrivenost:
    def test_konzum_ima_geokodirane_poslovnice(self):
        assert pokrivenost("konzum") > 0

    def test_izmisljen_lanac_nema_nijednu(self):
        assert pokrivenost("ne-postoji") == 0
