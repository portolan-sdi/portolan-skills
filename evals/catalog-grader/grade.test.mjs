// Tests for the programmatic checks in grade.mjs. No model calls.
// Run: node --test evals/

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { coverage, norm, quoteCheck, ruleViolations } from './grade.mjs';

const AREAS = ['machine-contract', 'honesty', 'documentation', 'access', 'visuals', 'organization', 'maintenance', 'concision'];

function report(grades, extra = {}) {
  const areas = Object.fromEntries(AREAS.map((a, i) => [a, { grade: grades[i], summary: '' }]));
  return {
    grade: 'B', complete: true, ceiling: { grade: 'none', reason: '' }, invented_claims: 0, areas,
    a_requirements: { met: false, requirements: { git: { met: false, evidence: '' } } },
    a_plus: { awarded: false }, findings: [], checked: { collections_read: [] }, ...extra,
  };
}

const CLEAN = { rashid: { error_count: 0 }, crawl_errors: [], links: {} };

test('overall grade is the lowest area', () => {
  const rep = report(['B', 'A', 'A', 'A', 'C', 'A', 'B', 'B'], { grade: 'C' });
  assert.deepEqual(ruleViolations(rep, CLEAN, true), []);
  assert.match(ruleViolations({ ...rep, grade: 'B' }, CLEAN, true)[0], /give C, report says B/);
});

test('five A areas among the other seven raise the grade one step', () => {
  const rep = report(['C', 'A', 'A', 'A', 'A', 'A', 'B', 'B'], { grade: 'B' });
  assert.deepEqual(ruleViolations(rep, CLEAN, true), []);
});

test('the raise never passes A, and A needs the A requirements', () => {
  const rep = report(['B', 'A', 'A', 'A', 'A', 'A', 'A', 'A'], { grade: 'B' });
  assert.deepEqual(ruleViolations(rep, CLEAN, true), []);
  const met = { ...rep, grade: 'A', a_requirements: { met: true, requirements: { git: { met: true } } } };
  assert.deepEqual(ruleViolations(met, CLEAN, true), []);
});

test('invented claims cap the grade and must match the findings', () => {
  const one = [{ id: 'F1', severity: 'invented' }];
  const rep = report(['A', 'A', 'A', 'A', 'A', 'B', 'B', 'B'], { grade: 'C', invented_claims: 1, findings: one });
  assert.deepEqual(ruleViolations(rep, CLEAN, true), []);
  const two = [...one, { id: 'F2', severity: 'invented' }];
  assert.deepEqual(ruleViolations({ ...rep, grade: 'D', invented_claims: 2, findings: two }, CLEAN, true), []);
  assert.match(ruleViolations({ ...rep, invented_claims: 0 }, CLEAN, true)[0], /invented_claims=0 but 1/);
});

test('rashid errors need a D ceiling', () => {
  const facts = { ...CLEAN, rashid: { error_count: 8 } };
  const rep = report(['B', 'A', 'A', 'A', 'B', 'A', 'B', 'B'], { grade: 'D', ceiling: { grade: 'D', reason: '' } });
  assert.deepEqual(ruleViolations(rep, facts, true), []);
  const v = ruleViolations({ ...rep, grade: 'B', ceiling: { grade: 'none' } }, facts, true);
  assert.ok(v.some(x => /need a D ceiling/.test(x)));
});

test('rashid not running, or the node limit, makes the report incomplete', () => {
  const rep = report(['B', 'B', 'B', 'B', 'B', 'B', 'B', 'B'], { grade: 'C', ceiling: { grade: 'C', reason: '' } });
  const noRashid = { ...CLEAN, rashid: { error: 'rashid timed out after 1200s' } };
  assert.match(ruleViolations(rep, noRashid, true).join(), /must be marked incomplete/);
  assert.deepEqual(ruleViolations({ ...rep, complete: false }, noRashid, true), []);
  const limit = { ...CLEAN, crawl_errors: [{ href: 'x', error: 'node limit 400 reached, not crawled' }] };
  assert.match(ruleViolations({ ...rep, ceiling: { grade: 'none' }, grade: 'B' }, limit, true).join(), /node limit/);
});

test('no repository keeps the grade at B or lower', () => {
  const rep = report(['A', 'A', 'A', 'A', 'A', 'A', 'A', 'A'], { grade: 'A', a_requirements: { met: true, requirements: { git: { met: true } } } });
  const v = ruleViolations(rep, CLEAN, false);
  assert.ok(v.some(x => /B or lower/.test(x)));
  assert.ok(v.some(x => /git requirement marked met/.test(x)));
});

test('quotes must appear verbatim after whitespace and quote-mark normalization', () => {
  const docs = [{ path: 'docs/a/README.md', text: 'The data has\n  6,316 stops. It is “complete”.' }];
  const rep = { findings: [
    { id: 'F1', quote: 'The data has 6,316 stops.' },
    { id: 'F2', quote: 'It is "complete".' },
    { id: 'F3', quote: 'The data has 6,317 stops.' },
    { id: 'F4', quote: null },
  ] };
  const q = quoteCheck(rep, docs);
  assert.equal(q.total, 3);
  assert.deepEqual(q.missing.map(m => m.id), ['F3']);
  assert.equal(norm('a\\nb'), 'a b');
});

test('coverage counts collections by full path or unique leaf id', () => {
  const nodes = [{ path: '', type: 'Catalog' }, { path: 'sub', type: 'Catalog' }];
  for (let i = 0; i < 20; i++) nodes.push({ path: `sub/c${i}`, type: 'Collection' });
  nodes.push({ path: 'other/c0', type: 'Collection' }); // makes leaf c0 ambiguous
  const facts = { nodes };
  const read = ['.', 'sub', 'c0', ...Array.from({ length: 11 }, (_, i) => `sub/c${i + 1}`)];
  const cov = coverage({ checked: { collections_read: read } }, facts);
  assert.equal(cov.total, 21);
  assert.equal(cov.required, 12);
  assert.equal(cov.read, 11); // '.', 'sub' are catalogs and 'c0' is ambiguous
  assert.equal(cov.ok, false);
  const all = coverage({ checked: { collections_read: [...read, 'c12'] } }, facts);
  assert.equal(all.ok, true);
});

test('a small catalog needs every collection read', () => {
  const facts = { nodes: [{ path: 'a', type: 'Collection' }, { path: 'b', type: 'Collection' }] };
  assert.equal(coverage({ checked: { collections_read: ['a'] } }, facts).ok, false);
  assert.equal(coverage({ checked: { collections_read: ['./a', 'b/'] } }, facts).ok, true);
});
