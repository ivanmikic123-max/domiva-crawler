"""
Zaštita od preusmjeravanja na privatne mreže.

`SECURITY.md`, odjeljak 3. Crawler po definiciji ide na tuđe adrese, i to na
adrese koje se mijenjaju bez najave. Uzvodni klijent ima `follow_redirects=True`,
što znači da lanac koji objavi `https://cjenik.example.hr/preuzmi` s
preusmjeravanjem na `http://169.254.169.254/latest/meta-data/` natjera crawler da
dohvati metapodatke poslužitelja i zapiše ih kao cjenik.

Provjera stoji na razini prijenosnog sloja, ne poziva. Tako je pokrivena svaka
karika lanca preusmjeravanja, uključujući onu koju nitko nije napisao izričito —
a to je upravo ona koja propušta.

**Granica koju treba znati:** ime se razrješava pri provjeri, a `httpx` ga
razrješava ponovno pri spajanju. Poslužitelj imena koji između ta dva trenutka
vrati drugu adresu (DNS rebinding) provuče se. Potpuna obrana traži spajanje na
provjerenu adresu s ručno postavljenim `Host` zaglavljem i SNI-jem, što lomi TLS
kod dijela lanaca. Ovdje se svjesno staje na razini koja hvata preusmjeravanja i
pogrešno konfigurirana imena; mrežna izolacija spremnika pokriva ostatak.
"""

from __future__ import annotations

import ipaddress
import socket
from logging import getLogger

import httpx

logger = getLogger(__name__)

DOPUSTENE_SHEME = {"http", "https"}


class NedopustenoOdrediste(httpx.RequestError):
    """Odredište je izvan javne mreže ili nije dohvatljivo."""


def _adrese(ime: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        podaci = socket.getaddrinfo(ime, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as greska:
        raise NedopustenoOdrediste(f"Ime {ime} se ne razrješava: {greska}") from greska

    adrese = []
    for _, _, _, _, sockaddr in podaci:
        try:
            adrese.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue

    return adrese


def provjeri_odrediste(url: httpx.URL) -> None:
    """
    Baca kad odredište nije javna adresa.

    `is_global` pokriva sve što treba jednim potezom: petlju (127.0.0.0/8, ::1),
    privatne raspone (10/8, 172.16/12, 192.168/16, fc00::/7), vezu (169.254/16 —
    odakle se čitaju metapodaci oblaka) i rezervirano.
    """
    if url.scheme not in DOPUSTENE_SHEME:
        raise NedopustenoOdrediste(f'Shema „{url.scheme}" nije dopuštena.')

    ime = url.host
    if not ime:
        raise NedopustenoOdrediste("Adresa nema ime poslužitelja.")

    adrese = _adrese(ime, url.port or (443 if url.scheme == "https" else 80))
    if not adrese:
        raise NedopustenoOdrediste(f"Ime {ime} nema nijednu upotrebljivu adresu.")

    for adresa in adrese:
        if not adresa.is_global:
            raise NedopustenoOdrediste(
                f"Ime {ime} pokazuje na adresu izvan javne mreže ({adresa})."
            )


class ZasticeniPrijenos(httpx.BaseTransport):
    """Omotač koji svaki zahtjev propušta tek nakon provjere odredišta."""

    def __init__(self, unutarnji: httpx.BaseTransport) -> None:
        self._unutarnji = unutarnji

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        provjeri_odrediste(request.url)
        return self._unutarnji.handle_request(request)

    def close(self) -> None:
        self._unutarnji.close()


def sigurni_klijent(
    timeout: float = 30.0,
    verify: bool = True,
    user_agent: str | None = None,
) -> httpx.Client:
    """
    `httpx.Client` koji ne ide na privatne mreže.

    Zamjenjuje klijent iz `BaseCrawler`. Ostale postavke — vremensko ograničenje,
    provjera certifikata, praćenje preusmjeravanja — ostaju kakve su bile, jer
    dio lanaca bez njih ne radi.
    """
    zaglavlja = {"User-Agent": user_agent} if user_agent else None

    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        verify=verify,
        headers=zaglavlja,
        transport=ZasticeniPrijenos(httpx.HTTPTransport(verify=verify)),
    )
