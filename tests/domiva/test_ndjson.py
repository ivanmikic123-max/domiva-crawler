"""
Ugovor prema Domivi.

Ovi testovi čuvaju jednu stvar: da se oblik NDJSON-a ne promijeni a da to netko
ne primijeti. S druge strane granice stoji Zod shema u
`packages/shared/src/sheme/cjenik.ts` i ona odbija sve što ne prepozna — pa bi
tiha promjena ovdje značila da Domiva odbaci cijeli lanac.
"""

from decimal import Decimal

import pytest

from crawler.crawl import CRAWLERS
from crawler.store.models import Product, Store
from domiva.ndjson import redak_cjenika, redak_poslovnice, zapisi_lanac


def proizvod(**izmjene) -> Product:
    podaci = {
        "product": "Mlijeko trajno 2,8% m.m.",
        "product_id": "LD-100241",
        "brand": "Milbona",
        "quantity": "1",
        "unit": "l",
        "price": Decimal("1.09"),
        "unit_price": Decimal("1.09"),
        "barcode": "3850001000017",
        "category": "mliječni proizvodi",
        "best_price_30": Decimal("0.99"),
        "anchor_price": Decimal("1.05"),
    }
    podaci.update(izmjene)
    return Product(**podaci)


def poslovnica(**izmjene) -> Store:
    podaci = {
        "chain": "lidl",
        "store_id": "1041",
        "name": "Lidl Zagreb — Zavrtnica",
        "store_type": "supermarket",
        "city": "Zagreb",
        "street_address": "Zavrtnica 17",
        "zipcode": "10000",
        "items": [proizvod()],
    }
    podaci.update(izmjene)
    return Store(**podaci)


class TestRedakCjenika:
    def test_polja_odgovaraju_ugovoru(self):
        redak = redak_cjenika(poslovnica(), proizvod())

        assert set(redak) == {
            "store_code",
            "external_code",
            "ean",
            "name",
            "brand",
            "net_quantity",
            "unit",
            "category_raw",
            "price",
            "unit_price",
            "special_price",
            "best_price_30",
            "anchor_price",
        }

    def test_cijene_su_decimalni_euri(self):
        redak = redak_cjenika(poslovnica(), proizvod())

        assert redak["price"] == 1.09
        assert redak["best_price_30"] == 0.99

    def test_polje_koje_lanac_ne_objavljuje_ostaje_prazno(self):
        # „Ne izmišljaj vrijednosti." Nula bi značila besplatan artikl.
        redak = redak_cjenika(poslovnica(), proizvod(special_price=None))
        assert redak["special_price"] is None

    def test_kolicina_s_decimalnim_zarezom(self):
        # Cjenici dolaze iz tridesetak sustava; zarez je češći od točke.
        assert (
            redak_cjenika(poslovnica(), proizvod(quantity="1,5"))["net_quantity"] == 1.5
        )

    def test_kolicina_s_jedinicom_u_istom_polju(self):
        assert (
            redak_cjenika(poslovnica(), proizvod(quantity="500 g"))["net_quantity"]
            == 500
        )

    def test_nečitljiva_kolicina_ostaje_prazna(self):
        assert (
            redak_cjenika(poslovnica(), proizvod(quantity="po dogovoru"))[
                "net_quantity"
            ]
            is None
        )

    def test_nepoznata_jedinica_ostaje_prazna(self):
        # Pogrešna jedinica je gora od nikakve — u planeru daje krivu količinu
        # za kupnju.
        assert redak_cjenika(poslovnica(), proizvod(unit="pakiranje"))["unit"] is None

    def test_jedinice_se_svode_na_male_znakove(self):
        assert redak_cjenika(poslovnica(), proizvod(unit="KG"))["unit"] == "kg"
        assert redak_cjenika(poslovnica(), proizvod(unit="Kom"))["unit"] == "kom"

    def test_ean_zadrzava_samo_znamenke(self):
        assert (
            redak_cjenika(poslovnica(), proizvod(barcode="385-000-1000017"))["ean"]
            == "3850001000017"
        )

    def test_prekratak_ean_ostaje_prazan(self):
        assert redak_cjenika(poslovnica(), proizvod(barcode="123"))["ean"] is None

    def test_prazan_ean_ostaje_prazan(self):
        assert redak_cjenika(poslovnica(), proizvod(barcode=""))["ean"] is None

    def test_ean_s_krivom_kontrolnom_znamenkom_prolazi(self):
        # I dalje je koristan kao ključ prema Open Food Factsu, a promašaj ondje
        # ne košta ništa.
        assert (
            redak_cjenika(poslovnica(), proizvod(barcode="3850001000010"))["ean"]
            is not None
        )

    def test_naziv_bez_sadrzaja_ne_ostaje_prazan(self):
        # Zod shema traži barem jedan znak; prazan naziv srušio bi cijeli redak.
        assert (
            redak_cjenika(poslovnica(), proizvod(product="   "))["name"]
            == "(bez naziva)"
        )

    def test_negativna_cijena_ostaje_prazna(self):
        assert (
            redak_cjenika(poslovnica(), proizvod(price=Decimal("-1")))["price"] is None
        )


