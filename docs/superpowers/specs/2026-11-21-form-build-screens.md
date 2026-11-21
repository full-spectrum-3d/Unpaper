# Transkrypcja screenów formularzy (research)

Uwagi ogólne
- Na screenach NIE ma widocznych nagłówków zakładek/stron (tabs) ani stepperа; widoczny jest tylko tytuł formularza na górze każdej strony. Tytuły stron podane niżej wynikają z plików .md ("strona tematyczna ...") lub są moim opisem [nazwa strony nie widoczna].
- Przyciski nawigacji: strona 1: "Przerwij wypełnianie" (link-przycisk, lewo) + "Dalej" (niebieski, prawo). Strony 2 i 3: "Przerwij wypełnianie" + "Wstecz" (obrys) + "Dalej". Na ostatniej stronie (3) nadal "Dalej" (brak strony podsumowania/podglądu na screenach).
- Wszystkie pola wizualnie: etykieta nad polem, pole z czarnym obrysem = edytowalne; pole szare tło bez obrysu = read-only (prefill).
- Pola TEXT_FIELD bez opisu/hintu, jeśli nie zaznaczono inaczej.

---------------------------------------------------------------------
# FORM 1: "Wniosek o stwierdzenie nadpłaty podatku"
Tytuł formularza (nad stroną): `Wniosek o stwierdzenie nadpłaty podatku`
Strony: 1) strona z danymi wnioskodawcy [tytuł nie widoczny], 2) strona tematyczna "Nadpłata i deklaracja podatkowa" (wg .md) [tytuł nie widoczny], 3) "Dane do kontaktu i zgoda na przetwarzanie danych osobowych" (wg .md) [tytuł nie widoczny].

## Strona 1 (screeny 01-12)

### Sekcja: "Urząd, do którego jest składany wniosek"
- "Nazwa urzędu" – TEXT_FIELD, read-only (szare), prefill: `Urząd Gminy Ulan-Majorat`

### Sekcja: "Podmiot wniosku"
- "Wybierz, w czyim imieniu wnioskujesz" – RADIO. Opcje: `Swoim`, `Innej osoby`, `Osoby prawnej lub jednostki organizacyjnej`. (01: Swoim zaznaczone; 02: Innej osoby; 06: Osoby prawnej…)
- "Wybierz, jako kto wnioskujesz" – RADIO, opcje: `Pełnomocnik`, `Reprezentant`. Widoczne tylko gdy Podmiot wniosku = "Osoby prawnej lub jednostki organizacyjnej" (wyświetlane w tej samej sekcji, pod pierwszym radio). Brak domyślnego zaznaczenia.

### Sekcja: "Twoje dane"
- "Imię" – TEXT_FIELD read-only, prefill `JAIME`
- "Nazwisko" – TEXT_FIELD read-only, prefill `SAVARETS`
- "Numer PESEL" – TEXT_FIELD read-only, prefill `51051101608`

### Sekcja: "Adres zamieszkania"
- "Kraj" – SELECT, wartość domyślna `Polska` (z ikoną X czyszczenia i strzałką), edytowalne
- "Województwo" – SELECT, placeholder `Wybierz`
- "Kod pocztowy" – TEXT_FIELD z maską, placeholder `__-___`
- "Ulica" – TEXT_FIELD, placeholder `Np. Polna, aleja Leśna, plac Lipowy, skwer Słoneczny`
- "Brak nazwy ulicy" – CHECKBOX (pod Ulicą)
- "Numer budynku" – TEXT_FIELD
- "Numer lokalu" – TEXT_FIELD
- "Brak numeru lokalu" – CHECKBOX
(Uwaga: dla form. 2 screen 14 pokazuje po wypełnieniu pola kaskadowe Powiat, Gmina, Miejscowość – patrz Form 2; w Form 1 nie pokazano wypełnionego stanu.)

