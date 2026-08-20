"""
Koordinate poslovnica.

Trgovci ih u cjenicima ne objavljuju. Bez njih poslovnica ne ulazi ni u jedan
radijus, pa cijeli odjeljak „poslovnice u blizini" ostaje prazan — a to je jedan
od razloga zbog kojih Domiva uopće postoji.

Izvor je `enrichment/stores.csv` iz uzvodnog projekta. Ta datoteka **nije** pod
CC BY-NC-SA licencom — uzvodni README pod nju stavlja samo `products.csv` — pa
stoji pod AGPL-3 licencom cijelog projekta i smije se koristiti. Obveza time
ostaje unutar ovog javnog repozitorija; Domiva vidi samo brojke u NDJSON-u.

Poslovnica koje u popisu nema dobiva `null`. To je jasno stanje, ne tiha greška:
Domiva je prikaže u katalogu, ali ne i u pretrazi po radijusu.
"""

from __future__ import annotations

import csv
import os
from functools import lru_cache
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)


def _putanja_popisa() -> Path:
    """
    Gdje stoji `stores.csv`.

    Iz repozitorija se pokreće pokraj paketa, pa je dovoljno gledati jedan
    direktorij iznad. U spremniku to ne vrijedi: `pip install .` odnese paket u
    `site-packages`, a `enrichment/` ostaje u `/app`. Ranije se tada gledalo
    samo pokraj paketa, pa je crawler radio i **tiho** ispisivao poslovnice bez
    koordinata — uz jedno upozorenje koje se izgubi među tisućama redaka.

    Zato se traži na oba mjesta, a `DOMIVA_STORES_CSV` nadglasava oba kad
    datoteka stoji negdje treće.
    """
    izvana = os.environ.get("DOMIVA_STORES_CSV", "").strip()
    if izvana:
        return Path(izvana)

    pokraj_paketa = Path(__file__).parents[1] / "enrichment" / "stores.csv"
    if pokraj_paketa.exists():
        return pokraj_paketa

    return Path("/app") / "enrichment" / "stores.csv"


POPIS = _putanja_popisa()

# Granice Hrvatske, grubo. Zadaća im je uhvatiti (0, 0) i zamijenjene stupce —
# najčešće dvije greške u geokodiranim popisima. Poslovnica u Gvinejskom zaljevu
# nikad se ne bi pojavila ni u jednom radijusu, a nitko ne bi znao zašto.
GRANICE_LAT = (42.0, 47.0)
GRANICE_LNG = (13.0, 20.0)


def _broj(vrijednost: str) -> float | None:
    tekst = (vrijednost or "").strip()
    if not tekst:
        return None
    try:
        return float(tekst)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _ucitaj() -> dict[tuple[str, str], tuple[float, float]]:
    """
    Učitava popis jednom po procesu.

    Ključ je `(lanac, šifra poslovnice)`. Sama šifra nije jedinstvena — dva lanca
    lako imaju poslovnicu „100".
    """
    if not POPIS.exists():
        logger.warning("Nema %s; poslovnice ostaju bez koordinata.", POPIS)
        return {}

    karta: dict[tuple[str, str], tuple[float, float]] = {}

    with POPIS.open(encoding="utf-8", newline="") as datoteka:
        for redak in csv.DictReader(datoteka):
            lanac = (redak.get("chain_code") or "").strip().lower()
            sifra = (redak.get("code") or "").strip()
            lat = _broj(redak.get("lat", ""))
            lng = _broj(redak.get("lon", ""))

            if not lanac or not sifra or lat is None or lng is None:
                continue

            if not (GRANICE_LAT[0] <= lat <= GRANICE_LAT[1]):
                continue
            if not (GRANICE_LNG[0] <= lng <= GRANICE_LNG[1]):
                continue

            karta[(lanac, sifra)] = (lat, lng)

    _dodaj_pricuvne_kljuceve(karta)

    logger.info("Učitano %d geokodiranih poslovnica.", len(karta))
    return karta


def _dodaj_pricuvne_kljuceve(karta: dict[tuple[str, str], tuple[float, float]]) -> None:
    """
    Dodaje šifre bez vodećih nula kao dodatne ključeve.

    Popis nosi `0463`, a lanac u cjeniku zna objaviti `463` — ista poslovnica,
    dva zapisa. Bez ovoga bi ispala iz svih radijusa, i to tiho.

    Pričuvni ključ se **ne dodaje kad bi pregazio postojeći**: ako lanac stvarno
    ima i `0463` i `463` kao dvije različite poslovnice, pogađanje bi korisnika
    poslalo u krivu. Tada se ostaje bez pričuve, što je manja šteta.
    """
    izvorni = set(karta)
    kandidati: dict[tuple[str, str], list[tuple[float, float]]] = {}

    for (lanac, sifra), koordinate in karta.items():
        skraceno = sifra.lstrip("0")
        if not skraceno or skraceno == sifra:
            continue

        kljuc = (lanac, skraceno)
        if kljuc in izvorni:
            continue

        kandidati.setdefault(kljuc, []).append(koordinate)

    for kljuc, koordinate in kandidati.items():
        # Dvije različite poslovnice koje se skraćuju na isti ključ — bez pričuve.
        if len(set(koordinate)) == 1:
            karta[kljuc] = koordinate[0]


def za_poslovnicu(lanac: str, sifra: str) -> tuple[float | None, float | None]:
    """
    Koordinate poslovnice ili `(None, None)`.

    Šifra se traži i onako kako je stigla i bez vodećih nula, jer se popis i
    cjenik u tome znaju razići u oba smjera.
    """
    karta = _ucitaj()
    lanac = lanac.strip().lower()
    sifra = str(sifra).strip()

    for kandidat in (sifra, sifra.lstrip("0"), sifra.zfill(4)):
        if not kandidat:
            continue
        pogodak = karta.get((lanac, kandidat))
        if pogodak is not None:
            return pogodak

    return None, None


def pokrivenost(lanac: str) -> int:
    """Broj geokodiranih poslovnica lanca. Za dnevnik i izvještaj o zdravlju."""
    return sum(1 for (kod, _) in _ucitaj() if kod == lanac.strip().lower())
