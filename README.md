# Symulator giełdowy

Webowy symulator inwestowania w akcje z predykcją kursów. Projekt jest budowany w Django, z PostgreSQL jako bazą danych oraz Docker Compose do uruchamiania lokalnego środowiska.

## Wymagania

- Docker i Docker Compose
- Python 3.12, jeśli uruchamiasz projekt bez Dockera

## Uruchamianie w Dockerze

```powershell
docker compose up --build
```

Kontener `web` automatycznie wykona migracje bazy, a aplikacja będzie dostępna pod adresem:

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

Domyślna konfiguracja lokalna oczekuje PostgreSQL dostępnego pod `localhost:5432` z danymi:

- baza: `stock_db`
- użytkownik: `stock_user`
- hasło: `stock_password`

W Dockerze te wartości są ustawiane automatycznie w `docker-compose.yml`.

## Gdy widzisz domyślną stronę Django

Jeśli po zmianie brancha na `http://localhost:8000/` nadal pojawia się ekran "The install worked successfully", działa stary proces serwera. Zrestartuj usługę:

```powershell
docker compose restart web
```

Jeśli to nie pomoże, przebuduj kontenery:

```powershell
docker compose down
docker compose up --build
```

## Testy

```powershell
python manage.py test
```

## Zakres MVP

Pierwsza wersja aplikacji ma zapewnic:

- formularz startu symulacji z tickerem, datami i gotówką startową,
- pobieranie historycznych danych z Yahoo Finance,
- symulacje portfela dzien po dniu,
- operacje kupna, sprzedaży i czekania,
- endpointy JSON do startu i wykonywania akcji,
- prosty panel tradingowy z historia transakcji i wykresem ceny.
