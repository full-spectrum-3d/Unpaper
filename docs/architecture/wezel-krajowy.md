# Integracja z Węzłem Krajowym (login.gov.pl) – ścieżka wdrożenia

| | |
|---|---|
| Status | plan wdrożenia, **nie jest częścią rozwiązania ocenianego na hackathonie** |
| Data | 2026-11-21 |
| Dotyczy | uwierzytelniania urzędników korzystających z API i frontendu |
| Powiązane | [01-system.md – Uwierzytelnianie](01-system.md#uwierzytelnianie); `backend/app/core/security.py` |

## 1. Kontekst

Domyślnie API wydaje własne tokeny JWT dla jednego konta technicznego (HS256). To wystarcza
do oceny i działa offline. W docelowym wdrożeniu w COI urzędnik powinien logować się
tożsamością państwową – przez Węzeł Krajowy (login.gov.pl: profil zaufany, e-dowód, bankowość).

## 2. Dlaczego API nie łączy się z Węzłem bezpośrednio

- **Protokół.** Węzeł Krajowy integruje dostawców usług przez **SAML 2.0** (podpisane
  i szyfrowane komunikaty XML, XML Signature / XML Encryption, artifact binding, własne
  certyfikaty do podpisu i szyfrowania). Nie wydaje tokenów JWT.
- **Przeglądarka.** Logowanie przez Węzeł to przekierowania w przeglądarce użytkownika.
  Bezstanowe REST API nie może go samo przeprowadzić.
- **Formalności.** Integracja wymaga zgłoszenia podmiotu do COI, wymiany metadanych
  i certyfikatów oraz testów na środowisku integracyjnym (`int.login.gov.pl`).
- **Wymagania konkursu.** Rozwiązanie nie może zależeć w działaniu od zewnętrznych usług.
  Węzeł zostaje więc poza konfiguracją domyślną.
- **Uwierzytelnienie ≠ uprawnienie.** Węzeł potwierdza, *kim* jest osoba (PESEL, imię,
  nazwisko). Zaloguje się każdy obywatel z profilem zaufanym, a nie tylko urzędnik.
  Uprawnienie („jest urzędnikiem tego urzędu”) musi nadać inny element.

## 3. Architektura docelowa

```
            ┌──────────────┐  1. logowanie (OIDC, PKCE)  ┌──────────────────────────┐
urzędnik ──▶│ frontend SPA │────────────────────────────▶│ broker tożsamości        │
            │ (Angular)    │◀────────────────────────────│ np. Keycloak (Apache-2.0)│
            └──────┬───────┘  4. access token JWT RS256  │                          │
                   │                                     │ 2. SAML 2.0 ▲ │ 3. asercja│
                   │ 5. Authorization: Bearer <JWT>      └─────────────┼─▼──────────┘
                   ▼                                            ┌──────┴────────┐
            ┌──────────────┐                                    │ login.gov.pl  │
            │ api (FastAPI)│  weryfikacja podpisu kluczem       │ Węzeł Krajowy │
            │ tryb „tylko  │  publicznym brokera – bez          └───────────────┘
            │ weryfikacja” │  wywołań sieciowych
            └──────────────┘
```

1. Frontend przekierowuje urzędnika do brokera (OpenID Connect, authorization code + PKCE).
2. Broker, skonfigurowany jako dostawca usług Węzła, przekierowuje dalej do login.gov.pl (SAML).
3. Węzeł zwraca asercję z tożsamością. Broker mapuje ją na konto użytkownika
   i nadaje role (np. `formularze-urzednik` – ręcznie przez administratora lub z katalogu urzędu).
4. Broker wydaje frontendowi access token JWT podpisany RS256.
5. Frontend wywołuje API z tokenem. API sprawdza podpis, `iss`, `aud`, ważność i rolę.

**Nasz kod nie zawiera nic z SAML ani Węzła.** Cała integracja z login.gov.pl żyje w brokerze,
który jest standardowym, wymienialnym komponentem. Broker może być wspólny dla wielu
systemów COI – jeśli Generator Formularzy ma już własne logowanie, podpinamy się pod nie
tą samą konfiguracją.

## 4. Konfiguracja API

Bez zmian w kodzie – tylko zmienne środowiskowe (pełna lista: `README.md`, sekcja „Konfiguracja”):

| Zmienna | Wartość dla Keycloak (przykład) | Znaczenie |
|---|---|---|
| `JWT_ALGORITHM` | `RS256` | podpis asymetryczny |
| `JWT_PUBLIC_KEY` | klucz publiczny realmu (PEM) | weryfikacja podpisu; **bez** `JWT_PRIVATE_KEY` → API nie wydaje tokenów, `/auth/token` nie istnieje |
| `JWT_ISSUER` | `https://sso.example.gov.pl/realms/coi` | musi być równy `iss` w tokenie |
| `JWT_AUDIENCE` | `coi-cf-api` | klient API w brokerze (mapper „audience”) |
| `JWT_SUBJECT_CLAIM` | `preferred_username` | claim z identyfikatorem użytkownika (Keycloak ma w `sub` UUID) |
| `JWT_ROLES_CLAIM` | `realm_access.roles` | gdzie w tokenie są role (ścieżka z kropkami = zagnieżdżenie) |
| `JWT_REQUIRED_ROLE` | `formularze-urzednik` | token bez tej roli → **403 `FORBIDDEN`** |
| `JWT_LEEWAY_S` | `30` | tolerancja różnicy zegarów |

Zachowanie API:
- token zły, wygasły, z innego `iss`/`aud` albo bez claimu użytkownika → **401** `INVALID_TOKEN`;
- token poprawny, ale bez wymaganej roli → **403** `FORBIDDEN`
  z `WWW-Authenticate: Bearer error="insufficient_scope"`;
- role mogą być listą (`["a", "b"]`) albo napisem rozdzielonym spacjami (styl `scope`).

Te same zmienne działają z własnymi tokenami API: przy `JWT_REQUIRED_ROLE` token wydany
przez `/auth/token` dostaje tę rolę w `JWT_ROLES_CLAIM`, więc obie ścieżki przechodzą
tę samą weryfikację.

## 5. Co trzeba zrobić przy wdrożeniu

| # | Krok | Kto |
|---|---|---|
| 1 | Zgłoszenie systemu jako dostawcy usług Węzła Krajowego, wymiana metadanych SAML i certyfikatów (kontakt: Integracje.WK@coi.gov.pl) | COI / właściciel systemu |
| 2 | Uruchomienie brokera (lub użycie istniejącego SSO COI) i konfiguracja Węzła jako zewnętrznego dostawcy tożsamości SAML. **Do weryfikacji:** czy wybrany broker obsługuje wymagania Węzła (artifact binding, szyfrowanie asercji, wymagane algorytmy); w razie braku – rozszerzenie brokera albo inny produkt | administrator SSO |
| 3 | Testy na środowisku integracyjnym `int.login.gov.pl` | zespół wdrożeniowy |
| 4 | Klient OIDC `coi-cf-frontend` (public, PKCE) i klient/audience `coi-cf-api` w brokerze; mapper roli `formularze-urzednik` | administrator SSO |
| 5 | Konfiguracja API zmiennymi z §4 | zespół wdrożeniowy |
| 6 | Frontend: logowanie przez OIDC zamiast formularza login/hasło (biblioteka OIDC open source bez copyleftu, np. `angular-auth-oidc-client`, MIT – do weryfikacji); slice `auth` w NgRx przechowuje token z brokera | zespół frontendu |
| 7 | Procedura rotacji kluczy brokera (§6) | administrator SSO |

## 6. Ograniczenia i decyzje

- **Klucz statyczny, bez JWKS.** API nie pobiera kluczy z sieci (wymóg braku zależności
  zewnętrznych w rozwiązaniu konkursowym). Skutek: po rotacji klucza brokera trzeba podmienić
  `JWT_PUBLIC_KEY` i zrestartować API. Jeśli w docelowym wdrożeniu dopuszczalne jest
  pobieranie JWKS z brokera w sieci wewnętrznej, to naturalne rozszerzenie `core/security.py`.
- **Jedna rola.** `JWT_REQUIRED_ROLE` to pojedyncza rola dostępu do całego API. Rozróżnianie
  uprawnień między endpointami (np. tylko odczyt) nie jest potrzebne w obecnym zakresie.
- **Brak danych osobowych w API.** API potrzebuje tylko identyfikatora użytkownika
  (do logów) i ról. PESEL z Węzła zostaje w brokerze – nie mapujemy go do tokenu dla API.
- **Ścieżki claimów** obsługują nazwy z literami, cyframi i znakami `_ : -`. Claimy
  w formie URL (np. `https://example/roles`) nie są obsługiwane.

## 7. Źródła

- [Budowa Krajowego Węzła Identyfikacji Elektronicznej – gov.pl](https://www.gov.pl/cyfryzacja/budowa-krajowego-wezla-identyfikacji-elektronicznej)
- [Specyfikacja komunikacji login.gov.pl – dostawca usług (gov.pl)](https://www.gov.pl/attachment/17973318-759b-4077-be79-496007cb776d)
- [Dokumentacja COI dot. integracji (gov.pl)](https://www.gov.pl/attachment/9ae72f17-b48c-4593-8139-5f5dbfa639a5)
- [laravel-wezel-krajowy – przykład integracji SAML z artifact binding](https://packagist.org/packages/beziworld/laravel-wezel-krajowy)
