**Każdy formularz powinien być skonfigurowany z zachowaniem poniższych reguł, a definicja formularza powinna mieć odzwierciedlenie w pliku json odpowiadającym danemu formularzowi:**

1. Tytuł formularza = nazwa usługi widoczna dla Obywatela – max 255 znaków.
2. Każdy formularz musi zawierać:
   1. Minimum dwie strony (tabs):
   2. Strona końcowa musi być oznaczona w jsonie tagiem finish
   3. Pozostałe strony muszą być oznaczone tagami main
3. Każda strona musi zawierać minimum jedno pole.
4. Każde pole musi być zagnieżdżone w sekcji lub sekcji powtarzającej się.
5. Sekcja lub sekcja powtarzająca się musi być zagnieżdżona na konkretnej stronie formularza.
6. Nie jest możliwe zagnieżdżenie sekcji/sekcji powtarzającej się w innej sekcji/sekcji powtarzającej się.
7. Na stronie końcowej nie mogą znajdować się żadne pola typu Input (do wprowadzania treści). Na ostatniej stronie oznaczonej jako finish może być dodane wyłącznie pole typu sekcja informacyjna "INFO\_SECTION".
8. Każde pole na stronie musi mieć określony atrybut obligatoryjności.
9. Strony muszą być połączone ze sobą warunkami przepływu stron.
10. Jeżeli pomiędzy polami/sekcjami/sekcjami powtarzającymi się występują zależności określające kiedy dane pole jest prezentowane na formularzu, to komponent, którego prezentacja zależy od wyboru Użytkownika w polu powiązanym, musi mieć zdefiniowane dynamiczne stany pola opisane (jsonata).
11. Możliwe jest zastosowanie słownika w polu typu lista rozwijana, checkbox, radiobutton.
12. Dostępne rodzaje komponentów konfigurowalnych na formularzu prezentuje tabela poniżej. Konfiguracja każdego pola musi mieć odzwierciedlenie w jsonie danego formularza.

|  |  |
| --- | --- |
| **Nazwa komponentu** | **Opis** |
| Pole tekstowe  "type": "TEXT\_FIELD" | Komponent umożliwiający użytkownikowi wprowadzenie krótkiej wartości tekstowej, np. imienia, nazwiska, nazwy podmiotu lub identyfikatora. Pole może podlegać walidacji zgodnie z konfiguracją formularza. |
| Pole wyboru checkbox  "type": "CHECKBOX" | Komponent umożliwiający zaznaczenie lub odznaczenie określonej opcji. Może być wykorzystywany m.in. do potwierdzania oświadczeń, wyboru niezależnych opcji. Pole wielokrotnego wyboru, może być zasilane słownikiem. |
| Pole numeryczne  "type": "NUMBER" | Komponent przeznaczony do wprowadzania wartości liczbowych. Może ograniczać dopuszczalne dane do określonego rodzaju lub zakresu liczb oraz podlegać dodatkowym regułom walidacyjnym. |
| Sekcja zgód  "type": "CONSENT\_SECTION" | Komponent grupujący zgody, oświadczenia lub potwierdzenia, które użytkownik może albo musi zaakceptować w związku z realizacją eUsługi. Poszczególne zgody mogą być wymagane lub opcjonalne. |
| Lista rozwijana  "type": "SELECT" | Komponent umożliwiający wybór wartości z wcześniej zdefiniowanej listy dostępnych opcji. Stosowany jest w sytuacji, gdy użytkownik powinien wskazać jedną wartość ze zbioru określonego w konfiguracji formularza.  Pole może być zasilane wartościami słownikowymi. |
| Textarea  "type": "TEXTAREA" | Komponent umożliwiający wprowadzenie dłuższej treści tekstowej, np. opisu, uzasadnienia, uwag lub dodatkowych informacji. W odróżnieniu od standardowego pola tekstowego umożliwia wygodne wprowadzanie tekstu w wielu wierszach. |
| Pole przesyłania plików  "type": "FILE\_UPLOADER" | Komponent umożliwiający użytkownikowi dodanie pliku jako załącznika do formularza. Przesyłany plik może podlegać ograniczeniom dotyczącym m.in. formatu, rozmiaru lub liczby załączników. |
| Pole wyboru radiobutton  "type": "RADIO" | Komponent umożliwiający wybór **jednej opcji** spośród wzajemnie wykluczających się wartości. Zaznaczenie jednej opcji powoduje wykluczenie pozostałych opcji należących do tej samej grupy. |
| Pole wyboru daty  "type": "DATEPICKER" | Komponent umożliwiający wprowadzenie lub wskazanie daty, w szczególności poprzez wybór jej z widoku kalendarza. Może uwzględniać ograniczenia dotyczące dopuszczalnego zakresu dat. |
| Blok tekstu  "type": "TEXT\_BLOCK" | Komponent prezentacyjny służący do wyświetlania statycznej treści w formularzu. Może być wykorzystywany m.in. do prezentowania opisów, instrukcji, objaśnień lub dodatkowych informacji i nie wymaga wprowadzania danych przez użytkownika. |
| Sekcja informacyjna  "type": "INFO\_SECTION" | Komponent służący do wydzielonego prezentowania użytkownikowi informacji związanych z formularzem lub realizowaną eUsługą, np. komunikatów, instrukcji lub dodatkowych wyjaśnień. Nie służy do wprowadzania danych przez użytkownika. |