class TestRedakPoslovnice:
    def test_polja_odgovaraju_ugovoru(self):
        assert set(redak_poslovnice(poslovnica())) == {
            "store_code",
            "name",
            "address",
            "city",
            "zip_code",
            "lat",
            "lng",
        }

    def test_poznata_poslovnica_dobiva_koordinate(self):
        # Konzum 0463 je u `enrichment/stores.csv` zapisan kao `463` — bez
        # podudaranja i s vodećim nulama i bez njih, ova bi poslovnica ispala iz
        # svih radijusa.
        redak = redak_poslovnice(poslovnica(chain="konzum", store_id="0463"))

        assert redak["lat"] == pytest.approx(45.36, abs=0.05)
        assert redak["lng"] == pytest.approx(14.34, abs=0.05)

    def test_nepoznata_poslovnica_ostaje_bez_koordinata(self):
        # Jasno stanje, ne tiha greška: vidljiva u katalogu, izvan radijusa.
        redak = redak_poslovnice(poslovnica(chain="lidl", store_id="ne-postoji"))

        assert redak["lat"] is None
        assert redak["lng"] is None

    def test_poslovnica_bez_naziva_dobiva_zamjenski(self):
        redak = redak_poslovnice(poslovnica(name=""))
        assert "lidl" in redak["name"].lower()


class TestZapis:
    def test_zapisuje_na_ocekivane_kljuceve(self, tmp_path):
        zapisi_lanac(tmp_path, "2026-08-11", "lidl", [poslovnica()], stlaci=False)

        assert (tmp_path / "raw" / "2026-08-11" / "lidl" / "prices.ndjson").exists()
        assert (tmp_path / "raw" / "2026-08-11" / "lidl" / "stores.ndjson").exists()

    def test_svaki_redak_je_zaseban_json(self, tmp_path):
        import json

        store = poslovnica(items=[proizvod(), proizvod(product_id="LD-2")])
        zapisi_lanac(tmp_path, "2026-08-11", "lidl", [store], stlaci=False)

        redci = (
            (tmp_path / "raw" / "2026-08-11" / "lidl" / "prices.ndjson")
            .read_text(encoding="utf-8")
            .strip()
            .split("\n")
        )

        assert len(redci) == 2
        assert all(json.loads(r)["store_code"] == "1041" for r in redci)

    def test_artikl_bez_cijene_ne_ulazi_u_cjenik(self, tmp_path):
        store = poslovnica(
            items=[proizvod(price=Decimal("-5")), proizvod(product_id="LD-2")]
        )
        broj_cijena, _ = zapisi_lanac(
            tmp_path, "2026-08-11", "lidl", [store], stlaci=False
        )

        assert broj_cijena == 1

    def test_stlaceni_zapis_dobiva_nastavak(self, tmp_path):
        zapisi_lanac(tmp_path, "2026-08-11", "lidl", [poslovnica()], stlaci=True)
        assert (tmp_path / "raw" / "2026-08-11" / "lidl" / "prices.ndjson.gz").exists()

    def test_hrvatski_znakovi_ostaju_citljivi(self, tmp_path):
        store = poslovnica(items=[proizvod(product="Šećer bijeli — Đakovo")])
        zapisi_lanac(tmp_path, "2026-08-11", "lidl", [store], stlaci=False)

        sadrzaj = (
            tmp_path / "raw" / "2026-08-11" / "lidl" / "prices.ndjson"
        ).read_text("utf-8")
        assert "Šećer" in sadrzaj


