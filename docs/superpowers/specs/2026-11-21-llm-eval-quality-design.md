# Jakość szkicu LLM: blisko 100% na 9 przypadkach bez szkody dla innych dokumentów – projekt

| | |
|---|---|
| Data | 2026-11-21 |
| Zakres | `backend/llm_eval/*` (zestaw kontrolny, powtórzenia, dopasowanie), `backend/app/pipeline/draft_rules.py`, `draft_normalize.py`, prompt (`analyze.py`), przypadki `llm_eval/cases/*` |
| Poza zakresem | frontend, builder JSON (`pipeline/build/*`), ekstraktory, wybór modelu (zostaje `qwen3.5:35b-a3b`), infrastruktura Modal |

## 1. Cel i powód

`llm_eval` mierzy, ile pól oczekiwanych ma szkic (trafność) i ile pól szkicu jest właściwych (precyzja). Na 9 przypadkach (nadplata, numer-porzadkowy, odpady, pas-drogowy, psy, stypendium, swietlica, zaswiadczenie, zwrot-oplaty) `qwen3.5:35b-a3b` ma 91% trafności i 71% precyzji. Najsłabsze przypadki to odpady (78% / 44%) i stypendium (93% / 69%).

Użytkownik chce wyników jak najbliżej 100% na każdym z tych 9 dokumentów. Te 9 to minimum. System ma działać na **dowolnym** formularzu urzędowym, a poprawki pod te 9 **nie mogą** pogarszać wyników na innych dokumentach.

Analiza błędów (wyniki z 2026-11-21, gemma4:31b i qwen3.5) daje trzy grupy:

1. **Pola, których wzorzec nie uznaje, bo wnioskodawca ich nie wpisuje.** Wartości wyliczane, czyli stawki, „Wysokość opłaty” per przedział, sumy, „Kwota z poz. 29” (odpady, pas-drogowy). Do tego drobne dane drugiej osoby rozbite na wiele pól (stypendium: imię, nazwisko i telefon reprezentanta oraz pełnomocnika).
2. **Prawdziwe pominięcia.** Adres nieruchomości D.1 w odpadach, „Nazwa podatku” (nadplata), „Numer rachunku” (zwrot-oplaty), „Dyscyplina sportowa” (stypendium).
3. **Szum.** Ten sam model między przebiegami waha się o kilka punktów procentowych, a dopasowanie etykiet czasem nie łączy oczywistych synonimów („Czas trwania (dni)” i „Liczba dni”).

## 2. Cele, nie-cele, anty-cele

**Cele**
- Średnia z 3 przebiegów na 9 przypadkach: trafność ≥ 97%, precyzja ≥ 90%, a żaden przypadek poniżej 90% / 80%.
- Zestaw kontrolny: nowe dokumenty spoza tych 9, na których wynik **nie spada** względem stanu wyjściowego (tolerancja: −2 pp na średniej, bo tyle wynosi szum).
- Każda zmiana w kodzie to ogólna reguła z testem jednostkowym na zmyślonym przykładzie, a nie na tekście z przypadku.

**Nie-cele**
- Zmiana modelu domyślnego albo wprowadzenie kilku modeli z głosowaniem (podejścia B i C, patrz §3). Jeśli po poprawkach z §4.2 cele z §2 nie są osiągnięte, praca **kończy się raportem** (wynik per przypadek, co zostało i dlaczego, czy B/C by pomogło). Decyzja o B/C zapada po raporcie (decyzja użytkownika).
- Zmiany w builderze JSON i w sekcjach predefiniowanych.
- Dokładne 100% w każdym przebiegu. Przy szumie modelu to nierealne, więc celem jest średnia.

**Anty-cele**, czyli porażka nawet przy dobrych liczbach:
- Reguła lub fragment promptu, który rozpoznaje konkretny dokument po jego treści, tytule albo numerach pozycji („poz. 29”, „D.1”).
- Podbicie wyniku przez poluzowanie metryki: niższy próg dopasowania albo aliasy, które łączą różne pola.
- Zmiana wzorca przypadku tylko po to, żeby zgadzał się z wynikiem modelu. Zmiana wzorca wymaga uzasadnienia merytorycznego (patrz §4.3).
- Spadek na zestawie kontrolnym.

## 3. Podejścia