### Sekcje warunkowe: Podmiot wniosku = "Innej osoby" (screeny 02-05), pod "Adres zamieszkania":
#### "Dane innej osoby"
- "Imię" – TEXT_FIELD (puste, edytowalne)
- "Nazwisko" – TEXT_FIELD
#### "Adres zamieszkania innej osoby"
- identyczne pola jak "Adres zamieszkania": Kraj (SELECT, Polska), Województwo (SELECT, "Wybierz"), Kod pocztowy (`__-___`), Ulica (placeholder jw.), "Brak nazwy ulicy", Numer budynku, Numer lokalu, "Brak numeru lokalu"
#### "Pełnomocnictwo"
- TEXT_BLOCK: `Dodaj dokument potwierdzający, że jesteś pełnomocnikiem.`
- FILE_UPLOADER, etykieta: `Plik dokumentu z pełnomocnictwem`; przycisk `Dodaj lub przeciągnij plik`
  - `Dopuszczalny format pliku:` `.jpg, .pdf, .xml, .PAdES, .png, .jpeg, .CAdES, .XAdES`
  - `Maksymalny rozmiar pliku:` `10 MB`
  - `Maksymalna liczba plików:` `1`
#### "Opłata skarbowa"
- TEXT_BLOCK: `Nie musisz płacić za złożenie pełnomocnictwa wystawionego przez najbliższą rodzinę: małżonka, dzieci, rodziców, dziadków, wnuków, rodzeństwo. Więcej informacji na stronie` + link `biznes.gov.pl` (ikona linku zewnętrznego)
- "Czy złożenie pełnomocnictwa wymaga opłaty skarbowej?" – RADIO: `Tak`, `Nie` (brak domyślnego)
- Gdy `Tak` (screen 05):
  - TEXT_BLOCK: `Opłata skarbowa za pełnomocnictwo wynosi **17 zł**.` (17 zł pogrubione)
  - TEXT_BLOCK: `Przelej ją na konto urzędu miasta lub gminy właściwego dla adresu zamieszkania osoby, która udzieliła pełnomocnictwa. Jeśli adres nie jest w Polsce, opłatę przelej na konto` + link `Urzędu Miasta Stołecznego Warszawy – Centrum Obsługi Podatnika` (zewn.) 
  - TEXT_BLOCK: `W tytule przelewu wpisz „Wniosek o stwierdzenie nadpłaty podatku – opłata skarbowa za pełnomocnictwo”.`
  - FILE_UPLOADER, etykieta `Plik z potwierdzeniem przelewu`; `Dodaj lub przeciągnij plik`; format `.jpg, .pdf, .png, .jpeg`; max rozmiar `10 MB`; max liczba plików `1`
- Gdy `Nie` (screen 04): brak dodatkowych pól.

### Sekcje warunkowe: Podmiot wniosku = "Osoby prawnej lub jednostki organizacyjnej" (screeny 06-12), pod "Adres zamieszkania":
#### "Dane podmiotu"
- "Nazwa" – TEXT_FIELD
- "NIP" – TEXT_FIELD
(Form 1: tylko Nazwa i NIP; brak REGON i KRS)
#### "Adres siedziby"
- Kraj (SELECT, Polska), Województwo ("Wybierz"), Kod pocztowy (`__-___`), Ulica (placeholder jw.), "Brak nazwy ulicy", Numer budynku, Numer lokalu, "Brak numeru lokalu"
#### Gdy "Wybierz, jako kto wnioskujesz" = Pełnomocnik (screeny 08-10), dodatkowo:
- Sekcja "Pełnomocnictwo": TEXT_BLOCK `Dodaj dokument potwierdzający, że jesteś pełnomocnikiem.`; FILE_UPLOADER `Plik dokumentu z pełnomocnictwem`; formaty `.jpg, .pdf, .xml, .PAdES, .png, .jpeg, .CAdES, .XAdES`; `10 MB`; `1`
- Sekcja "Opłata skarbowa za pełnomocnictwo" (bez pytania Tak/Nie – od razu widoczna treść):
  - `Opłata skarbowa za pełnomocnictwo wynosi **17 zł**.`
  - `Przelej ją na konto urzędu miasta lub gminy właściwego dla adresu siedziby podmiotu, który udzielił pełnomocnictwa. Jeśli adres nie jest w Polsce, opłatę przelej na konto` + link `Urzędu Miasta Stołecznego Warszawy – Centrum Obsługi Podatnika`
  - `W tytule przelewu wpisz „Wniosek o stwierdzenie nadpłaty podatku – opłata skarbowa za pełnomocnictwo”.`
  - `Więcej informacji o opłacie skarbowej za pełnomocnictwo znajdziesz na stronie` + link `biznes.gov.pl`
  - FILE_UPLOADER `Plik z potwierdzeniem przelewu`; `.jpg, .pdf, .png, .jpeg`; `10 MB`; `1`
