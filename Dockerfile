# Crawler kao zaseban servis.
#
# Ne dijeli sliku s Domivom i ne vidi njezinu bazu. Jedino što mu treba je izlaz
# na internet, mjesto za zapis i adresa API-ja kojoj javlja da je gotov.

FROM python:3.13-slim AS temelj

# `lxml` traži prevoditelj samo kad kotačić za platformu ne postoji; ostalo je
# potrebno za TLS prema lancima koji još stoje na starijim postavkama.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY crawler ./crawler
COPY common ./common
COPY domiva ./domiva

RUN pip install --no-cache-dir .

# Ne radi kao root. Crawler obrađuje sadržaj s tuđih poslužitelja, pa je to
# jedino mjesto u sustavu gdje tuđi podaci dolaze u dodir s parserima.
RUN useradd --create-home --uid 10001 crawler \
    && mkdir -p /podaci \
    && chown -R crawler:crawler /podaci
USER crawler

VOLUME ["/podaci"]

ENTRYPOINT ["crawl"]
CMD ["--all", "--output", "/podaci"]
