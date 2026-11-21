# Dane inicjalne – materiał dla zadania rozszerzającego zakres

Pola w formularzu mogą zostać zasilone danymi Obywatela pobranymi z zewnętrznych systemów.

- Jeżeli pole jest zasilane danymi inicjalnymi z Rejestru, to musi być ono oznaczone jako pole wyłącznie do odczytu.
- Na poziomie formularza Użytkownik nie ma możliwości modyfikacji danych w polu zasilanym danymi inicjalnymi.
- Jeżeli w źródle danych inicjalnych brakuje danych Użytkownika, to pole na formularzu nie zostaje zasilone żadną wartością i użytkownik nie może ręcznie tych danych uzupełnić.

Żeby pole w formularzu było zasilane danymi inicjalnymi, to na poziomie pojedynczego pola należy skonfigurować dla niego:

- Źródło danych – wskazanie systemu, z którego dane będą pobierane, np. rejestr PESEL
- Atrybut – jaka wartość z danego systemu powinna zasilić dane Pole, np. Imię zalogowanego
- W jednym polu może być wskazane tylko jedno źródło danych i jeden atrybut z danego źródła danych

Specyfikacja takiego pola w Jsonie powinna zawierać:

- Wskazanie, że pole jest readOnly
- W polu defaultValue wskazanie źródła danych i atrybutu, np. `"defaultValue": "PESEL.name"`,
- W polu defaultValueType wskazanie, że dane pole jest zasilane danymi z zewnętrznego systemu, np. `"defaultValueType": "EXTERNAL_SYSTEM"`,

## Dostępne źródła danych dla formularzy oraz zakres atrybutów

| Lp. | Źródło danych inicjalnych | Nazwa Rejestru |
| --- | --- | --- |
| 1 | PESEL | Rejestr PESEL |
| 2 | PESEL_ADDRESS | Dane zameldowania |
| 3 | MLPZ | Dane zalogowanego użytkownika |


## Rejestr PESEL – zakres danych

| Lp. | Atrybut | Nazwa | Typ pola |
| --- | --- | --- | --- |
| 1 | `pesel` | Pesel z PESEL | Pole tekstowe |
| 2 | `name` | Imię z PESEL | Pole tekstowe |
| 3 | `surname` | Nazwisko z PESEL | Pole tekstowe |
| 4 | `birthDate` | Data urodzenia z PESEL | Datepicker |
| 5 | `citizenship` | Narodowość z PESEL | Pole tekstowe |
| 6 | `motherName` | Imię matki z PESEL | Pole tekstowe |
| 7 | `birthPlace` | Miejsce urodzenia z PESEL | Pole tekstowe |
| 8 | `motherSurname` | Nazwisko matki z PESEL | Pole tekstowe |
| 9 | `sex` | Płeć z PESEL | Pole tekstowe |
| 10 | `fatherName` | Imię ojca z PESEL | Pole tekstowe |
| 11 | `secondName` | Drugie imię z PESEL | Pole tekstowe |
| 12 | `birthCountry` | Kraj urodzenia z PESEL | Pole tekstowe |
| 13 | `foreignBirthUSC` | Zagraniczne miasto USC urodzenia z PESEL | Pole tekstowe |
| 14 | `familyName` | Nazwisko rodowe z PESEL | Pole tekstowe |
| 15 | `fatherSurname` | Nazwisko ojca z PESEL | Pole tekstowe |
| 16 | `maritalStatus` | Stan cywilny z PESEL |  |

## Dane zameldowania – zakres danych