Lista możliwych walidatorów do użycia w różnych polach (nie wszystkie walidatory są możliwe do ustawienia w każdym typie pola na formularzu):

1. Pole wymagane (REQUIRED)
2. Email (EMAIL)
3. PESEL (PESEL)
4. NIP (NIP)
5. REGON (REGON)
6. Kod pocztowy (ZIP\_CODE)
7. Elektroniczna Skrzynka Podawcza ePUAP (EPUAP)
8. Adres do e-Doręczeń (ADE)
9. Seria i numer dowodu osobistego (SERIAL\_NUMBER\_ID\_CARD)

**Specyfikacja poszczególnych komponentów – możliwości konfiguracji poszczególnych komponentów na etapie konfiguracji formularza:**

**Sekcja -  "type": "SECTION"**

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obliatoryjność** |
| 1 | Nazwa sekcji | "title" | TAK |
| 2 | Nazwa techniczna sekcji | "techName" | TAK |

**Sekcja powtarzająca się - "type": "REPEATING\_SECTION"**

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obliatoryjność** |
| 1 | Nazwa sekcji | "title" | TAK |
| 2 | Nazwa techniczna sekcji | "techName" | TAK |

**Dynamiczne stany sekcji/sekcji powtarzającej się "states"**

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Dostępne stany** | **Obliatoryjność** |
| 1 | Stan | "type" | Pokaż (SHOW) | TAK |
| 2 | Warunek stanu | "query" |  | TAK |

**Dynamiczne stany pola "states"**

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Dostępne stany** | **Obliatoryjność** |
| 1 | Stan | "type" | Pokaż (SHOW)  Tylko do odczytu (READ\_ONLY) | TAK |
| 2 | Warunek stanu | "query" |  | TAK |

**Warunki jsonaty:**

1. Warunek SHOW jest wykorzystywany do dynamicznego prezentowania wskazanego pola/sekcji na formularzu
2. Warunek READ\_ONLY służy do prezentowania wskazanego pola na formularzu, w stanie tylko do odczytu.

Przykładowe komendy jsonaty:

