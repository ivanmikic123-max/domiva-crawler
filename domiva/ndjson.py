"""
Izlaz u NDJSON obliku koji Domiva očekuje.

Ovo je **jedina** dodirna točka podataka između crawlera i Domive. Ista shema
postoji i s druge strane, u `packages/shared/src/sheme/cjenik.ts`; kad se ovdje
mijenja polje, mijenja se i ondje.

Pravilo koje se ne krši: **polje koje lanac ne objavljuje ostaje `null`.**
Razlika između „nema akcijske cijene" i „akcijska cijena jednaka je redovnoj"
mora preživjeti put od trgovca do korisnika. Izmišljena nula ju briše.
"""

from __future__ import annotations

import gzip
import json
import re
from decimal import Decimal, InvalidOperation
from logging import getLogger
from pathlib import Path
from typing import Any, Iterable

from crawler.store.models import Store
from domiva.koordinate import za_poslovnicu

logger = getLogger(__name__)


# Jedinice koje Domiva poznaje. Sve ostalo je `null` — pogrešna jedinica je
# gora od nikakve, jer se u planeru pretvara u krivu količinu za kupnju.
JEDINICE = {
    "g": "g",
    "gr": "g",
    "gram": "g",
    "grama": "g",
    "kg": "kg",
    "kgm": "kg",
    "kilogram": "kg",
    "ml": "ml",
    "mililitar": "ml",
    "l": "l",
    "lit": "l",
    "litra": "l",
    "kom": "kom",
    "komad": "kom",
    "kom.": "kom",
    "pce": "kom",
}


def _broj(vrijednost: Any) -> float | None:
    """
    Broj iz onoga što je trgovac upisao.

    Cjenici dolaze kao CSV i XML iz tridesetak različitih sustava; količina zna
    biti `1`, `1,5`, `0.500`, `1 kg` ili prazna. Sve što se ne da pročitati
    postaje `null` umjesto da se pogađa.
    """
    if vrijednost is None:
        return None

    tekst = str(vrijednost).strip()
    if not tekst:
        return None

    # Zadrži prvi broj; `1,5 kg` → `1,5`.
    pogodak = re.search(r"\d+(?:[.,]\d+)?", tekst)
    if not pogodak:
        return None

    try:
        broj = float(pogodak.group(0).replace(",", "."))
    except ValueError:
        return None

    if broj <= 0:
        return None

    return broj


def _jedinica(vrijednost: Any) -> str | None:
    if vrijednost is None:
        return None

    kljuc = str(vrijednost).strip().lower()
    return JEDINICE.get(kljuc)


def _cijena(vrijednost: Decimal | float | str | None) -> float | None:
    """
    Cijena u eurima, na dvije decimale.

    Domiva je pretvara u cijele cente. Ovdje ostaje decimalna jer takva stoji u
    cjeniku, a pretvorba pripada onoj strani koja podatke sprema.
    """
    if vrijednost is None:
        return None

    try:
        broj = Decimal(str(vrijednost))
    except (InvalidOperation, ValueError):
        return None

    if broj < 0:
        return None

    return float(round(broj, 2))


def _ean(vrijednost: Any) -> str | None:
    """
    EAN, ako je uopće nalik na EAN.

    Kontrolna se znamenka **ne provjerava**. Neispravan EAN i dalje je koristan
    kao ključ prema Open Food Factsu, a promašaj ondje ne košta ništa. Odbaciti
    ga značilo bi ostati bez slike i nutritivnih podataka za artikl koji ih ima.
    """
    if vrijednost is None:
        return None

    znamenke = re.sub(r"\D", "", str(vrijednost))
    if not 8 <= len(znamenke) <= 14:
        return None

    return znamenke


def _neprazno(vrijednost: Any, najvise: int) -> str | None:
    if vrijednost is None:
        return None

    tekst = str(vrijednost).strip()
    if not tekst:
        return None

    return tekst[:najvise]