class TestSifreLanaca:
    """
    Šifre lanaca moraju se poklapati s Domivinim seedom.

    Popis je ovdje doslovno prepisan iz `packages/db/prisma/seed/lanci.ts`. Kad
    uzvodni projekt preimenuje lanac, ovaj test pada — inače bi taj lanac tiho
    prestao ulaziti u Domivu, a nitko ne bi znao zašto.
    """

    SIFRE_U_DOMIVI = {
        "boso",
        "branka",
        "brodokomerc",
        "bure",
        "djelo_vodice",
        "dm",
        "dukat",
        "eurospin",
        "gavranovic",
        "jadranka_trgovina",
        "kaufland",
        "konzum",
        "ktc",
        "lidl",
        "lorenco",
        "metro",
        "ntl",
        "plodine",
        "ribola",
        "roto",
        "spar",
        "stanic",
        "stridon",
        "studenac",
        "tommy",
        "trgocentar",
        "trgovina-krk",
        "vrutak",
        "zabac",
    }

    def test_svaki_crawler_ima_lanac_u_domivi(self):
        visak = set(CRAWLERS) - self.SIFRE_U_DOMIVI
        assert visak == set(), f"Crawler ima lance kojih u Domivi nema: {sorted(visak)}"

    def test_svaki_lanac_u_domivi_ima_crawler(self):
        nedostaje = self.SIFRE_U_DOMIVI - set(CRAWLERS)
        assert nedostaje == set(), (
            f"Domiva očekuje lance bez crawlera: {sorted(nedostaje)}"
        )

    def test_ima_ih_dvadeset_devet(self):
        assert len(CRAWLERS) == 29


@pytest.mark.parametrize(
    "ulaz,ocekivano",
    [
        ("1", 1.0),
        ("1,5", 1.5),
        ("0.500", 0.5),
        ("", None),
        ("0", None),
        (None, None),
    ],
)
def test_citanje_kolicine(ulaz, ocekivano):
    from domiva.ndjson import _broj

    assert _broj(ulaz) == ocekivano


class TestNatpisPakiranja:
    """
    Lidl u `JEDINICA_MJERE` upisuje cijelu mjeru, ne jedinicu.

    Prvi uvoz stvarnih podataka pokazao je posljedicu: od 7004 Lidlova
    proizvoda samo 15 je imalo jedinicu. Bez nje Domiva ne može izračunati
    cijenu po mjeri, pa je cijeli popis za kupnju ostao „NIJE DOSTUPNO" — a
    nigdje nije bilo greške koja bi na to uputila.
    """

    def test_natpis_daje_i_broj_i_jedinicu(self):
        redak = redak_cjenika(poslovnica(), proizvod(quantity="0.8", unit="800g"))
        assert redak["net_quantity"] == 800
        assert redak["unit"] == "g"

    def test_litre_iz_natpisa(self):
        redak = redak_cjenika(poslovnica(), proizvod(quantity="1.5", unit="1,5l"))
        assert redak["net_quantity"] == 1.5
        assert redak["unit"] == "l"

    def test_priblizna_mjera_se_prihvaca(self):
        redak = redak_cjenika(poslovnica(), proizvod(quantity="1", unit="ca. 500g"))
        assert redak["net_quantity"] == 500
        assert redak["unit"] == "g"

    def test_cista_jedinica_ima_prednost(self):
        # Lanci koji `unit` ispunjavaju ispravno moraju ostati netaknuti:
        # količina se i dalje uzima iz `quantity`, ne iz natpisa.
        redak = redak_cjenika(poslovnica(), proizvod(quantity="250", unit="g"))
        assert redak["net_quantity"] == 250
        assert redak["unit"] == "g"

    def test_slozen_natpis_ostaje_neprepoznat(self):
        # Iz „2x250g" se ne vidi je li neto količina 250 ili 500. Kriva mjera
        # tiho uđe u cijenu po kilogramu, pa je nikakva bolja od pogođene.
        redak = redak_cjenika(poslovnica(), proizvod(quantity="", unit="2x250g"))
        assert redak["unit"] is None

    def test_nepoznata_jedinica_u_natpisu_ostaje_neprepoznata(self):
        redak = redak_cjenika(poslovnica(), proizvod(quantity="", unit="500 vreca"))
        assert redak["unit"] is None
