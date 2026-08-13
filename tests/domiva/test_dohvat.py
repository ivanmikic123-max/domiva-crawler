"""
Zaštita od preusmjeravanja na privatne mreže.

`SECURITY.md`, odjeljak 3. Ovo je jedini sloj koji stoji između tuđe adrese i
naše unutarnje mreže, pa mu testovi nisu ukras.
"""

import httpx
import pytest

from domiva.dohvat import NedopustenoOdrediste, provjeri_odrediste, sigurni_klijent


class TestProvjeraOdredista:
    def test_javna_adresa_prolazi(self):
        # 8.8.8.8 je javan i ne traži razrješavanje imena.
        provjeri_odrediste(httpx.URL("https://8.8.8.8/cjenik.csv"))

    @pytest.mark.parametrize(
        "adresa",
        [
            "http://127.0.0.1/",
            "http://localhost/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            # Odavde se u oblaku čitaju vjerodajnice poslužitelja. Ovo je
            # razlog zbog kojeg cijela ova datoteka postoji.
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
        ],
    )
    def test_privatna_adresa_pada(self, adresa):
        with pytest.raises(NedopustenoOdrediste):
            provjeri_odrediste(httpx.URL(adresa))

    @pytest.mark.parametrize("adresa", ["file:///etc/passwd", "ftp://primjer.hr/", "gopher://x/"])
    def test_druge_sheme_padaju(self, adresa):
        with pytest.raises(NedopustenoOdrediste):
            provjeri_odrediste(httpx.URL(adresa))

    def test_ime_koje_se_ne_razrjesava_pada(self):
        with pytest.raises(NedopustenoOdrediste):
            provjeri_odrediste(httpx.URL("https://ovo-ime-sigurno-ne-postoji.invalid/"))

    def test_nestandardni_port_na_javnoj_adresi_prolazi(self):
        # Dio lanaca objavljuje cjenike na drugom portu. Zabrana porta ne bi
        # dodala sigurnost — SSRF je pitanje adrese, ne broja vrata.
        provjeri_odrediste(httpx.URL("https://8.8.8.8:8443/cjenik.csv"))


class TestKlijent:
    def test_zahtjev_na_petlju_ne_izlazi_van(self):
        # Ključno: provjera je na prijenosnom sloju, pa vrijedi i za svaku
        # kariku preusmjeravanja, ne samo za prvu adresu.
        klijent = sigurni_klijent(timeout=2.0)

        with pytest.raises(NedopustenoOdrediste):
            klijent.get("http://127.0.0.1:1/cjenik.csv")

    def test_klijent_prati_preusmjeravanja(self):
        # Bez toga dio lanaca ne radi; zaštita ne smije to ukinuti.
        klijent = sigurni_klijent()
        assert klijent.follow_redirects is True
