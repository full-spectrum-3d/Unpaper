import { computed } from '@angular/core';
import { Dictionary, DictionaryNode, findDictionary, setTerytLoader } from './sample-dictionaries';

const depthOk = (n: DictionaryNode, level: number): boolean =>
  level === 3 ? !n.children : !!n.children?.length && n.children.every((c) => depthOk(c, level + 1));

describe('findDictionary', () => {
  it('returns sorted countries', () => {
    const d = findDictionary('Kraje')!;
    const names = d.items.map((i) => i.name);
    expect(d.levels).toEqual(['Kraj']);
    expect(names).toEqual(expect.arrayContaining(['Polska', 'Niemcy', 'Ukraina']));
    expect(names.length).toBeGreaterThanOrEqual(190);
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, 'pl')));
  });

  it('returns TERYT tree with 4 levels', () => {
    const d = findDictionary('TERYT_4G_DOWODOWY')!;
    expect(d.levels).toEqual(['Województwo', 'Powiat', 'Gmina', 'Miejscowość']);
    expect(d.items.map((i) => i.name)).toEqual([
      'dolnośląskie', 'kujawsko-pomorskie', 'lubelskie', 'lubuskie', 'łódzkie', 'małopolskie',
      'mazowieckie', 'opolskie', 'podkarpackie', 'podlaskie', 'pomorskie', 'śląskie',
      'świętokrzyskie', 'warmińsko-mazurskie', 'wielkopolskie', 'zachodniopomorskie',
    ]);
    expect(d.items.every((w) => depthOk(w, 0))).toBe(true);
    for (const name of ['mazowieckie', 'małopolskie']) {
      expect(d.items.find((i) => i.name === name)!.children!.length).toBeGreaterThanOrEqual(2);
    }
  });

  it('aliases TERYT_DOWODOWY', () => {
    expect(findDictionary('TERYT_DOWODOWY')).toBe(findDictionary('TERYT_4G_DOWODOWY'));
  });

  it('derives single-level Województwo/Powiat/Gmina/Miejscowość from the TERYT tree', () => {
    const names = (n: string) => findDictionary(n)!.items.map((i) => i.name);
    expect(findDictionary('Województwo')!.levels).toEqual(['Województwo']);
    expect(names('Województwo')).toHaveLength(16);
    expect(names('Powiat')).toEqual(expect.arrayContaining(['Kraków', 'piaseczyński']));
    expect(names('Gmina')).toContain('Piaseczno');
    expect(names('Miejscowość')).toContain('Zalesie Górne');
    // Miasto na prawach powiatu występuje raz, choć jest powiatem, gminą i miejscowością.
    expect(names('Miejscowość').filter((n) => n === 'Kraków')).toHaveLength(1);
  });

  it('returns phone prefixes', () => {
    const d = findDictionary('NUMERY_KIERUNKOWE')!;
    expect(d.levels).toEqual(['Numer kierunkowy']);
    expect(d.items.map((i) => i.name)).toContain('+48 Polska');
    expect(d.items.length).toBeGreaterThanOrEqual(8);
  });

  it('returns undefined for unknown', () => {
    expect(findDictionary('Nieznany')).toBeUndefined();
    expect(findDictionary(undefined)).toBeUndefined();
  });
});

describe('findDictionary with a TERYT loader', () => {
  const full: Dictionary = {
    levels: ['Województwo', 'Powiat', 'Gmina', 'Miejscowość'],
    items: [
      {
        name: 'dolnośląskie',
        children: [
          {
            name: 'bolesławiecki',
            children: [{ name: 'Gromadka', code: '0201032', children: [{ name: 'Gromadka' }, { name: 'Wierzbowa' }] }],
          },
        ],
      },
    ],
  };
  afterEach(() => setTerytLoader(undefined));

  it('fetches TERYT once and serves it reactively to all TERYT dictionaries', async () => {
    const load = vi.fn(() => Promise.resolve(full));
    setTerytLoader(load);
    const powiaty = computed(() => findDictionary('Powiat')?.items.map((i) => i.name));

    expect(findDictionary('TERYT_4G_DOWODOWY')).toBeUndefined();
    expect(powiaty()).toBeUndefined();
    await Promise.resolve();

    expect(findDictionary('TERYT_DOWODOWY')).toBe(full);
    expect(powiaty()).toEqual(['bolesławiecki']);
    expect(findDictionary('Miejscowość')!.items.map((i) => i.name)).toEqual(['Gromadka', 'Wierzbowa']);
    expect(findDictionary('Kraje')!.items.length).toBeGreaterThan(190);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('does not retry immediately after a failed fetch', async () => {
    const load = vi.fn(() => Promise.reject(new Error('401')));
    setTerytLoader(load);
    findDictionary('Powiat');
    await Promise.resolve();
    await Promise.resolve();
    expect(findDictionary('Powiat')).toBeUndefined();
    expect(load).toHaveBeenCalledTimes(1);
  });
});
