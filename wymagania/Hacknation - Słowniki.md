**Słowniki, wykorzystywane w formularzach eUsług**

Formularze eUsług mogą wykorzystywać słowniki, w celu dostarczenia gotowego, predefiniowanego zestawu odpowiedzi oczekiwanych przez system w danym polu. Użytkownik podczas wypełniania formularza, w polu korzystającym ze słownika, nie wprowadza wartości ręcznie, tylko wybiera konkretną pozycję ze słownika.

Zależnie od konfiguracji pola udostępniającego słownik Użytkownik może wybrać jedną lub więcej pozycji.

**Słownik może być podpięty wyłącznie w polach typu Lista rozwijalna, radiobutton, checkbox.**

**Sposób działania słowników na formularzach eUsług na przykładzie słownika Kraje.**

1. **Pole formularza zostaje powiązane ze słownikiem krajów** w konfiguracji formularza (w pliku json).
2. Formularz eUsługi **udostępnia użytkownikowi wartości pochodzące ze słownika**, np. w formie listy wyboru.
3. Użytkownik wybiera pozycję z listy państw dostępnych w słowniku zamiast wprowadzać nazwę państwa jako dowolny tekst.
4. Wybrana wartość jest zapisywana jako wartość pola formularza i może zostać wykorzystana w dalszym przetwarzaniu danych eUsługi.
5. Zastosowanie wspólnego słownika zapewnia **spójność i standaryzację danych**, w szczególności eliminuje różne warianty zapisu tej samej nazwy.

**Dostępne predefiniowane słowniki do wykorzystania w formularzach:**

1. **Słownik Województwo** – ustandaryzowany zbiór województw występujących w Polsce;
2. **Słownik Powiat** – ustandaryzowany zbiór powiatów występujących w Polsce;
3. **Słownik Gmina** – ustandaryzowany zbiór gmin występujących w Polsce;
4. **Słownik Miejscowość** – ustandaryzowany zbiór miejscowości występujących w Polsce;

**Słowniki Województwo, Powiat, Gmina, Miejscowość** mogą być wykorzystywane w formularzach eUsług wszędzie tam, gdzie wymagane jest wskazanie danych adresowych.

Można je przypisać **wyłącznie do pola typu lista rozwijalna.**

1. **Słownik Kraje** – ustandaryzowany zbiór państw;

**Słownik krajów** może być wykorzystywany w formularzach eUsług wszędzie tam, gdzie wymagane jest wskazanie kraju, np. kraju urodzenia, obywatelstwa, zamieszkania lub adresu zagranicznego.

Słownik Kraje można przypisać **wyłącznie do pola typu lista rozwijalna.**

1. **Słownik Numery kierunkowe -** ustandaryzowany zbiór międzynarodowych prefiksów telefonicznych przypisanych do krajów;

**Słownik numerów kierunkowych** może być wykorzystywany w formularzach eUsług w polach przeznaczonych do podawania numeru telefonu. Pozwala użytkownikowi wybrać właściwy kod kraju, np. **+48 dla Polski**, zamiast wprowadzać go ręcznie.

Jeżeli podczas analizy formularzy widzisz możliwość zastosowania innego nowego słownika – zaproponuj jego nazwę, strukturę i zastosowanie w formularzu (opcjonalne rozszerzenie).