#### Gdy = Reprezentant (screeny 11-12), dodatkowo:
- Sekcja "Potwierdzenie, że jesteś reprezentantem": TEXT_BLOCK `Dołącz aktualny odpis danych z Krajowego Rejestru Sądowego lub innego rejestru. Odpis powinien potwierdzać, że jesteś reprezentantem podmiotu lub instytucji.`; FILE_UPLOADER `Plik z odpisem danych`; formaty `.jpg, .pdf, .png, .jpeg`; `10 MB`; max liczba plików `3`

## Strona 2 (screeny 13-15) – nadpłata
Przyciski: "Przerwij wypełnianie", "Wstecz", "Dalej".
### Sekcja: "Informacje o nadpłacie"
- "Podatek, którego dotyczy nadpłata" – TEXT_FIELD (pusty; na screenie ma fokus)
- "Kwota" – NUMBER/TEXT_FIELD (pusty; brak widocznej jednostki)
- TEXT_BLOCK/opis nad polem: `Uzasadnij dlaczego Twoim zdaniem powstała nadpłata i z czego wynika jej wysokość.`
- "Uzasadnienie" – TEXTAREA, licznik znaków `0/8000` (limit 8000)
### Sekcja: "Rozliczenie nadpłaty"
- "Wybierz, co mamy zrobić z nadpłatą" – RADIO: `Zaliczyć na poczet przyszłego zobowiązania podatkowego`, `Zwrócić przelewem na rachunek bankowy` (brak domyślnego)
  - po wyborze 1. opcji: "Nazwa podatku" – TEXT_FIELD (screen 14)
  - po wyborze 2. opcji: "Numer rachunku" – TEXT_FIELD (screen 15)
### Sekcja: "Korekta deklaracji"
- TEXT_BLOCK: `Załącz poprawioną deklarację podatkową, z której wynika prawidłowa, niższa wysokość zobowiązania podatkowego, a w konsekwencji nadpłata.`
- FILE_UPLOADER `Plik deklaracji podatkowej`; formaty `.jpg, .pdf, .png, .jpeg, .doc, .odt, .docx, .ods`; `10 MB`; `1`

## Strona 3 (screen 16) – kontakt i zgoda
### Sekcja: "Dane do kontaktu"
- Opis: `Wpisanie danych do kontaktu może przyspieszyć załatwienie sprawy. Urzędnik będzie mógł skontaktować się z Tobą w przypadku pytań lub wątpliwości.` (nowa linia) `Jeśli widzisz uzupełnione dane, sprawdź, czy są poprawne. Możesz je zmienić lub usunąć.`
- "Numer telefonu (opcjonalnie)" – TEXT_FIELD, prefill `+48123456789`, edytowalne (X czyszczenia)
- "Adres e-mail (opcjonalnie)" – TEXT_FIELD, prefill `jan.nowak@mail.pl`, edytowalne (X)
### Sekcja: "Zgoda"
- CONSENT_SECTION / CHECKBOX (zaznaczony na screenie): `Wyrażam zgodę na przetwarzanie moich danych osobowych zgodnie z klauzulą informacyjną` – link: `klauzulą informacyjną` (ikona zewn.)
- Brak komunikatu błędu na tym screenie.

---------------------------------------------------------------------
# FORM 2: "Wniosek o ustalenie numeru porządkowego nieruchomości"
Tytuł: `Wniosek o ustalenie numeru porządkowego nieruchomości`
Strony: 1) dane wnioskodawcy [tytuł nie widoczny], 2) "Lokalizacja budynku" (wg .md), 3) "Dane do kontaktu" (wg .md).

