# Stock Market Simulator

Interaktywna aplikacja webowa w Django do symulacji inwestowania w akcje z wykorzystaniem danych historycznych i docelowo predykcji ML.

## Aktualny status

Projekt jest na etapie fundamentu technicznego:

- Django 6,
- aplikacja `main`,
- PostgreSQL w Dockerze,
- Docker Compose do uruchamiania środowiska.

Docelowo aplikacja ma pozwalać użytkownikowi wybrać spółkę i zakres dat, przechodzić przez dane giełdowe dzień po dniu, wykonywać decyzje `buy`, `sell`, `hold` oraz obserwować wpływ decyzji na portfel.

## Uruchomienie przez Docker

Wymagania:

- Docker Desktop,
- Git.

Start aplikacji:

```powershell
docker compose up --build
```

Pierwsze przygotowanie bazy lub migracje po zmianach modeli:

```powershell
docker compose exec web python manage.py migrate
```

Aplikacja:

```text
http://localhost:8000/
```

Panel admina Django:

```text
http://localhost:8000/admin/
```

Zatrzymanie środowiska:

```powershell
docker compose down
```

## Uruchomienie lokalne

Opcjonalnie można utworzyć lokalne środowisko Pythona:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Uwaga: domyślna konfiguracja używa PostgreSQL. Najprościej uruchamiać bazę przez Docker Compose.

## Plan najbliższych prac

1. Dodać własną stronę startową aplikacji.
2. Dodać endpointy API do startu symulacji i wykonywania decyzji.
3. Dodać moduł pobierania danych z Yahoo Finance.
4. Dodać silnik portfela z operacjami `buy`, `sell`, `hold`.
5. Dodać podstawowy panel symulacji.
6. Dołożyć model ML i wykresy.
