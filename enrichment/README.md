# enrichment/

Podaci koji dopunjuju ono što trgovci objavljuju.

## Što je ovdje

| Datoteka     | Sadržaj                                              | Licenca |
| ------------ | ---------------------------------------------------- | ------- |
| `cities.csv` | Preslikavanje naziva gradova u kanonski oblik         | AGPL-3  |
| `stores.csv` | Geokodirane poslovnice (`lat`, `lon`) po lancu i šifri | AGPL-3  |

## Što je uklonjeno i zašto

`products.csv` iz uzvodnog projekta **nije u ovom repozitoriju**.

Uzvodni README ga izričito stavlja pod
[CC BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/), koja ne
dopušta komercijalnu upotrebu. Domiva je pretplatnički servis, pa se ti podaci ne
smiju koristiti — ni izravno ni posredno kroz izvedeni katalog.

Posao koji je `products.csv` radio — svođenje artikala na generičke pojmove —
Domiva radi sama, iz vlastitog kataloga sastojaka i vlastitog mapiranja.

**Ista rečenica iz uzvodnog READMEa ne spominje `cities.csv` ni `stores.csv`.**
Te dvije datoteke stoje pod AGPL-3 licencom cijelog projekta, pa se smiju
koristiti. AGPL obveza time ostaje unutar ovog repozitorija, koji je javan — a
Domiva ih vidi samo kroz NDJSON koji crawler zapiše.

## Zašto `stores.csv` uopće treba

Trgovci u cjenicima **ne objavljuju koordinate poslovnica**. Bez njih poslovnica
ne ulazi ni u jedan radijus, pa cijeli odjeljak „poslovnice u tvojoj blizini"
ostaje prazan.

Popis pokriva 886 poslovnica. Poslovnica koje u njemu nema dobiva `lat` i `lng`
jednake `null` — Domiva je tada prikaže u katalogu, ali ne i u pretrazi po
radijusu. To je jasno stanje, ne tiha greška.