## Strona 1 (screeny 01-14)
### Sekcja: "Organ, do którego jest składany wniosek"  (RÓŻNICA: "Organ", nie "Urząd")
- "Nazwa organu" – TEXT_FIELD read-only, prefill `Wójt Gminy Elbląg`

### Sekcja: "Podmiot wniosku" – identyczna jak w Form 1
- "Wybierz, w czyim imieniu wnioskujesz" – RADIO: `Swoim`, `Innej osoby`, `Osoby prawnej lub jednostki organizacyjnej`
- "Wybierz, jako kto wnioskujesz" – RADIO: `Pełnomocnik`, `Reprezentant` (warunkowo, jak w Form 1)

### Sekcja: "Twoje dane"  (RÓŻNICA: tylko Imię i Nazwisko, BEZ PESEL)
- "Imię" – read-only `JAIME`
- "Nazwisko" – read-only `SAVARETS`

### Sekcja: "Adres zamieszkania" – pola jak w Form 1 (Kraj, Województwo, Kod pocztowy, Ulica, Brak nazwy ulicy, Numer budynku, Numer lokalu, Brak numeru lokalu).
Dodatkowo screen 13 (wypełniony stan, Pełnomocnik/Reprezentant): po wyborze Województwa pojawiają się kaskadowe SELECT-y: "Województwo" = `Kujawsko-pomorskie`, "Powiat" = `Aleksandrowski`, "Gmina" = `Aleksandrów Kujawski (gmina miejska)`, "Miejscowość" = `Aleksandrów Kujawski` (kolejność: Kraj, Województwo, Powiat, Gmina, Miejscowość, Kod pocztowy, Ulica, ...). "Kod pocztowy" `02-111` (prefill/wpisane), "Ulica" `Słoneczna`, "Numer budynku" `4`; zaznaczone "Brak numeru lokalu" → pole "Numer lokalu" szare/disabled. (To stan z wpisanymi danymi, nie domyślny; kaskada Powiat/Gmina/Miejscowość występuje najpewniej też w Form 1 i w pozostałych sekcjach adresowych.)

### Sekcje warunkowe: "Innej osoby" (screeny 02-06)
- "Dane innej osoby": "Imię", "Nazwisko" (jak Form 1)
- "Adres zamieszkania innej osoby": jak Form 1
- "Pełnomocnictwo": TEXT_BLOCK `Dodaj dokument potwierdzający, że jesteś pełnomocnikiem.`; FILE_UPLOADER z etykietą `Dokument z potwierdzeniem, podpisany elektronicznie` (RÓŻNICA vs Form 1: "Plik dokumentu z pełnomocnictwem"); formaty `.jpg, .pdf, .xml, .PAdES, .png, .jpeg, .CAdES, .XAdES`; `10 MB`; `1`
- "Opłata skarbowa": TEXT_BLOCK identyczny jak Form 1 (`Nie musisz płacić za złożenie pełnomocnictwa wystawionego przez najbliższą rodzinę: małżonka, dzieci, rodziców, dziadków, wnuków, rodzeństwo. Więcej informacji na stronie` + link `biznes.gov.pl`); RADIO `Czy złożenie pełnomocnictwa wymaga opłaty skarbowej?` Tak/Nie.
  - Tak: `Opłata skarbowa za pełnomocnictwo wynosi **17 zł**.` / `Przelej ją na konto urzędu miasta lub gminy właściwego dla adresu zamieszkania osoby, która udzieliła pełnomocnictwa. Jeśli adres nie jest w Polsce, opłatę przelej na konto` + link `Urzędu Miasta Stołecznego Warszawy – Centrum Obsługi Podatnika` / `W tytule przelewu wpisz „Wniosek o zwrot opłaty skarbowej – opłata skarbowa za pełnomocnictwo”.` (RÓŻNICA: inny tytuł przelewu niż Form 1; wygląda na kopię z innego wniosku, ale to tekst na screenie) / FILE_UPLOADER z etykietą `Potwierdzenie przelewu` (Form 1: "Plik z potwierdzeniem przelewu"); `.jpg, .pdf, .png, .jpeg`; `10 MB`; `1`
    (Uwaga: w wariancie "Innej osoby" w Form 2 nie ma zdania "Więcej informacji o opłacie skarbowej… biznes.gov.pl" – tak samo jak w Form 1.)
  - Nie: brak dodatkowych pól.

