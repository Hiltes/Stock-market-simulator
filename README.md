# Symulator gieldowy

Webowy symulator inwestowania w akcje z predykcja kursow. Projekt jest budowany w Django, z PostgreSQL jako baza danych oraz Docker Compose do uruchamiania lokalnego srodowiska.

## Wymagania

- Docker i Docker Compose
- Python 3.12, jesli uruchamiasz projekt bez Dockera
- dostep do internetu do pobierania danych z Yahoo Finance

Nie jest wymagane konto ani klucz API. Dane sa pobierane przez biblioteke `yfinance`, a wykresy korzystaja z Chart.js ladowanego z CDN.

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

## Gdy widzisz domyslna strone Django

Jesli po zmianie brancha na `http://localhost:8000/` nadal pojawia sie ekran "The install worked successfully", dziala stary proces serwera. Zrestartuj usluge:

```powershell
docker compose restart web
```

Jesli to nie pomoze, przebuduj kontenery:

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

## Jak dziala aplikacja

1. Uzytkownik wybiera ticker, zakres dat i gotowke poczatkowa.
2. Backend pobiera historyczne dane gieldowe z Yahoo Finance.
3. Backend pobiera tez niewidoczny bufor danych sprzed daty startu, uzywany wylacznie do treningu modelu.
4. Dane sa przetwarzane na cechy ML: opoznione ceny, zmiany procentowe, srednie kroczace, zmiennosc i zmiany wolumenu.
5. System trenuje modele Random Forest na danych historycznych dostepnych do aktualnego dnia symulacji.
6. Frontend pokazuje kolejne dni notowan, predykcje, dane OHLC, wolumen, portfel i historie decyzji.
7. Uzytkownik wykonuje decyzje: kupno, sprzedaz albo czekanie.
8. Po zakonczeniu symulacji aplikacja pokazuje podsumowanie i porownanie ze strategia "kup i trzymaj".

## API

Frontend komunikuje sie z backendem przez lokalne endpointy Django:

- `POST /api/start` - uruchamia symulacje na podstawie `ticker`, `start_date`, `end_date`, `initial_cash`
- `POST /api/start` przyjmuje tez parametry modelu `training_window_days` i `lookback_days`
- `POST /api/decision` - wykonuje decyzje `BUY`, `SELL` albo `HOLD` z polem `shares` i odslania kolejny dzien
- `GET /api/history` - pobiera historie decyzji i wartosci portfela

Przykladowy start:

```json
POST /api/start
{
  "ticker": "AAPL",
  "start_date": "2024-01-01",
  "end_date": "2024-03-01",
  "initial_cash": "10000",
  "training_window_days": 60,
  "lookback_days": 3
}
```

Przykladowa decyzja:

```json
POST /api/decision
{
  "action": "BUY",
  "shares": 5
}
```

Odpowiedz API zawiera tylko aktualnie odsloniety dzien (`current_day` i `ohlcv`), stan portfela (`cash`, `shares`, `portfolio_value`, `profit_loss`) oraz historie wykonanych transakcji. Backend nie zwraca przyszlych dni przed wykonaniem kolejnego kroku. Predykcja modelu jest liczona w trybie walk-forward: moze korzystac z niewidocznego bufora danych sprzed daty startu oraz z dni odslonietych do biezacego kroku, ale nie korzysta z przyszlych dni symulacji. Dla zgodnosci zostawiony jest tez alias `POST /api/action`.

Frontend pokazuje dodatkowo:

- podstawowe statystyki odslonietych danych, bez podgladu przyszlosci
- sekcje `predykcja vs rzeczywistosc`, uzupelniana po kazdym kroku, gdy znany jest juz faktyczny wynik kolejnego dnia

## Model ML

Projekt wykorzystuje:

- `RandomForestRegressor` do predykcji nastepnej ceny zamkniecia
- `RandomForestClassifier` do oceny kierunku zmiany ceny
- walk-forward training bez wykorzystywania przyszlych danych wzgledem aktualnego kroku symulacji
- niewidoczny bufor historyczny sprzed daty startu, zeby Random Forest mogl dzialac od pierwszego dnia symulacji

Prezentowane metryki:

- regresja: `MAE`, `RMSE`, `R2`
- klasyfikacja: `accuracy`, `precision`, `recall`, `F1`

Predykcje maja charakter orientacyjny. Dane gieldowe sa zaszumione i model nie gwarantuje zysku.

## Zalozenia i ograniczenia

- aplikacja obsluguje cztery tickery demo: `AAPL`, `TSLA`, `MSFT`, `NVDA`
- symulacja nie uwzglednia kosztow transakcyjnych
- symulacja nie uwzglednia poslizgu cenowego ani prowizji brokera
- transakcje uzytkownika nie maja wplywu na rynek ani na dane historyczne
- decyzje wykonywane sa po cenie zamkniecia aktualnie odslonietego dnia
- przyszle dane pozostaja ukryte do momentu wykonania kolejnego kroku
- metryki i predykcje modelu maja charakter pomocniczy, nie inwestycyjnej rekomendacji
- jesli mimo bufora historycznego danych jest zbyt malo do treningu Random Forest, aplikacja pokazuje predykcje bazowa

## Zakres funkcjonalny

Aplikacja zapewnia:

- formularz startu symulacji z tickerem, datami i gotowka startowa
- automatyczna walidacje zakresu dat
- pobieranie historycznych danych z Yahoo Finance
- preprocessing danych pod model ML
- predykcje ceny i kierunku zmiany
- symulacje portfela dzien po dniu
- operacje kupna, sprzedazy i czekania
- endpointy JSON do startu i wykonywania akcji
- panel tradingowy z historia transakcji
- panel `predykcja vs rzeczywistosc`
- podstawowe statystyki odslonietej czesci szeregu
- wykres otwarcia, maksimum, minimum, zamkniecia i wolumenu
- metryki jakosci modelu
- podsumowanie koncowe symulacji