|  |  |  |
| --- | --- | --- |
| **Lp.** | **Opis komendy** | **Komenda jsonata** |
| 1 | Odwołanie do odpowiedzi z pola wyboru w sekcji | "**Opcja 1**" in tabs['**Strona 1**' in title].questions['**sekcja\_1**' in field.techName].field.repeatingSectionGrid['**pole\_1**' in field.techName].field.\_\_userAnswer |
| 2 | Odwołanie do odpowiedzi z pola wyboru w sekcji powtarzającej się | "**Opcja 1**" in tabs['**Strona 1**'in title].questions['**sekcja\_1**' in field.techName].field.\_\_userAnswer[$repeatingSectionIndex]['**pole\_1**'in fieldTechName].answers |

**Przykładowy warunek jsonaty dla pola typu SELECT:**

"states": [

                                        {

                                            "type": "SHOW",

                                            "query": "(\"Polska\" in tabs['Dane' in title].questions['adres\_zamieszkania' in field.techName].field.repeatingSectionGrid['kraj' in field.techName].field.\_\_userAnswer)"

                                        }

                                    ],

**Komponent Pole tekstowe – "type": "TEXT\_FIELD"**

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji w jsonie** |
| 1 | Etykieta | "title" | NIE |
| 2 | Nazwa techniczna | "techName" | TAK |
| 3 | Opis | "description" | NIE |
| 4 | Pole tylko do odczytu | "readOnly" | NIE |
| 5 | Jsonata | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |
| 6 | Wartość domyślna ustawiana w polu (może być zasilana danymi inicjalnymi) | "defaultValue" | NIE |
| 7 | Walidacje – pole może mieć ustawiony dowolny walidator z listy walidatorów | "validation": [] |  |

**Komponent – Checkbox (**"type": "CHECKBOX")

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Etykieta | "title" | NIE |
| 2 | Nazwa techniczna | "techName" | TAK |
| 3 | Opis | "description" | NIE |
| 4 | Pole tylko do odczytu | "readOnly" | NIE |
| 5 | Opcje wyboru – jeżeli dla pola są zdefiniowane dedykowane opcje inne niż słownik | Każda pozycja w tablicy opisana zestawem wartości:  "id":  "name":  "techName": | TAK – jeżeli pole korzysta ze słownika, to tablica jest pusta |
| 6 | Słownik – dodany jeżeli pole dostarcza opcje wyboru z predefiniowanego słownika | "dictionaryName" | NIE |
| 7 | Walidacje – pole może mieć ustawiony walidator wymagalności | "validation": [] |  |
| 8 | Dynamiczne stany pola  (Ustaw warunki stanu używając komendy jsonata) | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |

**Komponent Pole numeryczne (**"type": "NUMBER")

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Etykieta | "title" | Nie |
| 2 | Nazwa techniczna | "techName" | Tak |
| 3 | Opis | "description" | Nie |
| 4 | Pole tylko do odczytu | "readOnly" | NIE |
| 5 | Walidacje – pole może mieć ustawiony walidator wymagalności | "validation": [] | TAK |
| 6 | Dynamiczne stany pola  (Ustaw warunki stanu używając komendy jsonata) | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |

**Komponent Blok tekstu (**"type": "TEXT\_BLOCK")

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Etykieta | "title" | Nie |
| 2 | Nazwa techniczna | "techName" | Tak |
| 3 | Opis | "description" | Nie |
| 4 | Dynamiczne stany pola  (Ustaw warunki stanu używając komendy jsonata) | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |

**Komponent Lista rozwijana ("type": "SELECT")**

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Etykieta | "title" | Nie |
| 2 | Nazwa techniczna | "techName" | Tak |
| 3 | Opis | "description" | Nie |
| 4 | Pole tylko do odczytu | "readOnly" | NIE |
| 5 | Pole do wyszukiwania wartości na liście | "searchEnabled": true/false | NIE |
| **6** | Opcje wyboru – dodane jeżeli dla pola są zdefiniowane dedykowane opcje inne niż słownik | Każda pozycja opisana zestawem wartości:  "id":  "name":  "techName": | TAK – jeżeli pole korzysta ze słownika, to tablica jest pusta |
| 7 | Słownik – ustawiony jeżeli pole dostarcza wartości z predefiniowanego słownika | "dictionaryName" | NIE |
| 8 | Wartość domyślna | "defaultValue": [] |  |
| 9 | Walidacje – pole może mieć ustawiony walidator wymagalności | "validation": [] | TAK |
| 10 | Dynamiczne stany pola  (Ustaw warunki stanu używając komendy jsonata) | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |

**Komponent Textarea (**"type": "TEXTAREA")

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Etykieta | "title" | Nie |
| 2 | Nazwa techniczna | "techName" | Tak |
| 3 | Wartość domyślna ustawiana w polu (może być zasilana danymi inicjalnymi) | "defaultValue": [] | NIE |
| 4 | Opis | "description" | NIE |
| 5 | Pole tylko do odczytu | "readOnly" | NIE |
| 6 | Walidacje – pole może mieć ustawiony walidator wymagalności | "validation": [] | TAK |
| 7 | Dynamiczne stany pola  (Ustaw warunki stanu używając komendy jsonata) | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |

**Komponent Przesyłanie plików ("type": "FILE\_UPLOADER")**

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Etykieta | "title" | Nie |
| 2 | Nazwa techniczna | "techName" | Tak |
| 3 | Wartość domyślna | "defaultValue": [] | NIE |
| 4 | Opis | "description" | Nie |
| 5 | Walidacje – pole może mieć ustawiony walidator wymagalności | "validation": [] | TAK |
| 6 | Dynamiczne stany pola  (Ustaw warunki stanu używając komendy jsonata) | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |

**Komponent wyboru Radiobutton (**"type": "RADIO")

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Etykieta | "title" | Nie |
| 2 | Nazwa techniczna\* | "techName" | Tak |
| 3 | Opis | "description" | NIE |
| 4 | Pole tylko do odczytu | "readOnly" | NIE |
| **5** | Opcje wyboru – dodane jeżeli dla pola są zdefiniowane dedykowane opcje inne niż słownik | Każda pozycja opisana zestawem wartości:  "id":  "name":  "techName": | TAK – jeżeli pole korzysta ze słownika, to tablica jest pusta |
| 6 | Słownik – ustawiony jeżeli pole dostarcza wartości z predefiniowanego słownika | "dictionaryName" | NIE |
| 7 | Walidacje – pole może mieć ustawiony walidator wymagalności | "validation": [] | TAK |
| 8 | Dynamiczne stany pola  (Ustaw warunki stanu używając komendy jsonata) | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |

**Komponent Datepicker (**"type": "DATEPICKER")

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Etykieta | "title" | Nie |
| 2 | Nazwa techniczna\* | "techName" | Tak |
| 3 | Opis | "description" | NIE |
| 4 | Pole tylko do odczytu | "readOnly" | NIE |
| 5 | Walidacje – pole może mieć ustawiony walidator wymagalności | "validation": [] | TAK |
| 6 | Dynamiczne stany pola  (Ustaw warunki stanu używając komendy jsonata) | "states": [  {  "type": "SHOW",  "query": (komenda jsonata)  ] | NIE |

**Komponent Sekcja zgód (**"type": "CONSENT\_SECTION")

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Nazwa techniczna pola\* | "techName" | Tak |
| 2 | Czy pod polem ma być widoczny przycisk 'Zaznacz wszystkie' | "selectAllEnabled": true/false | NIE |
| 3 | Zgoda | Każda zgoda w tablicy opisana zestawem wartości:  "consents": [  {  "description":  "required": false/true  }, | TAK |
| 4 | Plik zgody możliwy do pobrania na formularzu | "files": [], |  |

**Komponent Sekcja informacyjna (**"type": "INFO\_SECTION")

|  |  |  |  |
| --- | --- | --- | --- |
| **Lp.** | **Pole opisujące komponent** | **Nazwa pola w jsonie** | **Obligatoryjność konfiguracji** |
| 1 | Nazwa techniczna | "techName" | Tak |
| 2 | Opis | "description" | Tak |