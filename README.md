# Automatický organizátor souborů

Webová aplikace ve stylu průzkumníka souborů, která umí soubory automaticky uspořádat do složek.
Autor: Patrik Mičian · ročníková práce

## Technologie
Python (Flask) · HTML · CSS · JavaScript

## Spuštění
1. Nainstaluj Python 3.9 nebo novější.
2. V této složce spusť:
   ```
   pip install -r requirements.txt
   python app.py
   ```
3. Otevři v prohlížeči http://127.0.0.1:5000

## Použití
- Aplikace pracuje ve složce `workspace/` (jsou v ní ukázkové soubory na vyzkoušení).
- Soubory můžeš nahrát tlačítkem nebo je přetáhnout do okna.
- Tlačítko **Automaticky uspořádat** nabídne 4 režimy: podle typu, přípony, data a velikosti.
  Nejdřív se ukáže náhled změn, přesun se provede až po potvrzení.
- Tlačítko **Zpět** vrátí poslední uspořádání.

## Struktura
```
app.py              server a logika (Flask, REST API)
static/index.html   struktura stránky
static/style.css    vzhled
static/app.js       ovládání a komunikace se serverem
workspace/          pracovní složka s ukázkovými soubory
requirements.txt    závislosti
```

## Bezpečnost
Aplikace nikdy nesahá mimo složku `workspace/`. Při shodě názvů se soubory nepřepisují (přidá se (1), (2)…).
