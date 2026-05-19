# Stock Market Simulator

Webowy symulator inwestowania w akcje z predykcja kursow. Projekt jest budowany w Django, z PostgreSQL jako baza danych oraz Docker Compose do uruchamiania lokalnego srodowiska.

## Wymagania

- Docker i Docker Compose
- Python 3.12, jesli uruchamiasz projekt bez Dockera

## Uruchamianie w Dockerze

```powershell
docker compose up --build
```

Kontener `web` automatycznie wykona migracje bazy, a aplikacja bedzie dostepna pod adresem:

```text
http://localhost:8000/
```

Migracje mozna tez wykonac recznie:

```powershell
docker compose exec web python manage.py migrate
```

## Uruchamianie lokalne

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Domyslna konfiguracja lokalna oczekuje PostgreSQL dostepnego pod `localhost:5432` z danymi:

- baza: `stock_db`
- uzytkownik: `stock_user`
- haslo: `stock_password`

W Dockerze te wartosci sa ustawiane automatycznie w `docker-compose.yml`.

## Testy

```powershell
python manage.py test
```

## Zakres MVP

Pierwsza wersja aplikacji ma zapewnic:

- formularz startu symulacji z tickerem, datami i gotowka startowa,
- pobieranie historycznych danych z Yahoo Finance,
- symulacje portfela dzien po dniu,
- operacje `BUY`, `SELL` i `HOLD`,
- endpointy JSON do startu i wykonywania akcji,
- prosty panel tradingowy z historia transakcji i wykresem ceny.
