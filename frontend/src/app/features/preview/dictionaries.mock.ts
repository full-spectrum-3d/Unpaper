// Dane przykładowe do podglądu: backend nie dostarcza pozycji słowników predefiniowanych.
export interface DictionaryNode {
  name: string;
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

const TERYT: Dictionary = {
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

export const SAMPLE_DICTIONARIES: Readonly<Record<string, Dictionary>> = {
  Kraje: { levels: ['Kraj'], items: flat(COUNTRIES) },
  TERYT_4G_DOWODOWY: TERYT,
  TERYT_DOWODOWY: TERYT,
  NUMERY_KIERUNKOWE: {
    levels: ['Numer kierunkowy'],
    items: [
      '+48 Polska', '+49 Niemcy', '+44 Wielka Brytania', '+33 Francja', '+39 Włochy',
      '+34 Hiszpania', '+420 Czechy', '+421 Słowacja', '+380 Ukraina', '+370 Litwa', '+1 Stany Zjednoczone',
    ].map(leaf),
  },
};

export function findDictionary(name: string | undefined): Dictionary | undefined {
  return name === undefined ? undefined : SAMPLE_DICTIONARIES[name];
}