| | Opis | Za | Przeciw |
|---|---|---|---|
| **A (wybrane)** | Zestaw kontrolny i powtórzenia w `llm_eval`, potem ogólne reguły w `draft_rules`/`draft_normalize` i w prompcie, każda sprawdzona na obu zestawach | Wiarygodne, tanie w działaniu (bez dodatkowych wywołań LLM), daje się testować | Najwięcej pracy, a reguły trzeba pisać ostrożnie |
| B | Dwa modele albo dwa przebiegi i głosowanie nad polami | Ogólne, bez reguł | Czas ×2–3, a pola wyliczane i tak trzeba usuwać regułą |
| C | Drugi przebieg LLM jako recenzent szkicu | Elastyczne | Na 35B bywa niestabilne, +50% czasu, trudne do testowania |

Użytkownik wybrał **A**.

## 4. Projekt

### 4.1 Pomiar (najpierw, przed jakąkolwiek poprawką)

- **Zestaw kontrolny** w `llm_eval/holdout/`, w tym samym formacie co `cases/`. 6–8 dokumentów z BIP-ów gmin, o rodzajach różnych od tych 9 (np. wniosek o dowód osobisty, o wycinkę drzew, o zajęcie pasa drogowego innej gminy, deklaracja na podatek od nieruchomości, wniosek o dodatek mieszkaniowy, zgłoszenie imprezy). Mieszanka formatów: DOCX, PDF tekstowy i przynajmniej jeden skan.
  - Dokumenty wejściowe budujemy **prawdziwą ekstrakcją** (`app/pipeline/extract`), bo przez nią przechodzą dokumenty użytkowników. `llm_eval/extract.py` jest prowizoryczny.
  - Wzorce pól ustala builder według zasad z §4.3, **bez przeglądu użytkownika** (decyzja użytkownika). Dokumenty mają być **nie za łatwe**: wiele sekcji, tabele, listy wyboru, numerowane pozycje, dane innej osoby, co najmniej jeden skan. Wzorce powstają i są commitowane **przed** pierwszą poprawką z §4.2 i nie zmieniają się w trakcie, chyba że z uzasadnieniem z §4.3.
- **Powtórzenia:** `llm_eval.run --repeat N` (domyślnie 1) liczy średnią i rozrzut (min–max) per przypadek i dla całości. Przy `temperature=0` i `seed=42` wyniki i tak się różnią (batching na GPU), dlatego bierzemy średnią z 3 przebiegów.
- **Wybór zestawu:** `--set cases|holdout|all`.
- **Stan wyjściowy:** pierwszy pomiar `--set all --repeat 3` na aktualnym `feat/normalize` (po scaleniu `main` z 2026-11-21), zapisany w `llm_eval/results/` i wpisany do tabeli w `docs/` (patrz §6).
- **Reguła przyjęcia zmiany:** średnia na `cases` rośnie albo zostaje i nic nie spada na `holdout` (tolerancja z §2). Wynik każdej przyjętej zmiany trafia do tabeli. Doprecyzowanie (decyzja projektanta):
  - trafność i precyzja liczone **osobno**; każda z dwóch średnich na `holdout` ≥ stan wyjściowy − 2 pp;
  - pojedynczy dokument kontrolny nie może spaść o więcej niż 10 pp (średnia z 3 przebiegów);
  - porównanie zawsze ze **stanem wyjściowym**, a nie z poprzednią zmianą, żeby małe spadki się nie sumowały.
- **Ścieżka bez LLM:** każda zmiana w `draft_normalize`/`doc_hints` jest też mierzona `--model rules` (bez GPU, sekundy) z tą samą regułą przyjęcia, bo to fallback na produkcji.
- **Ekstrakcja 9 przypadków:** `document` w `cases/*.json` budujemy od nowa prawdziwą ekstrakcją (`app/pipeline/extract`), a pola wzorca zostają, bo opisują treść dokumentu, nie ekstrakcję. Stan wyjściowy mierzymy już na nowych dokumentach; stary pomiar zostaje w tabeli dla porównania (decyzja projektanta).
- **Kolejność:** zestaw kontrolny, pomiar i stan wyjściowy powstają pierwsze. Żadna poprawka nie jest przyjęta (commit do gałęzi), zanim nie przejdzie sprawdzenia na `holdout`.

### 4.2 Poprawki ogólne (kolejność według zysku)

Każda poprawka jest regułą w kodzie (z testem) albo zasadą w prompcie. W obu przypadkach sprawdzamy ją regułą z §4.1.

