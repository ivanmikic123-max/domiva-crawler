"""
Dodatak koji Domiva dodaje uzvodnom crawleru.

Sve što je ovdje je novo; sami crawleri po lancima ostaju kakvi jesu. Razlog je
praktičan koliko i pravni: uzvodni projekt se i dalje razvija, pa se izmjene u
`crawler/store/*.py` žele moći povući bez sukoba.

Tri stvari:

  · `ndjson`   — izlaz u obliku koji Domiva očekuje
  · `dohvat`   — zaštita od preusmjeravanja na privatne mreže
  · `obavijest` — javljanje Domivi da je lanac gotov
"""
