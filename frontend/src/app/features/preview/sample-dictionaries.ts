import { signal } from '@angular/core';

// Słowniki do podglądu. TERYT (pełny: wszystkie powiaty, gminy i miejscowości) przychodzi
// z backendu (GET /api/v1/dictionaries/teryt) po zarejestrowaniu loadera; bez niego
// (testy, Storybook) używana jest poniższa próbka. Kraje i numery kierunkowe są lokalne.
export interface DictionaryNode {
  name: string;
  /** Identyfikator TERYT (gminy z backendu). */
  code?: string;
  children?: DictionaryNode[];
}
export interface Dictionary {
  levels: string[];
  items: DictionaryNode[];
}

const byPl = (a: string, b: string) => a.localeCompare(b, 'pl');
const flat = (names: string[]): DictionaryNode[] => [...names].sort(byPl).map((name) => ({ name }));
const node = (name: string, ...children: DictionaryNode[]): DictionaryNode => ({ name, children });
const leaf = (name: string): DictionaryNode => ({ name });
/** Powiat → gmina → miejscowość. */
const place = (powiat: string, gmina: string, ...miejscowosci: string[]): DictionaryNode =>
  node(powiat, node(gmina, ...miejscowosci.map(leaf)));
/** Miasto na prawach powiatu: powiat, gmina i miejscowość o tej samej nazwie. */
const city = (name: string): DictionaryNode => place(name, name, name);

const COUNTRIES = [
  'Afganistan', 'Albania', 'Algieria', 'Andora', 'Angola', 'Antigua i Barbuda', 'Arabia Saudyjska',
  'Argentyna', 'Armenia', 'Australia', 'Austria', 'Azerbejdżan', 'Bahamy', 'Bahrajn', 'Bangladesz',
  'Barbados', 'Belgia', 'Belize', 'Benin', 'Bhutan', 'Białoruś', 'Birma', 'Boliwia',
  'Bośnia i Hercegowina', 'Botswana', 'Brazylia', 'Brunei', 'Bułgaria', 'Burkina Faso', 'Burundi',
  'Chile', 'Chiny', 'Chorwacja', 'Cypr', 'Czad', 'Czarnogóra', 'Czechy', 'Dania',
  'Demokratyczna Republika Konga', 'Dominika', 'Dominikana', 'Dżibuti', 'Egipt', 'Ekwador',
  'Erytrea', 'Estonia', 'Eswatini', 'Etiopia', 'Fidżi', 'Filipiny', 'Finlandia', 'Francja', 'Gabon',
  'Gambia', 'Ghana', 'Grecja', 'Grenada', 'Gruzja', 'Gujana', 'Gwatemala', 'Gwinea',
  'Gwinea Bissau', 'Gwinea Równikowa', 'Haiti', 'Hiszpania', 'Holandia', 'Honduras', 'Indie',
  'Indonezja', 'Irak', 'Iran', 'Irlandia', 'Islandia', 'Izrael', 'Jamajka', 'Japonia', 'Jemen',
  'Jordania', 'Kambodża', 'Kamerun', 'Kanada', 'Katar', 'Kazachstan', 'Kenia', 'Kirgistan',
  'Kiribati', 'Kolumbia', 'Komory', 'Kongo', 'Korea Południowa', 'Korea Północna', 'Kostaryka',
  'Kuba', 'Kuwejt', 'Laos', 'Lesotho', 'Liban', 'Liberia', 'Libia', 'Liechtenstein', 'Litwa',
  'Luksemburg', 'Łotwa', 'Macedonia Północna', 'Madagaskar', 'Malawi', 'Malediwy', 'Malezja',
  'Mali', 'Malta', 'Maroko', 'Mauretania', 'Mauritius', 'Meksyk', 'Mikronezja', 'Mołdawia',
  'Monako', 'Mongolia', 'Mozambik', 'Namibia', 'Nauru', 'Nepal', 'Niemcy', 'Niger', 'Nigeria',
  'Nikaragua', 'Norwegia', 'Nowa Zelandia', 'Oman', 'Pakistan', 'Palau', 'Palestyna', 'Panama',
  'Papua-Nowa Gwinea', 'Paragwaj', 'Peru', 'Polska', 'Portugalia', 'Republika Południowej Afryki',
  'Republika Środkowoafrykańska', 'Republika Zielonego Przylądka', 'Rosja', 'Rumunia', 'Rwanda',
  'Saint Kitts i Nevis', 'Saint Lucia', 'Saint Vincent i Grenadyny', 'Salwador', 'Samoa',
  'San Marino', 'Senegal', 'Serbia', 'Seszele', 'Sierra Leone', 'Singapur', 'Słowacja', 'Słowenia',
  'Somalia', 'Sri Lanka', 'Stany Zjednoczone', 'Sudan', 'Sudan Południowy', 'Surinam', 'Syria',
  'Szwajcaria', 'Szwecja', 'Tadżykistan', 'Tajlandia', 'Tanzania', 'Timor Wschodni', 'Togo',
  'Tonga', 'Trynidad i Tobago', 'Tunezja', 'Turcja', 'Turkmenistan', 'Tuvalu', 'Uganda', 'Ukraina',
  'Urugwaj', 'Uzbekistan', 'Vanuatu', 'Watykan', 'Wenezuela', 'Węgry', 'Wielka Brytania', 'Wietnam',
  'Włochy', 'Wybrzeże Kości Słoniowej', 'Wyspy Marshalla', 'Wyspy Salomona',
  'Wyspy Świętego Tomasza i Książęca', 'Zambia', 'Zimbabwe', 'Zjednoczone Emiraty Arabskie',
];