1. **Pola wyliczane i stawki** (odpady, pas-drogowy; największy zysk precyzji). Pole zostaje usunięte, jeśli etykieta mówi o wartości, którą liczy system albo urząd z innych pól: „stawka”, „wysokość opłaty”, „kwota opłaty”, „suma”, „razem”, „łącznie”, „kwota z poz. N”, „opłata wynosi”. Wyjątkiem są pola, które wnioskodawca wpisuje sam według instrukcji, gdy dokument nie podaje wzoru ani stawki. Rozstrzyganie w kolejności:
   - prompt: zasada „nie twórz pól na wartości wyliczane z innych pól ani na stawki z cennika”;
   - `draft_normalize`: usunięcie pól z etykietą wyliczaną, gdy w tej samej sekcji są pola liczbowe, z których da się ją wyliczyć (np. liczba gospodarstw w przedziale). Ostrożna wersja, bo „Kwota nadpłaty” w nadplacie to pole wpisywane.
2. **Numerowane pozycje deklaracji jako pola** (odpady D.1; trafność). W deklaracjach podatkowych i opłatowych pozycja „26. Miejscowość” to miejsce do wpisania, nawet bez kropek. Prompt dostaje zasadę, a `doc_hints` może oznaczyć bloki „N. Etykieta” bez wartości jako `input_placeholder`. Builder sprawdza, czy to bezpieczne dla pozostałych przypadków.
3. **Rozbijanie danych drugiej osoby** (stypendium). Gdy sekcja dotyczy innej osoby (`_OTHER_PERSON`), „Imię” i „Nazwisko” sklejamy w jedno „Imię i nazwisko …”, jak we wzorcach. Pozostałe pola zostają. Builder najpierw sprawdza we wzorcach w `wymagania/` (nadplata, numer porządkowy), czy standard tego wymaga. Jeśli standard rozdziela imię i nazwisko, poprawka odpada, a zmienia się wzorzec (§4.3).
4. **Pominięcia pojedynczych pól** (Nazwa podatku, Numer rachunku, Dyscyplina). Najpierw diagnoza: czy pole jest w `DocumentModel`, czy prompt je wycina (instrukcje, powtórzenia), czy usuwa je normalizacja. Naprawiamy przyczynę ogólnie albo, jeśli to tylko szum (raz jest, raz nie ma), zostawiamy.
5. **Dopasowanie w metryce.** Tylko poprawki, które łączą to samo pole różnie nazwane, z testem w `tests/unit/test_llm_eval_metrics.py` (np. „Czas trwania (dni)” ≈ „Liczba dni”). Każdy nowy alias albo zmiana dopasowania musi też pokazywać przykład pary, która **nadal się nie łączy**.

### 4.3 Zasady wzorca (dla nowych wzorców i korekt istniejących)

Wzorzec zawiera pola, które wnioskodawca wpisuje albo zaznacza w części „przedmiot wniosku”:
- bez danych wnioskodawcy, podpisu, miejsca i daty, które są w sekcjach predefiniowanych;
- bez wartości wyliczanych i stawek;
- bez tekstów informacyjnych;
- bez oświadczeń, bo te są osobno.

Lista wyboru to jedno pole. Tabela, w której wnioskodawca wpisuje wiersze, to pole powtarzalne albo pola per wiersz, zgodnie z tym, jak wygląda dokument. Korekta istniejącego wzorca jest dozwolona tylko z uzasadnieniem merytorycznym w opisie commita. Przykład: pole, którego wnioskodawca nie wypełnia.

## 5. Ryzyka

- **Reguła „wyliczanych” usuwa pole wpisywane.** Chroni przed tym zestaw kontrolny i testy na kontrprzykładach („Kwota nadpłaty”, „Kwota dochodu”).
- **Za mały zestaw kontrolny, żeby wychwycić spadek.** 6–8 dokumentów to minimum, a przy wątpliwościach dokładamy kolejne.
- **Koszt GPU.** Jeden przebieg `all` to około 2–3 min na L40S, więc 3 powtórzenia po każdej zmianie to około 0,3 USD. Zmieścimy się w limicie 15 USD przy około 20 zmianach.

## 6. Wynik pracy

Raport w `docs/` (obok tabeli wyników): stan wyjściowy i końcowy per przypadek na obu zestawach, lista przyjętych i odrzuconych poprawek z wynikami, pozostałe błędy z przyczyną, rekomendacja co do B/C.

## 7. Decyzje pozostawione builderowi

- Dokładne słowa kluczowe reguły „wyliczanych” i próg, od którego reguła działa.
- Czy poprawka 2 idzie przez prompt, `doc_hints`, czy oba.
- Dobór konkretnych dokumentów kontrolnych (z zachowaniem różnorodności z §4.1).
- Gdzie zapisać tabelę wyników: domyślnie istniejący dokument z wynikami LLM w `docs/` (ten z commita 4328498).