def redak_cjenika(store: Store, proizvod: Any) -> dict[str, Any]:
    """Jedan artikl u jednoj poslovnici."""
    return {
        "store_code": str(store.store_id).strip(),
        "external_code": str(proizvod.product_id).strip(),
        "ean": _ean(proizvod.barcode),
        "name": _neprazno(proizvod.product, 500) or "(bez naziva)",
        "brand": _neprazno(proizvod.brand, 200),
        "net_quantity": _broj(proizvod.quantity),
        "unit": _jedinica(proizvod.unit),
        "category_raw": _neprazno(proizvod.category, 300),
        "price": _cijena(proizvod.price),
        "unit_price": _cijena(proizvod.unit_price),
        "special_price": _cijena(proizvod.special_price),
        "best_price_30": _cijena(proizvod.best_price_30),
        "anchor_price": _cijena(proizvod.anchor_price),
    }


def redak_poslovnice(store: Store) -> dict[str, Any]:
    """
    Jedna poslovnica.

    Koordinate ne dolaze iz cjenika — trgovci ih ne objavljuju — nego iz
    `enrichment/stores.csv`. Poslovnica koje ondje nema dobiva `null` i time
    ostaje vidljiva u katalogu, ali izvan pretrage po radijusu.
    """
    lat, lng = za_poslovnicu(store.chain, store.store_id)

    return {
        "store_code": str(store.store_id).strip(),
        "name": _neprazno(store.name, 300) or f"{store.chain} {store.city}".strip(),
        "address": _neprazno(store.street_address, 300),
        "city": _neprazno(store.city, 120),
        "zip_code": _neprazno(store.zipcode, 20),
        "lat": lat,
        "lng": lng,
    }


def _zapisi(putanja: Path, redci: Iterable[dict[str, Any]], stlaci: bool) -> int:
    """
    Zapisuje NDJSON, redak po redak.

    Ne slaže se cijeli sadržaj u memoriju: cjenik velikog lanca ima stotine
    tisuća redaka, a crawler se vrti pored ostalih.
    """
    putanja.parent.mkdir(parents=True, exist_ok=True)

    otvori = (
        (
            lambda: gzip.open(
                putanja.with_suffix(putanja.suffix + ".gz"), "wt", encoding="utf-8"
            )
        )
        if stlaci
        else (lambda: putanja.open("w", encoding="utf-8"))
    )

    broj = 0
    with otvori() as izlaz:
        for redak in redci:
            izlaz.write(json.dumps(redak, ensure_ascii=False, separators=(",", ":")))
            izlaz.write("\n")
            broj += 1

    return broj


def zapisi_lanac(
    korijen: Path,
    datum: str,
    lanac: str,
    stores: list[Store],
    stlaci: bool = True,
) -> tuple[int, int]:
    """
    Zapisuje cjenik i popis poslovnica jednog lanca.

    Ključevi su isti kao u S3 (`raw/{datum}/{lanac}/…`), pa je prelazak s diska
    na objektnu pohranu samo promjena odredišta.

    Vraća `(broj cijena, broj poslovnica)` — te brojke idu u obavijest Domivi,
    koja tako može provjeriti je li sve stiglo.
    """
    mapa = korijen / "raw" / datum / lanac

    # Artikl bez cijene nema što raditi u cjeniku; sve ostalo smije nedostajati.
    cijene = (
        redak_cjenika(store, proizvod)
        for store in stores
        for proizvod in store.items
        if _cijena(proizvod.price) is not None
    )

    broj_cijena = _zapisi(mapa / "prices.ndjson", cijene, stlaci)
    broj_poslovnica = _zapisi(
        mapa / "stores.ndjson", (redak_poslovnice(s) for s in stores), stlaci
    )

    logger.info(
        "%s %s: %d cijena, %d poslovnica → %s",
        lanac,
        datum,
        broj_cijena,
        broj_poslovnica,
        mapa,
    )

    return broj_cijena, broj_poslovnica