const SAMPLE_TERYT: Dictionary = {
  levels: ['Województwo', 'Powiat', 'Gmina', 'Miejscowość'],
  items: [
    node('dolnośląskie', city('Wrocław'), place('wrocławski', 'Kobierzyce', 'Kobierzyce')),
    node('kujawsko-pomorskie', city('Bydgoszcz'), city('Toruń')),
    node('lubelskie', city('Lublin')),
    node('lubuskie', city('Gorzów Wielkopolski'), city('Zielona Góra')),
    node('łódzkie', city('Łódź')),
    node(
      'małopolskie',
      city('Kraków'),
      place('wielicki', 'Wieliczka', 'Wieliczka', 'Kokotów'),
      place('tatrzański', 'Zakopane', 'Zakopane'),
    ),
    node(
      'mazowieckie',
      city('Warszawa'),
      place('piaseczyński', 'Piaseczno', 'Piaseczno', 'Zalesie Górne'),
      place('pruszkowski', 'Pruszków', 'Pruszków'),
    ),
    node('opolskie', city('Opole')),
    node('podkarpackie', city('Rzeszów')),
    node('podlaskie', city('Białystok')),
    node('pomorskie', city('Gdańsk'), city('Gdynia')),
    node('śląskie', city('Katowice')),
    node('świętokrzyskie', city('Kielce')),
    node('warmińsko-mazurskie', city('Olsztyn')),
    node('wielkopolskie', city('Poznań')),
    node('zachodniopomorskie', city('Szczecin')),
  ],
};

/** Unique names at one TERYT depth (0 = województwo), for single-level dictionaries. */
const tier = (teryt: Dictionary, depth: number): Dictionary => {
  let nodes = teryt.items;
  for (let d = 0; d < depth; d++) nodes = nodes.flatMap((n) => n.children ?? []);
  return { levels: [teryt.levels[depth]], items: flat([...new Set(nodes.map((n) => n.name))]) };
};

/** All dictionaries backed by the TERYT tree, by name. */
const terytDictionaries = (teryt: Dictionary): Record<string, Dictionary> => ({
  TERYT_4G_DOWODOWY: teryt,
  TERYT_DOWODOWY: teryt,
  // Single-level TERYT dictionaries the backend binds to bare "Województwo:" / "Powiat:" labels.
  Województwo: tier(teryt, 0),
  Powiat: tier(teryt, 1),
  Gmina: tier(teryt, 2),
  Miejscowość: tier(teryt, 3),
});

const LOCAL_DICTIONARIES: Readonly<Record<string, Dictionary>> = {
  Kraje: { levels: ['Kraj'], items: flat(COUNTRIES) },
  NUMERY_KIERUNKOWE: {
    levels: ['Numer kierunkowy'],
    items: [
      '+48 Polska', '+49 Niemcy', '+44 Wielka Brytania', '+33 Francja', '+39 Włochy',
      '+34 Hiszpania', '+420 Czechy', '+421 Słowacja', '+380 Ukraina', '+370 Litwa', '+1 Stany Zjednoczone',
    ].map(leaf),
  },
};

export const SAMPLE_DICTIONARIES: Readonly<Record<string, Dictionary>> = {
  ...LOCAL_DICTIONARIES,
  ...terytDictionaries(SAMPLE_TERYT),
};
const TERYT_NAMES = new Set(Object.keys(terytDictionaries(SAMPLE_TERYT)));

export type TerytLoader = () => Promise<Dictionary>;
const RETRY_MS = 10_000;
let loader: TerytLoader | undefined;
let pending = false;
let failedAt = -Infinity;
const remoteTeryt = signal<Record<string, Dictionary> | undefined>(undefined);

/** Switches TERYT dictionaries to the full backend data, fetched on first use. */
export function setTerytLoader(load: TerytLoader | undefined): void {
  loader = load;
  pending = false;
  failedAt = -Infinity;
  remoteTeryt.set(undefined);
}

function requestTeryt(load: TerytLoader): void {
  if (pending || Date.now() - failedAt < RETRY_MS) return;
  pending = true;
  load().then(
    (teryt) => {
      if (loader !== load) return;
      pending = false;
      remoteTeryt.set(terytDictionaries(teryt));
    },
    () => {
      if (loader !== load) return;
      pending = false;
      failedAt = Date.now();
    },
  );
}

/**
 * Synchronous lookup, reactive inside computed()/templates: with a loader registered,
 * TERYT dictionaries are undefined until the backend data arrives, then update in place.
 */
export function findDictionary(name: string | undefined): Dictionary | undefined {
  if (name === undefined) return undefined;
  if (!TERYT_NAMES.has(name) || !loader) return SAMPLE_DICTIONARIES[name];
  const remote = remoteTeryt();
  if (!remote) requestTeryt(loader);
  return remote?.[name];
}