| Lp. | Atrybut | Nazwa | Typ pola |
| --- | --- | --- | --- |
| 1 | `temporaryAddressVoivodeship` | Tymczasowy adres zameldowania: województwo z PESEL | Pole tekstowe |
| 2 | `temporaryAddressDistrict` | Tymczasowy adres zameldowania: region z PESEL |  |
| 3 | `temporaryAddressCommunity` | Tymczasowy adres zameldowania: gmina z PESEL | Pole tekstowe |
| 4 | `temporaryAddressPlace` | Tymczasowy adres zameldowania: Miejscowość z PESEL | Pole tekstowe |
| 5 | `temporaryAddressStreetType` | Tymczasowy adres zameldowania: Typ ulicy z PESEL | Pole tekstowe |
| 6 | `temporaryAddressStreet` | Tymczasowy adres zameldowania: Ulica z PESEL | Pole tekstowe |
| 7 | `temporaryAddressHouseNumber` | Tymczasowy adres zameldowania: Numer domu z PESEL | Pole tekstowe |
| 8 | `temporaryAddressApartmentNumber` | Tymczasowy adres zameldowania: Numer lokalu z PESEL | Pole tekstowe |
| 9 | `temporaryAddressPostalCode` | Tymczasowy adres zameldowania: Kod pocztowy z PESEL | Pole tekstowe |
| 10 | `permanentAddressVoivodeship` | Stały adres zameldowania: województwo z PESEL | Pole tekstowe |
| 11 | `permanentAddressDistrict` | Stały adres zameldowania: region z PESEL | Pole tekstowe |
| 12 | `permanentAddressCommunity` | Stały adres zameldowania: gmina z PESEL | Pole tekstowe |
| 13 | `permanentAddressPlace` | Stały adres zameldowania: Miejscowość z PESEL | Pole tekstowe |
| 14 | `permanentAddressStreetType` | Stały adres zameldowania: Typ ulicy z PESEL | Pole tekstowe |
| 15 | `permanentAddressStreet` | Stały adres zameldowania: Ulica z PESEL | Pole tekstowe |
| 16 | `permanentAddressPostalCode` | Stały adres zameldowania: Kod pocztowy z PESEL | Pole tekstowe |
| 17 | `permanentAddressHouseNumber` | Stały adres zameldowania: Numer domu z PESEL | Pole tekstowe |
| 18 | `permanentAddressApartmentNumber` | Stały adres zameldowania: Numer lokalu z PESEL | Pole tekstowe |

## Dane zalogowanego użytkownika – zakres danych

| Lp. | Atrybut | Nazwa | Typ pola |
| --- | --- | --- | --- |
| 1 | `name` | Imię z MLPZ | Pole tekstowe |
| 2 | `secondName` | Drugie Imię z MLPZ | Pole tekstowe |
| 3 | `surname` | Nazwisko z MLPZ | Pole tekstowe |
| 4 | `pesel` | Wartość PESEL z MLPZ | Pole tekstowe |
| 5 | `phoneNumber` | Numer telefonu z MLPZ | Pole tekstowe |
| 6 | `email` | Adres email z MLPZ | Pole tekstowe |
| 7 | `country` | Kraj z MLPZ | Pole tekstowe |
| 8 | `voivodeship` | Województwo z MLPZ | Pole tekstowe |
| 9 | `district` | Dzielnica z MLPZ | Pole tekstowe |
| 10 | `community` | Gmina z MLPZ | Pole tekstowe |
| 11 | `place` | Miejscowość z MLPZ | Pole tekstowe |
| 12 | `postCode` | Kod pocztowy z MLPZ | Pole tekstowe |
| 13 | `street` | Ulica z MLPZ | Pole tekstowe |
| 14 | `building` | Nr budynku z MLPZ | Pole tekstowe |
| 15 | `apartment` | Nr lokalu z MLPZ | Pole tekstowe |
| 16 | `institutionName` | Nazwa Organizacji z MLPZ | Pole tekstowe |
| 17 | `descriptiveOrganizationName` | Opisowa nazwa organizacji z MLPZ | Pole tekstowe |

> Uwaga: w oryginalnym PDF pole „Typ pola” jest puste dla `temporaryAddressDistrict` oraz `maritalStatus`; kolejność atrybutów stałego adresu jest zgodna z oryginałem (kod pocztowy przed numerem domu).
