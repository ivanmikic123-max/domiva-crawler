"""
Javljanje Domivi da je lanac gotov.

Poziv **ne nosi podatke** — samo kaže koji je lanac za koji datum zapisan i
koliko redaka. Da nosi cjenik, zajednička tajna postala bi jedina prepreka između
vanjskog svijeta i Domivinih cijena; ovako je najgore što napadač s ukradenom
tajnom postiže to da Domiva pročita datoteke koje ionako sama piše.

Brojke redaka nisu ukras: Domiva njima provjerava je li pročitala sve što je
crawler zapisao. Prekinut prijenos tako ne prođe kao uspješan uvoz.
"""

from __future__ import annotations

import os
from logging import getLogger

import httpx

logger = getLogger(__name__)

ZAGLAVLJE_TAJNE = "X-Domiva-Crawler-Secret"


class ObavijestNijePoslana(RuntimeError):
    """Domiva nije prihvatila obavijest."""


def javi_da_je_lanac_gotov(
    lanac: str,
    datum: str,
    broj_cijena: int,
    broj_poslovnica: int,
    api_url: str | None = None,
    tajna: str | None = None,
    timeout: float = 10.0,
) -> None:
    """
    Šalje `POST /internal/ingest/chain-ready`.

    Bez postavljene adrese ili tajne se **preskače uz zapis u dnevnik**, ne puca.
    Crawler se mora dati pokrenuti sam, bez Domive — inače se ne da ni ispitati
    ni popraviti kad lanac promijeni oblik cjenika.
    """
    api_url = api_url or os.environ.get("DOMIVA_API_URL", "")
    tajna = tajna or os.environ.get("DOMIVA_CRAWLER_SECRET", "")

    if not api_url or not tajna:
        logger.info(
            "DOMIVA_API_URL ili DOMIVA_CRAWLER_SECRET nisu postavljeni — "
            "ne javljam da je %s gotov.",
            lanac,
        )
        return

    odrediste = f"{api_url.rstrip('/')}/internal/ingest/chain-ready"

    try:
        odgovor = httpx.post(
            odrediste,
            headers={ZAGLAVLJE_TAJNE: tajna},
            json={
                "chain": lanac,
                "date": datum,
                "price_rows": broj_cijena,
                "store_rows": broj_poslovnica,
            },
            timeout=timeout,
        )
    except httpx.RequestError as greska:
        raise ObavijestNijePoslana(f"Domiva nije dostupna: {greska}") from greska

    if odgovor.status_code >= 400:
        # Tijelo odgovora se **ne ispisuje**. Ako je poziv promašio odredište i
        # završio negdje drugdje, u dnevniku ne treba tuđi sadržaj.
        raise ObavijestNijePoslana(
            f"Domiva je odbila obavijest za {lanac}: HTTP {odgovor.status_code}"
        )

    logger.info("Domiva je obaviještena da je %s gotov za %s.", lanac, datum)
