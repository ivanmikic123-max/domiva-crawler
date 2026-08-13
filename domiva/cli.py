"""
Naredbeni redak crawlera.

    crawl --chain lidl --date 2026-08-11
    crawl --all
    crawl --list

Zaseban je od uzvodnog `crawler.cli.crawl`, koji zapisuje CSV i ZIP za svoj
poslužitelj. Ovaj zapisuje NDJSON u obliku koji Domiva očekuje i javlja joj kad
je lanac gotov.

Uzvodni ostaje netaknut, pa se njegove izmjene i dalje daju povući bez sukoba.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from time import time
from zoneinfo import ZoneInfo

from crawler.crawl import CRAWLERS
from domiva.ndjson import zapisi_lanac
from domiva.obavijest import ObavijestNijePoslana, javi_da_je_lanac_gotov

logger = logging.getLogger("domiva")

ZONA = ZoneInfo("Europe/Zagreb")


def danas() -> str:
    """
    Današnji datum po zagrebačkom danu.

    Ne po UTC-u. Crawler se vrti rano ujutro, a spremnik radi u UTC-u — ljeti bi
    pokretanje u 01:30 po Zagrebu zapisalo cjenik pod jučerašnji datum, i Domiva
    ga sljedeći dan ne bi našla.
    """
    return datetime.now(ZONA).strftime("%Y-%m-%d")


def _datum(tekst: str) -> str:
    try:
        datetime.strptime(tekst, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError("Datum mora biti u obliku YYYY-MM-DD.")
    return tekst


def _postavi_dnevnik(razina: str) -> None:
    logging.basicConfig(
        level=getattr(logging, razina.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def obradi_lanac(lanac: str, datum: str, izlaz: Path, javi: bool) -> tuple[int, int]:
    """
    Povlači jedan lanac i zapisuje ga.

    Baca kad lanac ne uspije. Odluku što s tim radi donosi pozivatelj — kod
    `--all` ostali lanci idu dalje, jer ispad jednog trgovca ne smije ostaviti
    Domivu bez ostalih 28.
    """
    razred = CRAWLERS.get(lanac)
    if razred is None:
        raise ValueError(f"Nepoznat lanac: {lanac}")

    pocetak = time()
    stores = razred().get_all_products(date.fromisoformat(datum))

    if not stores:
        raise RuntimeError(f"Lanac {lanac} nije vratio nijednu poslovnicu.")

    broj_cijena, broj_poslovnica = zapisi_lanac(izlaz, datum, lanac, stores)

    if broj_cijena == 0:
        # Prazan cjenik s poslovnicama znači promijenjen oblik izvora, ne prazan
        # dan. Zapisati ga kao uspjeh značilo bi da Domiva sutra prikaže lanac
        # bez ijednog artikla.
        raise RuntimeError(f"Lanac {lanac} nije dao nijednu cijenu.")

    logger.info(
        "%s: %d cijena u %d poslovnica, %.1f s",
        lanac,
        broj_cijena,
        broj_poslovnica,
        time() - pocetak,
    )

    if javi:
        try:
            javi_da_je_lanac_gotov(lanac, datum, broj_cijena, broj_poslovnica)
        except ObavijestNijePoslana as greska:
            # Podaci su zapisani; Domiva ih pokupi i po rasporedu u 08:00.
            # Neuspjelo javljanje nije razlog da se lanac vodi kao pao.
            logger.warning("%s: %s", lanac, greska)

    return broj_cijena, broj_poslovnica


def main() -> int:
    razclanik = argparse.ArgumentParser(
        prog="crawl",
        description="Povlači cjenike hrvatskih trgovačkih lanaca i zapisuje ih kao NDJSON.",
    )
    skupina = razclanik.add_mutually_exclusive_group(required=True)
    skupina.add_argument("--chain", help="Šifra lanca (npr. lidl).")
    skupina.add_argument("--all", action="store_true", help="Svi podržani lanci.")
    skupina.add_argument("--list", action="store_true", help="Ispiši lance i izađi.")

    razclanik.add_argument("--date", type=_datum, default=None, help="YYYY-MM-DD, zadano danas.")
    razclanik.add_argument(
        "--output",
        type=Path,
        default=Path("./podaci/sirovo"),
        help="Korijen pohrane. Ključevi su isti kao u S3.",
    )
    razclanik.add_argument(
        "--no-notify",
        action="store_true",
        help="Ne javljaj Domivi. Korisno pri ispitivanju jednog lanca.",
    )
    razclanik.add_argument("--log-level", default="info")

    argumenti = razclanik.parse_args()
    _postavi_dnevnik(argumenti.log_level)

    if argumenti.list:
        for lanac in sorted(CRAWLERS):
            print(lanac)
        return 0

    datum = argumenti.date or danas()
    lanci = sorted(CRAWLERS) if argumenti.all else [argumenti.chain]
    javi = not argumenti.no_notify

    pali: list[str] = []
    ukupno_cijena = 0

    for lanac in lanci:
        try:
            broj_cijena, _ = obradi_lanac(lanac, datum, argumenti.output, javi)
            ukupno_cijena += broj_cijena
        except Exception as greska:  # noqa: BLE001 — ispad lanca ne ruši ostale
            logger.error("%s nije prošao: %s", lanac, greska, exc_info=True)
            pali.append(lanac)

    logger.info(
        "Gotovo za %s: %d lanaca, %d cijena, %d palo%s",
        datum,
        len(lanci) - len(pali),
        ukupno_cijena,
        len(pali),
        f" ({', '.join(pali)})" if pali else "",
    )

    # Izlazni kod govori raspoređivaču je li sve prošlo. Jedan lanac koji je pao
    # nije razlog za `1` kad je traženo samo njega — ondje jest.
    if pali and len(pali) == len(lanci):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