### Sekcje warunkowe: "Osoby prawnej lub jednostki organizacyjnej" (screeny 07-14)
- "Dane podmiotu" (RÓŻNICA: 4 pola): "Nazwa", "NIP", "REGON", "Numer KRS" (TEXT_FIELD)
- "Adres siedziby": pola jak Form 1
- Pełnomocnik (09-11): "Pełnomocnictwo" (etykieta uploadu `Dokument z potwierdzeniem, podpisany elektronicznie`, formaty jak wyżej, 10 MB, 1) oraz "Opłata skarbowa za pełnomocnictwo": `Opłata skarbowa za pełnomocnictwo wynosi **17 zł**.` / `Przelej ją na konto urzędu miasta lub gminy właściwego dla adresu siedziby podmiotu, który udzielił pełnomocnictwa. Jeśli adres nie jest w Polsce, opłatę przelej na konto` + link `Urzędu Miasta Stołecznego Warszawy – Centrum Obsługi Podatnika` / `W tytule przelewu wpisz „Wniosek o zwrot opłaty skarbowej – opłata skarbowa za pełnomocnictwo”.` / `Więcej informacji o opłacie skarbowej za pełnomocnictwo znajdziesz na stronie` + link `biznes.gov.pl` / upload `Potwierdzenie przelewu` (`.jpg, .pdf, .png, .jpeg`, 10 MB, 1)
- Reprezentant (12-14): "Potwierdzenie, że jesteś reprezentantem": `Dołącz aktualny odpis danych z Krajowego Rejestru Sądowego lub innego rejestru. Odpis powinien potwierdzać, że jesteś reprezentantem podmiotu lub instytucji.`; upload `Plik z odpisem danych`; `.jpg, .pdf, .png, .jpeg`; `10 MB`; max liczba plików `3` (identyczne jak Form 1)

## Strona 2 (screen 15)
### Sekcja: "Lokalizacja budynku"
- "Miejscowość" – TEXT_FIELD (screen: wpisane `Dzierżoniów`, X czyszczenia) [wartość przykładowa; w tle nie wiadomo czy prefill]
- "Ulica" – TEXT_FIELD (przykład `Polna`)
- "Brak nazwy ulicy" – CHECKBOX
- "Numer ewidencyjny działki" – TEXT_FIELD (przykład `123/qwe/2026`)
- "Obręb" – TEXT_FIELD (przykład `12a/123`; fokus)
Przyciski: Przerwij wypełnianie, Wstecz, Dalej.

## Strona 3 (screen 16)
### Sekcja: "Dane do kontaktu" – identyczna jak Form 1 (ten sam opis; "Numer telefonu (opcjonalnie)" prefill `+48123456789`; "Adres e-mail (opcjonalnie)" prefill `jan.nowak@mail.pl`)
### Sekcja o tytule: `Zgoda_sekcja` (RÓŻNICA/wygląda na techniczny identyfikator zamiast "Zgoda" – tytuł widoczny dosłownie jako "Zgoda_sekcja")
- CHECKBOX (niezaznaczony, stan błędu – czerwony obrys): `Wyrażam zgodę na przetwarzanie moich danych osobowych zgodnie z klauzulą informacyjną` (link `klauzulą informacyjną`); komunikat walidacji (czerwony, z ikoną ostrzeżenia): `Oświadczenie jest wymagane.` => zgoda jest wymagana (required).

