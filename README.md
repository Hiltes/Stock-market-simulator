# Symulator giełdowy

Webowy symulator inwestowania w akcje z predykcją kursów. Projekt jest budowany w Django, z PostgreSQL jako bazą danych oraz Docker Compose do uruchamiania lokalnego środowiska.

## Wymagania

- Docker i Docker Compose
- Python 3.12, jeśli uruchamiasz projekt bez Dockera
- dostęp do internetu do pobierania danych z Yahoo Finance

Nie jest wymagane konto ani klucz API. Dane są pobierane przez bibliotekę `yfinance`, a wykresy korzystają z Chart.js ładowanego z CDN.

## Uruchamianie w Dockerze

```powershell
docker compose up --build
```

Kontener `web` automatycznie wykona migracje bazy, a aplikacja będzie dostępna pod adresem:

```text
http://localhost:8000/
```

Migracje można też wykonać ręcznie:

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

W Dockerze:

```powershell
docker compose exec web python manage.py test
```

## Jak działa aplikacja

1. Użytkownik wybiera ticker, zakres dat i gotówkę początkową.
2. Backend pobiera historyczne dane giełdowe z Yahoo Finance.
3. Dane są przetwarzane na cechy ML: opóźnione ceny, zmiany procentowe, średnie kroczące, zmienność i zmiany wolumenu.
4. System trenuje modele Random Forest na początkowej części szeregu czasowego.
5. Frontend pokazuje kolejne dni notowań, predykcję, dane OHLC, wolumen, portfel i historię decyzji.
6. Użytkownik wykonuje decyzje: kupno, sprzedaż albo czekanie.
7. Po zakończeniu symulacji aplikacja pokazuje podsumowanie i porównanie ze strategią "kup i trzymaj".

## API

Frontend komunikuje się z backendem przez lokalne endpointy Django:

- `POST /api/start/` - start symulacji i przygotowanie danych oraz modelu,
- `POST /api/action/` - wykonanie decyzji użytkownika i przejście do kolejnego dnia,
- `GET /api/history/` - pobranie historii decyzji i wartości portfela.

## Model ML

Projekt wykorzystuje:

- `RandomForestRegressor` do predykcji następnej ceny zamknięcia,
- `RandomForestClassifier` do oceny kierunku zmiany ceny.

Prezentowane metryki:

- regresja: `MAE`, `RMSE`, `R2`,
- klasyfikacja: `accuracy`, `precision`, `recall`, `F1`.

Predykcje mają charakter orientacyjny. Dane giełdowe są zaszumione i model nie gwarantuje zysku.

## Zakres funkcjonalny

Aplikacja zapewnia:

- formularz startu symulacji z tickerem, datami i gotówką startową,
- automatyczną walidację zakresu dat,
- pobieranie historycznych danych z Yahoo Finance,
- preprocessing danych pod model ML,
- predykcję ceny i kierunku zmiany,
- symulację portfela dzień po dniu,
- operacje kupna, sprzedaży i czekania,
- endpointy JSON do startu i wykonywania akcji,
- panel tradingowy z historią transakcji,
- wykres otwarcia, maksimum, minimum, zamknięcia i wolumenu,
- metryki jakości modelu,
- podsumowanie końcowe symulacji.
