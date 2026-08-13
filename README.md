# domiva-crawler

Preuzimanje cjenika hrvatskih trgovačkih lanaca i zapisivanje u NDJSON.

Fork projekta [cijene-api](https://github.com/senko/cijene-api) autora Senka
Rašića i suradnika, pod istom **AGPL-3.0** licencom. Vidi [NOTICE](NOTICE) za
popis izmjena i [LICENSE](LICENSE) za cjelovit tekst licence.

---

## Što ovaj repozitorij jest i što nije

**Jest:** program koji jednom dnevno povuče cjenike koje trgovci objavljuju po
Odluci NN 75/2025 i zapiše ih u dogovorenom obliku.

**Nije:** dio Domive. Domiva je zaseban, zatvoreni projekt i ovaj kod **ne
uvozi**. Dodiruju se na točno dva mjesta:

1. **Datoteke u objektnoj pohrani**

   ```
   raw/{datum}/{lanac}/prices.ndjson
   raw/{datum}/{lanac}/stores.ndjson
   ```

2. **Jedan HTTP poziv** — `POST /internal/ingest/chain-ready`, autoriziran
   zajedničkom tajnom, koji samo javlja da je lanac gotov.

Ta granica nije stvar ukusa. AGPL-3.0 traži da se izvedeno djelo objavi pod istom
licencom; držanjem crawlera u zasebnom procesu koji s Domivom razgovara preko
podataka, obveze ostaju unutar ovog repozitorija — koji je javan.

## Upotreba

```bash
crawl --list                              # podržani lanci
crawl --chain lidl --date 2026-08-11      # jedan lanac
crawl --all                               # svi lanci, današnji datum
crawl --chain lidl --no-notify            # bez javljanja Domivi
```

Zadani datum je **današnji po zagrebačkom danu**, ne po UTC-u.

Ispad jednog lanca ne zaustavlja ostale. Izlazni kod je `1` samo kad nijedan
lanac nije prošao.

### Okruženje

| Varijabla                | Značenje                                              |
| ------------------------ | ----------------------------------------------------- |
| `DOMIVA_API_URL`         | Adresa Domivinog API-ja. Bez nje se javljanje preskače |
| `DOMIVA_CRAWLER_SECRET`  | Zajednička tajna, najmanje 32 znaka                    |

Bez te dvije varijable crawler i dalje radi i zapisuje datoteke — samo ne javlja.
To je namjerno: mora se dati pokrenuti i ispitati bez Domive.

## Oblik zapisa

Jedan JSON po retku, bez zareza i uglatih zagrada. Polje koje lanac **ne
objavljuje ostaje `null`** — nikad nula, nikad prazan niz.

`prices.ndjson`:

```json
{"store_code":"1041","external_code":"LD-100241","ean":"3850001000017",
 "name":"Mlijeko trajno 2,8% m.m.","brand":"Milbona",
 "net_quantity":1.0,"unit":"l","category_raw":"mliječni proizvodi",
 "price":1.09,"unit_price":1.09,"special_price":null,
 "best_price_30":0.99,"anchor_price":1.05}
```

`stores.ndjson`:

```json
{"store_code":"1041","name":"Lidl Zagreb — Zavrtnica","address":"Zavrtnica 17",
 "city":"Zagreb","zip_code":"10000","lat":45.7982,"lng":15.9954}
```

Ista je shema opisana i s Domivine strane, u `packages/shared/src/sheme/cjenik.ts`.
Kad se ovdje mijenja polje, mijenja se i ondje — inače Domiva odbije cijeli lanac.

### Koordinate poslovnica

Trgovci ih u cjenicima **ne objavljuju**. Dolaze iz
[`enrichment/stores.csv`](enrichment/README.md), koji je pod AGPL-3 licencom
projekta — za razliku od `products.csv`, koji je uklonjen jer je pod
CC BY-NC-SA.

Pokrivenost je neujednačena i to treba znati:

| Lanac    | Poslovnica |     | Lanac       | Poslovnica |
| -------- | ---------: | --- | ----------- | ---------: |
| Konzum   |        286 |     | Tommy       |         79 |
| Plodine  |        232 |     | Kaufland    |         50 |
| Spar     |        143 |     | KTC         |         34 |
| Lidl     |        110 |     | Eurospin    |         31 |
| Studenac |         18 |     | Trgocentar  |          1 |

Ukupno **984 poslovnice u 10 lanaca**. Preostalih 19 lanaca nema nijednu
geokodiranu poslovnicu; njihovi artikli su vidljivi u katalogu cijena, ali ne i
u pretrazi po radijusu. To je jasno stanje, ne tiha greška.

## Sigurnost

Crawler ide na tuđe adrese koje se mijenjaju bez najave, pa svaki HTTP zahtjev
prolazi kroz provjeru odredišta ([`domiva/dohvat.py`](domiva/dohvat.py)):
odbijaju se petlja, privatni rasponi i adresa `169.254.169.254`, s koje se u
oblaku čitaju vjerodajnice poslužitelja.

Provjera stoji na razini prijenosnog sloja, pa vrijedi za **svaku kariku lanca
preusmjeravanja**, ne samo za prvu adresu.

Granica koju treba znati: ime se razrješava pri provjeri, a `httpx` ga razrješava
ponovno pri spajanju, pa se DNS rebinding provuče. Ostatak pokriva mrežna
izolacija spremnika.

## Razvoj

```bash
uv sync
uv run pytest
uv run ruff check .
```

## Praćenje uzvodnog projekta

Uzvodni repozitorij je pod udaljenom oznakom `upstream`; guranje na njega je
onemogućeno.

```bash
git fetch upstream
git merge upstream/main
```

Izmjene Domive su namjerno skupljene u `domiva/`, uz jednu jedinu promjenu u
uzvodnom kodu — zamjenu HTTP klijenta u `crawler/store/base.py`. Sve ostalo u
`crawler/` i `common/` ostaje netaknuto, pa se uzvodne izmjene povlače bez
sukoba.
