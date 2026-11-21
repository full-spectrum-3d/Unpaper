import { FormDefinition, FormTab, Question } from './form-definition';

export function orderTabs(def: FormDefinition): FormTab[] {
  const links = def.flow?.links ?? [];
  const byId = new Map(def.tabs.map((t) => [t.id, t]));
  const mains = def.tabs.filter((t) => t.type !== 'FINISH');
  const start =
    mains.find((t) => !links.some((l) => l.target === t.id && byId.has(l.source))) ?? mains[0];

  const ordered: FormTab[] = [];
  const seen = new Set<string>();
  const visit = (tab: FormTab | undefined) => {
    for (let t = tab; t && !seen.has(t.id);) {
      seen.add(t.id);
      if (t.type !== 'FINISH') ordered.push(t);
      t = byId.get(links.find((l) => l.source === t!.id && byId.has(l.target))?.target ?? '');
    }
  };
  visit(start);
  mains.forEach((t) => visit(t));
  return [...ordered, ...def.tabs.filter((t) => t.type === 'FINISH')];
}

export const sortQuestions = (qs: Question[]): Question[] =>
  [...qs].sort((a, b) => a.y - b.y || a.x - b.x);