---------------------------------------------------------------------
# Conditional logic
1. Podmiot wniosku = "Innej osoby" -> pod "Adres zamieszkania" pojawiają się: "Dane innej osoby", "Adres zamieszkania innej osoby", "Pełnomocnictwo", "Opłata skarbowa". "Twoje dane" i "Adres zamieszkania" pozostają widoczne.
2. Podmiot wniosku = "Osoby prawnej lub jednostki organizacyjnej" -> w sekcji "Podmiot wniosku" pojawia się radio "Wybierz, jako kto wnioskujesz" (Pełnomocnik/Reprezentant); pod "Adres zamieszkania" pojawiają się "Dane podmiotu" i "Adres siedziby".
   - "Wybierz, jako kto wnioskujesz" = Pełnomocnik -> dodatkowo "Pełnomocnictwo" + "Opłata skarbowa za pełnomocnictwo" (bez pytania Tak/Nie, upload potwierdzenia zawsze widoczny).
   - = Reprezentant -> dodatkowo "Potwierdzenie, że jesteś reprezentantem".
3. W "Opłata skarbowa" (tylko ścieżka "Innej osoby"): "Czy złożenie pełnomocnictwa wymaga opłaty skarbowej?" = Tak -> pojawiają się teksty (17 zł, przelew, tytuł przelewu) + upload potwierdzenia przelewu; = Nie -> nic więcej.
4. Swoim -> żadne dodatkowe sekcje.
5. Form 1 str. 2: "Rozliczenie nadpłaty" = "Zaliczyć na poczet przyszłego zobowiązania podatkowego" -> pole "Nazwa podatku"; = "Zwrócić przelewem na rachunek bankowy" -> pole "Numer rachunku" (wg .md warunek jsonata).
6. Form 2 str. 1: zaznaczenie "Brak numeru lokalu" wyłącza (szarzeje) "Numer lokalu" (widoczne na screenie 13); analogicznie "Brak nazwy ulicy" -> "Ulica" (zakładane, niewidoczne). Wybór Województwa uruchamia kaskadę Powiat -> Gmina -> Miejscowość (screen 13).
7. Walidacja wymagana: zgoda na stronie 3 (komunikat `Oświadczenie jest wymagane.`).

# Różnice między formularzami
| Element | Form 1 (nadpłata) | Form 2 (numer porządkowy) |
|---|---|---|
| Sekcja 1 (tytuł/etykieta) | "Urząd, do którego jest składany wniosek" / "Nazwa urzędu" = Urząd Gminy Ulan-Majorat | "Organ, do którego jest składany wniosek" / "Nazwa organu" = Wójt Gminy Elbląg |
| "Twoje dane" | Imię, Nazwisko, Numer PESEL | Imię, Nazwisko (bez PESEL) |
| "Dane podmiotu" | Nazwa, NIP | Nazwa, NIP, REGON, Numer KRS |
| Etykieta uploadu w "Pełnomocnictwo" | `Plik dokumentu z pełnomocnictwem` | `Dokument z potwierdzeniem, podpisany elektronicznie` |
| Etykieta uploadu potwierdzenia przelewu | `Plik z potwierdzeniem przelewu` | `Potwierdzenie przelewu` |
| Tytuł przelewu | „Wniosek o stwierdzenie nadpłaty podatku – opłata skarbowa za pełnomocnictwo” | „Wniosek o zwrot opłaty skarbowej – opłata skarbowa za pełnomocnictwo” |
| Tytuł sekcji zgody (str. 3) | `Zgoda` | `Zgoda_sekcja` (prawdopodobny błąd/techniczny klucz) |
| Zgoda na screenie | zaznaczona | niezaznaczona z błędem "Oświadczenie jest wymagane." |
| Strony tematyczne | str.2 "Informacje o nadpłacie/Rozliczenie nadpłaty/Korekta deklaracji" | str.2 "Lokalizacja budynku" |

Identyczne w obu: "Podmiot wniosku" (radia), "Adres zamieszkania", "Dane innej osoby", "Adres zamieszkania innej osoby", "Adres siedziby", tekst + parametry uploadu "Pełnomocnictwo" (opis `Dodaj dokument potwierdzający, że jesteś pełnomocnikiem.`, formaty, 10 MB, 1), "Opłata skarbowa" (tekst wstępny + radio), kwota 17 zł, teksty przelewu (poza tytułem), "Opłata skarbowa za pełnomocnictwo", "Potwierdzenie, że jesteś reprezentantem" (3 pliki), "Dane do kontaktu", klauzula zgody.

