|  |  |  |
| --- | --- | --- |
| **Pole** | **Typ** | **Opis** |
| title | string | tytuł formularza, zrozumiały dla użytkownika |
| tabs | tablica | obiekt zawierający definicję stron/zakładek |
| tabs.id | string | unikatowy identyfikator obiektu UUID |
| tabs.title | string | tytuł może być prezentowany dla użytkownika |
| tabs.type | string | typ obiektu, możliwa jednak z dwóch wartości MAIN, FINISH |
| tabs.questions | tablica | tablica zawierająca definicję pól na stronie/zakładce |
| tabs.questions.x | number | pozycja początkowa w osi poziomej (kolumna), liczona od 0  wartość używana do zbudowania: CSS grid-area: {y+1} / {x+1} / span {rows} / span {cols} |
| tabs.questions.y | number | pozycja początkowa w osi pionowej (wiersz), liczona od 0  wartość używana do zbudowania: CSS grid-area: {y+1} / {x+1} / span {rows} / span {cols} |
| tabs.questions.rows | number | liczba wierszy zajmowanych przez element  wartość używana do zbudowania:  CSS grid-area: {y+1} / {x+1} / span {rows} / span {cols} |
| tabs.questions.cols | number | liczba kolumn zajmowanych przez element  wartość używana do zbudowania:  CSS grid-area: {y+1} / {x+1} / span {rows} / span {cols} |
| tabs.questions.field | obiekt | obiekt zawierający ustawienia dla pola |
| tabs.questions.field.id | string | unikatowy identyfikator obiektu UUID |
| tabs.questions.field.type | string | typ pola |
| tabs.questions.field.techName | string | nazwa techniczna, używana np. do JSONaty |
| tabs.questions.field.title | string | tekst wyświetlany jako tytuł dla pola |
| tabs.questions.field.description | string | tekst wyświetlany jako dodatkowy opis wyjaśniający dla pola |
| tabs.questions.field.options | tablica | tablica zawierająca listę wartości dla pola jeśli dany typ na to pozwala |
| tabs.questions.field.options.id | string | identyfikator opcji |
| tabs.questions.field.options.name | string | nazwa opcji |
| tabs.questions.field.options.techName | string | nazwa techniczna,  używana np. do JSONaty |
| tabs.questions.field.validation | tablica | tablica stringów przyjmująca nazwy predefiniowanych walidacji |
| tabs.questions.field.dictionaryName | string | nazwa predefiniowanego słownika |
| tabs.questions.field.readOnly | boolean | pole prezentujące wartość wyłącznie do odczytu |
| tabs.questions.field.repetingSectionGrid | tablica | tablica zawierająca obiekty definiujące pola zagnieżdżone w sekcji powtarzającej, w strukturze jak question |
| tabs.questions.field.defaultValue | string | domyślna wartość ustawiana przez użytkownika |
| tabs.questions.field.defaultValueType | string | przyjmuje wartość  EXTERNAL\_SYSTEM jeśli wartość ma pochodzić z rejestru państwowego lub pozostaje puste gdy wartość nie jest ustawiana dynamicznie |
| tabs.questions.field.consentSectionConfig | obiekt | konfiguracja sekcji zgód dostępna wyłącznie dla typu CONSENT\_SECTIOM |
| tabs.questions.field.consentSectionConfig.consents | tablica | zawiera obiekty definiujące zgody załączane do formularza |
| tabs.questions.field.consentSectionConfig.consents.descripton | string | opis zgody |
| tabs.questions.field.consentSectionConfig.required | boolean | wymagalność zgody |
| tabs.questions.field.consentSectionConfig.files | tablica | kolekcja nazwa plików |
| tabs.questions.field.states | tablica | tablica obiektów definiujących JSONaty |
| tabs.questions.field.states.type | string | typ operacji |
| tabs.questions.field.states.query | string | sformułowane zapytanie |
| tabs.questions.field.questionOrder | numer | numer kolejności umieszczenia pola na stronie |
| tabs.questions.field.tooltipMessage | string | opis pomocniczy prezentowany przy polu |
| flow | obiekt | Obiekt przechowujący definicję nawigacji pomiędzy stronami |
| flow.links | tablica | Tablica takich definicji, przejście ze strony A na stronę B traktowane jako jeden obiekt |
| flow.links.id | string | identyfikator przejścia UUID |
| flow.links.source | string | identyfikator strony źródłowej |
| flow.links.target | string | identyfikator strony docelowej |