# Shared predefined sections – canonical version
(Pola jednolite; różnice parametrów w nawiasach.)

1. **Podmiot wniosku**: RADIO "Wybierz, w czyim imieniu wnioskujesz": Swoim | Innej osoby | Osoby prawnej lub jednostki organizacyjnej. Warunkowe RADIO "Wybierz, jako kto wnioskujesz": Pełnomocnik | Reprezentant (gdy Osoby prawnej…).
2. **Twoje dane** (read-only, prefill z rejestru): Imię, Nazwisko, [Numer PESEL – tylko Form 1].
3. **Adres zamieszkania**: Kraj (SELECT, domyślnie Polska), Województwo (SELECT, placeholder "Wybierz"), [Powiat, Gmina, Miejscowość – kaskadowe SELECT po wyborze województwa], Kod pocztowy (maska `__-___`), Ulica (placeholder `Np. Polna, aleja Leśna, plac Lipowy, skwer Słoneczny`), CHECKBOX "Brak nazwy ulicy", Numer budynku, Numer lokalu, CHECKBOX "Brak numeru lokalu".
4. **Dane innej osoby**: Imię, Nazwisko. **Adres zamieszkania innej osoby**: jak pkt 3.
5. **Dane podmiotu**: Nazwa, NIP, [REGON, Numer KRS – tylko Form 2]. **Adres siedziby**: jak pkt 3.
6. **Pełnomocnictwo**: `Dodaj dokument potwierdzający, że jesteś pełnomocnikiem.`; upload (etykieta zależna od formularza); `.jpg, .pdf, .xml, .PAdES, .png, .jpeg, .CAdES, .XAdES`; 10 MB; 1 plik.
7. **Opłata skarbowa** (Innej osoby): tekst o najbliższej rodzinie + link biznes.gov.pl; RADIO "Czy złożenie pełnomocnictwa wymaga opłaty skarbowej?" Tak/Nie; Tak -> 17 zł, tekst przelewu (adres zamieszkania osoby, która udzieliła pełnomocnictwa), tytuł przelewu (zależny od formularza), upload potwierdzenia (`.jpg, .pdf, .png, .jpeg`, 10 MB, 1).
8. **Opłata skarbowa za pełnomocnictwo** (podmiot/Pełnomocnik): jak wyżej ale tekst "dla adresu siedziby podmiotu, który udzielił pełnomocnictwa" + zdanie `Więcej informacji o opłacie skarbowej za pełnomocnictwo znajdziesz na stronie` + link `biznes.gov.pl`; upload zawsze widoczny.
9. **Potwierdzenie, że jesteś reprezentantem**: `Dołącz aktualny odpis danych z Krajowego Rejestru Sądowego lub innego rejestru. Odpis powinien potwierdzać, że jesteś reprezentantem podmiotu lub instytucji.`; upload `Plik z odpisem danych`; `.jpg, .pdf, .png, .jpeg`; 10 MB; 3 pliki.
10. **Dane do kontaktu**: opis `Wpisanie danych do kontaktu może przyspieszyć załatwienie sprawy. Urzędnik będzie mógł skontaktować się z Tobą w przypadku pytań lub wątpliwości.` + `Jeśli widzisz uzupełnione dane, sprawdź, czy są poprawne. Możesz je zmienić lub usunąć.`; "Numer telefonu (opcjonalnie)" (prefill +48123456789), "Adres e-mail (opcjonalnie)" (prefill jan.nowak@mail.pl).
11. **Zgoda**: CHECKBOX `Wyrażam zgodę na przetwarzanie moich danych osobowych zgodnie z klauzulą informacyjną` (link "klauzulą informacyjną"); wymagana, komunikat `Oświadczenie jest wymagane.`

# Strona podsumowania / podglądu
Na żadnym z 32 screenów nie widać strony podsumowania ani podglądu ("Podgląd") ani przycisku "Wyślij"/"Złóż wniosek"; ostatnia strona (3) ma przyciski "Przerwij wypełnianie", "Wstecz", "Dalej".
