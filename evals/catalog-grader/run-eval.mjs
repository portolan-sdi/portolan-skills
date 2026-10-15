#!/usr/bin/env node
// Catalog-grader eval; see README.md for usage and grade.mjs for scoring.
// Harness scaffold: github.com/anthropics/skills,
// skills/claude-api/shared/evals/report. Copyright Anthropic, Apache-2.0.

import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { homedir, tmpdir } from 'node:os';
import { closeSync, constants as FS, cpSync, existsSync, mkdtempSync, readdirSync, rmSync, symlinkSync, fstatSync, ftruncateSync, lstatSync, mkdirSync, openSync, readFileSync, realpathSync, writeFileSync, writeSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { claudeEnv, gradeReport, readDocs, spawnJson } from './grade.mjs';

// Refuse links in model-influenced output paths. Windows lacks O_NOFOLLOW.
const WIN = process.platform === 'win32';
const NOFOLLOW = WIN ? 0 : FS.O_NOFOLLOW;
// Only ENOENT means absent; other inspection failures must abort.
const lstatOrNull = p => { try { return lstatSync(p); } catch (e) { if (e?.code === 'ENOENT') return null; throw e; } };
const isSymlink = p => lstatOrNull(p)?.isSymbolicLink() === true;
// Strip terminal controls from model-influenced output.
const ESC_SEQ = /\x1b\[[0-?]*[ -\/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b[@-_]/g;
const CONTROL = /[\x00-\x1f\x7f-\x9f]/g;
const termSafe = s => String(s).replace(ESC_SEQ, '').replace(CONTROL, '');
const eprint = (...a) => console.error(...a.map(termSafe));
// Resolve parents to catch intermediate links. Separate checks and opens
// cannot prevent a concurrent directory swap; Node has no sync openat API.
let flowRealRoot = null;
function assertInFlow(dir, what) {
  if (flowRealRoot == null) throw new Error(`refusing to ${what}: flow root not resolved yet`);
  const dirReal = realpathSync(dir);
  if (dirReal !== flowRealRoot && !dirReal.startsWith(flowRealRoot + (WIN ? '\\' : '/')))
    throw new Error(`refusing to ${what}: ${dir} resolves outside the flow directory`);
}
function openNoFollow(p, flags) {
  if (isSymlink(dirname(p))) throw new Error(`refusing to open through symlinked directory: ${dirname(p)}`);
  assertInFlow(dirname(p), 'open');
  if (WIN && isSymlink(p)) throw new Error(`refusing to open through symlink: ${p}`);
  const fd = openSync(p, flags | NOFOLLOW, 0o644);
  try {
    const st = fstatSync(fd);
    if (!st.isFile()) throw new Error(`refusing to use non-regular file: ${p}`);
    // Hard links bypass symlink checks; runner-created files have one link.
    if (st.nlink > 1) throw new Error(`refusing to use ${p}: it has a second hard link (another name for the same file); replace it with a plain copy if it is yours`);
  } catch (e) { closeSync(fd); throw e; }
  return fd;
}
// Check before truncating; writeFileSync handles short writes.
function writeFileNoFollow(p, data) {
  const fd = openNoFollow(p, FS.O_WRONLY | FS.O_CREAT);
  try { ftruncateSync(fd, 0); writeFileSync(fd, data); } finally { closeSync(fd); }
}
// Bun on Windows needs an explicit offset for O_APPEND handles.
function appendFileNoFollow(p, data) {
  const fd = openNoFollow(p, FS.O_WRONLY | FS.O_CREAT | FS.O_APPEND);
  try {
    if (!WIN) { writeFileSync(fd, data); return; }
    const buf = Buffer.from(data);
    const start = fstatSync(fd).size;
    for (let off = 0; off < buf.length;) {
      const n = writeSync(fd, buf, off, buf.length - off, start + off);
      if (n <= 0) throw new Error(`append to ${p} made no progress`);
      off += n;
    }
  } finally { closeSync(fd); }
}
// Count symlinks as present so the freeze guard cannot overwrite them.
const lexists = p => lstatOrNull(p) != null;
function readFileNoFollow(p) {
  const fd = openNoFollow(p, FS.O_RDONLY);
  try { return readFileSync(fd, 'utf8'); } finally { closeSync(fd); }
}
function readIfPresent(p) {
  try { return readFileNoFollow(p); } catch (e) { if (e?.code === 'ENOENT') return null; throw e; }
}
function mkdirNoFollow(dir) {
  if (isSymlink(dir)) throw new Error(`refusing to use symlinked directory: ${dir}`);
  mkdirSync(dir, { recursive: true });
  // Recursive mkdir follows ancestor links; recheck before writing files.
  assertInFlow(dir, 'create directory');
}
// Readers and freeze guards must recognize the same reference extensions.
const REF_EXTS = ['', '.html', '.txt', '.json'];

// Catalog-grader cases

const EVAL_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(EVAL_DIR, '..', '..');
const AGENT_TOOLS = ['Read', 'Write', 'Edit', 'Glob', 'Grep', 'WebFetch', 'Skill',
  'Bash(python3 *)', 'Bash(uv run *)', 'Bash(jq *)', 'Bash(ls *)', 'Bash(wc *)', 'Bash(head *)'];
// Keep the judge distinct from the tested model.
const JUDGE_MODEL = process.env.CG_EVAL_JUDGE ?? 'claude-sonnet-5-5';

let staged = null; // { pluginDir, configDir }, made once per process
function stage() {
  if (staged) return staged;
  const root = mkdtempSync(join(tmpdir(), 'cg-eval-stage-'));
  const pluginDir = join(root, 'plugin');
  cpSync(join(REPO_ROOT, '.claude-plugin'), join(pluginDir, '.claude-plugin'), { recursive: true });
  cpSync(join(REPO_ROOT, 'skills'), join(pluginDir, 'skills'), { recursive: true });
  const configDir = join(root, 'config');
  mkdirSync(configDir, { mode: 0o700 });
  // Linux credentials can be linked; macOS Keychain login needs a token.
  const cred = join(homedir(), '.claude', '.credentials.json');
  if (existsSync(cred)) symlinkSync(cred, join(configDir, '.credentials.json'));
  else if (!process.env.ANTHROPIC_API_KEY && !process.env.CLAUDE_CODE_OAUTH_TOKEN)
    throw new Error('no credentials for the headless sessions: set CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`) or ANTHROPIC_API_KEY');
  staged = { root, pluginDir, configDir };
  process.on('exit', () => { try { rmSync(root, { recursive: true, force: true }); } catch {} });
  return staged;
}

async function loadCases() {
  const cases = JSON.parse(readFileSync(join(EVAL_DIR, 'cases.json'), 'utf8'));
  const gold = JSON.parse(readFileSync(join(EVAL_DIR, 'gold.json'), 'utf8'));
  const only = process.env.CG_EVAL_ONLY ? new Set(process.env.CG_EVAL_ONLY.split(',')) : null;
  stage(); // fails here, before any spend, when no credentials are available
  return cases
    .filter(c => !only || only.has(c.id))
    .map(c => {
      const frozen = join(EVAL_DIR, 'cases', c.id, 'frozen');
      if (!existsSync(join(frozen, 'facts.json'))) throw new Error(`no frozen facts for ${c.id}; run freeze/freeze.sh`);
      if (!gold[c.id]) throw new Error(`no gold entry for ${c.id} in gold.json`);
      return { ...c, prompt: taskPrompt(c), frozen, gold: gold[c.id] };
    });
}

function taskPrompt(c) {
  const repo = c.repo
    ? `The catalog is built from the git repository ${c.repo}. The facts already include its CI and git data under "repo".`
    : 'There is no repository for this catalog.';
  return [
    `Use the catalog-grader skill to grade the Portolan catalog at ${c.url}.`,
    'Step 1 is already done. Its output is in ./out: facts.json, docs/, thumbnails/, and the logo.',
    'Do not run collect_facts.py again. Start at Step 2 and use ./out as $OUT.',
    repo,
    'This is not a registry submission.',
    'Write ./out/report.json and ./out/report.md.',
  ].join('\n');
}


// Convert stream-json events to report transcript turns.
function toTranscript(events, prompt) {
  const turns = [{ role: 'user', content: prompt }];
  for (const ev of events) {
    if (ev.type === 'assistant') {
      let thinking = '';
      for (const b of ev.message?.content ?? []) {
        if (b.type === 'thinking') thinking += b.thinking ?? '';
        else if (b.type === 'text' && b.text?.trim()) {
          turns.push({ role: 'assistant', content: b.text, ...(thinking ? { thinking } : {}) }); thinking = '';
        } else if (b.type === 'tool_use') {
          turns.push({ role: 'tool_call', name: b.name, content: JSON.stringify(b.input, null, 2),
                       ...(thinking ? { thinking } : {}) }); thinking = '';
        }
      }
    } else if (ev.type === 'user') {
      for (const b of ev.message?.content ?? []) {
        if (b.type !== 'tool_result') continue;
        const content = typeof b.content === 'string' ? b.content
          : (b.content ?? []).map(x => x.type === 'text' ? x.text : `[${x.type}]`).join('\n');
        turns.push({ role: 'tool_result', content: content.slice(0, 20000) });
      }
    }
  }
  return turns;
}

function regradeCase(input, ctx) {
  const src = resolve(process.env.CG_EVAL_REGRADE_FROM);
  const row = readFileSync(join(src, 'results.jsonl'), 'utf8').split('\n').filter(Boolean)
    .map(l => JSON.parse(l)).find(r => r.prompt_id === input.id && r.rep === ctx.rep);
  if (!row) { const e = new Error(`no row for ${input.id} rep${ctx.rep} in ${src}`); e.failure_class = 'harness'; throw e; }
  const transcript = JSON.parse(readFileSync(join(src, 'traces', `${input.id}_rep${ctx.rep}.json`), 'utf8'));
  const last = transcript.at(-1);
  const reportText = last?.role === 'assistant' && last.content.startsWith('```json\n')
    ? last.content.slice(8, -4) : null;
  const facts = JSON.parse(readFileSync(join(input.frozen, 'facts.json'), 'utf8'));
  const docs = readDocs(input.frozen);
  return { output: reportText ?? '', reportText, transcript, docs, facts,
           model: row.model, usage: row.usage, stop_reason: row.stop_reason,
           cc_cost_usd: row.cc_cost_usd, num_turns: row.num_turns, tool_calls: row.tool_calls,
           latency_s: row.latency_s };
}

async function runCase(input, ctx) {
  if (process.env.CG_EVAL_REGRADE_FROM) return regradeCase(input, ctx);
  const { pluginDir, configDir } = stage();
  const work = mkdtempSync(join(tmpdir(), `cg-eval-${input.id}-`));
  try {
    cpSync(input.frozen, join(work, 'out'), { recursive: true,
      filter: src => !/collect\.log$/.test(src) });
    const model = ctx.model ?? 'claude-opus-5-5';
    const args = ['-p', input.prompt, '--model', model, '--effort', process.env.CG_EVAL_EFFORT ?? 'high',
      '--plugin-dir', pluginDir, '--output-format', 'stream-json', '--verbose',
      '--no-session-persistence', '--permission-mode', 'dontAsk', '--strict-mcp-config',
      '--allowedTools', AGENT_TOOLS.join(',')];
    const res = await spawnJson('claude', args, { cwd: work, env: claudeEnv(configDir) }, (ctx.timeoutS || 1800) * 1000);
    const events = res.out.split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
    const result = events.findLast(e => e.type === 'result');
    if (!result) {
      const e = new Error(`claude exited ${res.code} with no result event: ${res.err.slice(-500)}`);
      e.failure_class = 'harness'; throw e;
    }
    if (result.is_error && /rate.?limit|overloaded|529|429/i.test(String(result.result ?? ''))) {
      const e = new Error(`claude: ${String(result.result).slice(0, 300)}`); e.status = 429; throw e;
    }
    if (!['success', 'error_max_turns'].includes(result.subtype)) {
      const e = new Error(`claude result ${result.subtype}: ${String(result.result ?? '').slice(0, 300)}`);
      e.failure_class = 'harness'; throw e;
    }
    const served = events.filter(e => e.type === 'assistant').map(e => e.message?.model).filter(Boolean);
    const counts = served.reduce((m, x) => (m[x] = (m[x] ?? 0) + 1, m), {});
    const servedModel = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
    const transcript = toTranscript(events, input.prompt);
    const reportPath = join(work, 'out', 'report.json');
    const reportText = existsSync(reportPath) ? readFileSync(reportPath, 'utf8') : null;
    const reportMd = existsSync(join(work, 'out', 'report.md')) ? readFileSync(join(work, 'out', 'report.md'), 'utf8') : null;
    if (reportText) transcript.push({ role: 'assistant', content: '```json\n' + reportText + '\n```' });
    return {
      output: reportText ?? '',
      reportText, reportMd, transcript,
      docs: readDocs(join(work, 'out')),
      facts: JSON.parse(readFileSync(join(work, 'out', 'facts.json'), 'utf8')),
      model: servedModel, usage: result.usage,
      stop_reason: result.subtype === 'success' ? 'end_turn' : result.subtype,
      cc_cost_usd: result.total_cost_usd, num_turns: result.num_turns,
      tool_calls: transcript.filter(t => t.role === 'tool_call').length,
    };
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
}


function gradeCase(input, run, ref, ctx) {
  return gradeReport(input, run, { env: claudeEnv(stage().configDir), judgeModel: JUDGE_MODEL });
}

function perfFrom(run) {
  // Preserve original latency when regrading.
  return { ...(run.latency_s != null ? { latency_s: run.latency_s } : {}),
           cc_cost_usd: run.cc_cost_usd, num_turns: run.num_turns, tool_calls: run.tool_calls,
           report_grade: run.reportText ? (() => { try { return JSON.parse(run.reportText).grade; } catch { return null; } })() : null };
}

// Harness

function parseArgs(argv) {
  const a = { flow: '.claude/hillclimb/flow', variant: 'baseline',
              model: undefined, reps: 1, concurrency: 4, timeoutS: 1800,
              approveHarness: false };
  // Missing --model values would disable the served-model check.
  const val = (i) => { if (argv[i] === undefined) { eprint(`missing value for ${argv[i - 1]}`); usage(); process.exit(2); } return argv[i]; };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--flow') a.flow = val(++i);
    else if (k === '--variant') a.variant = val(++i);
    else if (k === '--model') a.model = val(++i);
    else if (k === '--reps') a.reps = +val(++i);
    else if (k === '--concurrency') a.concurrency = +val(++i);
    else if (k === '--timeout-s') a.timeoutS = +val(++i);
    else if (k === '--approve-harness') a.approveHarness = true;
    else if (k === '-h' || k === '--help') { usage(); process.exit(0); }
    else { eprint(`unknown argument: ${k}`); usage(); process.exit(2); }
  }
  if (!/^(baseline|v[1-9]\d*)$/.test(a.variant)) {
    // The report discovers only baseline and v<N> directories.
    eprint(`--variant must be 'baseline' or 'v<N>', got '${a.variant}'`);
    usage(); process.exit(2);
  }
  if (!Number.isFinite(a.timeoutS) || a.timeoutS < 0
      || a.timeoutS * 1000 > 2147483647 // setTimeout clamps >2^31-1 ms to 1 ms - the ceiling would fire instantly
      || !Number.isInteger(a.reps) || a.reps < 1
      || !Number.isInteger(a.concurrency) || a.concurrency < 1) { usage(); process.exit(2); }
  return a;
}
function usage() {
  eprint('usage: node run-eval.mjs --flow DIR --variant ID [--model ID] [--reps N] [--concurrency N] [--timeout-s N (0 = no ceiling)] [--approve-harness]');
}

// Detect harness changes before unattended runs. The agent can edit this
// record, so permissions must constrain the exact runner command. Installed
// dependencies beyond lockfiles are outside the digest.
function checkHarness(statePath, st, approve) {
  const self = fileURLToPath(import.meta.url);
  const listed = Array.isArray(st.harness_paths) ? st.harness_paths.map(String) : [];
  const lockfiles = [...new Set([dirname(self), process.cwd()].flatMap(d =>
    ['package-lock.json', 'bun.lock', 'bun.lockb', 'yarn.lock', 'pnpm-lock.yaml'].map(f => join(d, f))))]
    .filter(f => existsSync(f));
  const paths = [...new Set([self, ...lockfiles, ...listed.map(p => resolve(p))])].sort();
  const h = createHash('sha256');
  const hashed = [];
  for (const p of paths) {
    let buf;
    try { buf = readFileSync(p); }
    catch (e) {
      if (p === self) throw e;
      eprint(`warning: harness path '${relative(process.cwd(), p)}' not readable (${e?.code || 'error'}) - skipped`);
      continue;
    }
    h.update(relative(process.cwd(), p)).update('\0').update(buf).update('\0');
    hashed.push(relative(process.cwd(), p));
  }
  const sha = h.digest('hex');
  if (st.harness_sha === sha) return;
  if (!lockfiles.length) eprint('note: no lockfile beside the runner or in the current directory - dependency changes are outside the harness sha');
  if (approve) {
    st.harness_sha = sha;
    writeFileNoFollow(statePath, JSON.stringify(st, null, 2) + '\n');
    eprint(`harness approved: sha256 ${sha.slice(0, 12)} over ${hashed.length} file(s) recorded in ${statePath}`);
    return;
  }
  if (st.harness_sha == null) {
    eprint(`no approved harness sha in ${statePath} (computed ${sha.slice(0, 12)} over: ${hashed.join(', ')}).`);
    eprint('Review the harness, then run once with --approve-harness to record it.');
  } else {
    eprint(`harness changed since last approved run (files: ${hashed.join(', ')}); `
      + `approved ${String(st.harness_sha).slice(0, 12)}, now ${sha.slice(0, 12)}.`);
    eprint('Re-run with --approve-harness after reviewing the diff.');
  }
  process.exit(2);
}

async function withBackoff(fn, retry, deadline = Infinity, tries = 5) {
  for (let attempt = 0; ; attempt++) {
    // Enforce the deadline before both model and judge attempts.
    if (Date.now() >= deadline) {
      const e = new Error('wall-clock ceiling exceeded before attempt');
      e.failure_class = 'timeout';
      throw e;
    }
    try { return await fn(); } catch (e) {
      const status = e?.status ?? e?.response?.status;
      const transient = status === 429 || status === 529 || (status >= 500 && status < 600)
        || /overloaded|rate.?limit/i.test(String(e?.message ?? ''));
      if (!transient || attempt >= tries - 1) throw e;
      const delay = Math.min(60_000, 1000 * 2 ** attempt) * (0.5 + Math.random());
      if (Date.now() + delay >= deadline) throw e;
      retry.count++;
      await new Promise(r => setTimeout(r, delay));
    }
  }
}

// A wall-clock limit handles streams that keep sending keepalives.
// The underlying call may continue after the slot is freed.
function withTimeout(promise, seconds, label) {
  if (!(seconds > 0)) return promise;
  let timer;
  const ceiling = new Promise((_, reject) => {
    timer = setTimeout(() => {
      const e = new Error(`${label}: exceeded ${seconds}s wall-clock ceiling`);
      e.failure_class = 'timeout';
      reject(e);
    }, seconds * 1000);
  });
  return Promise.race([promise, ceiling]).finally(() => clearTimeout(timer));
}

// Use one path-safe ID for rows, traces, and references; hash changed IDs
// to avoid collisions and keep the original in meta.original_id.
function pathSafeId(id) {
  const raw = String(id);
  const cleaned = raw.replace(/[^\w.-]/g, '_');
  // Preserve already-safe IDs, including this function's own output.
  if (cleaned === raw && raw.length <= 129) return raw;
  return `${cleaned.slice(0, 120)}-${createHash('sha256').update(raw).digest('hex').slice(0, 8)}`;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  // Trailing separators make lstat follow links. Backslash separates paths
  // only on Windows.
  args.flow = args.flow.replace(WIN ? /(.)[\\/]+$/ : /(.)\/+$/, '$1');
  const flowSegments = args.flow.split(WIN ? /[\\/]/ : '/');
  // Dot segments can make link checks and join() resolve different paths.
  if (flowSegments.some(seg => seg === '.' || seg === '..')) {
    eprint(`refusing to run: --flow must not contain '.' or '..' segments, got '${args.flow}'`);
    process.exit(2);
  }
  const vdir = join(args.flow, args.variant);
  // Check output paths before paying for model calls.
  for (const p of [args.flow, join(args.flow, 'baseline'), vdir, join(vdir, 'traces'),
                   join(vdir, 'results.jsonl'), join(vdir, 'errors.jsonl'),
                   join(vdir, 'progress.txt'), join(args.flow, 'baseline', 'ref'), join(args.flow, '_state.json')])
    if (isSymlink(p)) { eprint(`refusing to run: ${p} is a symlink (the flow dir must hold regular files)`); process.exit(2); }
  // Reject relative ancestor links before capturing the containment root.
  // Absolute paths may have legitimate ancestor links, such as macOS /tmp.
  if (!isAbsolute(args.flow)) {
    let walk = '';
    for (const part of flowSegments.filter(Boolean).slice(0, -1)) {
      walk = walk ? join(walk, part) : part;
      if (isSymlink(walk)) { eprint(`refusing to run: ${walk} is a symlink (ancestor of --flow)`); process.exit(2); }
    }
  }
  mkdirSync(args.flow, { recursive: true });
  flowRealRoot = realpathSync(args.flow);
  mkdirNoFollow(join(vdir, 'traces'));
  // The orchestrator owns state; only --approve-harness writes it.
  const statePath = join(args.flow, '_state.json');
  let st = {};
  // Suppress parse errors that could expose file contents.
  const stateText = readIfPresent(statePath);
  if (stateText != null) {
    try { st = JSON.parse(stateText) || {}; }
    catch { eprint(`${statePath} exists but is not valid JSON - fix it before spending a pass`); process.exit(2); }
  }
  checkHarness(statePath, st, args.approveHarness);
  const ctx = { ...args, state: st };

  const resultsPath = join(vdir, 'results.jsonl');
  const done = new Set();
  for (const ln of (readIfPresent(resultsPath) ?? '').split('\n')) {
    if (!ln.trim()) continue;
    try { const r = JSON.parse(ln); done.add(`${r.prompt_id}\0${r.rep}`); } catch {}
  }

  const cases = await loadCases();
  // Reject ID collisions before model calls, including on case-insensitive
  // filesystems. Split IDs must use the same sanitized form as result rows.
  const seen = new Map();
  for (const c of cases) {
    const k = pathSafeId(c.id).toLowerCase();
    if (seen.has(k)) {
      eprint(`duplicate case id after sanitization: '${c.id}' collides with '${seen.get(k)}'`);
      process.exit(2);
    }
    seen.set(k, c.id);
  }
  const safeIds = new Set(cases.map(c => pathSafeId(c.id)));
  for (const k of ['train_ids', 'val_ids', 'test_ids'])
    if (st[k] != null && !Array.isArray(st[k])) { eprint(`_state.json ${k} must be a list of ids`); process.exit(2); }
  for (const sid of [...(st.train_ids ?? []), ...(st.val_ids ?? []), ...(st.test_ids ?? [])]) {
    const s = String(sid);
    if (safeIds.has(s)) continue;
    if (s !== pathSafeId(s)) {
      eprint(`_state.json split id '${s}' is not a path-safe id - record split ids exactly as they appear in results.jsonl's prompt_id`);
      process.exit(2);
    }
    // Missing IDs are valid for subset runs.
    eprint(`note: split id '${s}' matches no loaded case (expected for a trimmed subset run)`);
  }
  const refDir = join(args.flow, 'baseline', 'ref');
  const tasks = [];
  for (const c of cases) for (let rep = 0; rep < args.reps; rep++) {
    if (done.has(`${pathSafeId(c.id)}\0${rep}`)) continue;
    tasks.push({ c, rep });
  }
  eprint(`[${args.variant}] ${tasks.length} of ${cases.length * args.reps} (id,rep) to run`);

  let i = 0, ok = 0, fail = 0;
  const errorsPath = join(vdir, 'errors.jsonl');
  // Isolate incomplete final rows so a new append cannot merge with them.
  for (const p of [resultsPath, errorsPath]) {
    const tail = readIfPresent(p);
    if (tail && !tail.endsWith('\n')) appendFileNoFollow(p, '\n');
  }
  async function worker() {
    while (i < tasks.length) {
      const { c, rep } = tasks[i++];
      const safeId = pathSafeId(c.id);
      const t0 = Date.now();
      let lastRun = null; // Keep billed usage on failure.
      let rowWritten = false;
      const deadline = args.timeoutS > 0 ? t0 + args.timeoutS * 1000 : Infinity;
      const appRetry = { count: 0 }, judgeRetry = { count: 0 };
      try {
        const { run, g, latency_s } = await withTimeout((async () => {
          let tAttempt = t0;
          const run = await withBackoff(() => { tAttempt = Date.now(); return runCase(c, { ...ctx, rep }); },
            appRetry, deadline);
          lastRun = run;
          // Measure only the final app attempt, excluding retries and judging.
          const latency_s = (Date.now() - tAttempt) / 1000;
          // Allow exact model matches or dated snapshots of the requested alias.
          if (ctx.model && run.model && run.model !== ctx.model) {
            const base = ctx.model.replace(/-latest$|-0$/, '');
            const rest = String(run.model).startsWith(base)
              ? String(run.model).slice(base.length) : null;
            if (!(rest != null && /^[-@](\d{8}|\d{4}-\d{2}-\d{2})$/.test(rest))) {
              const e = new Error(`served model ${run.model} != requested ${ctx.model}`);
              e.failure_class = 'serving_substitution';
              throw e;
            }
          }
          let ref = null;
          if (args.variant !== 'baseline') {
            const p = join(refDir, safeId);
            for (const ext of REF_EXTS) {
              try { ref = readFileNoFollow(p + ext); break; }
              catch (e) { if (e?.code !== 'ENOENT') throw e; }
            }
          }
          const g = await withBackoff(() => gradeCase(c, run, ref, ctx), judgeRetry, deadline);
          return { run, g, latency_s };
        })(), args.timeoutS, `${c.id} rep${rep}`);
        const row = {
          prompt_id: safeId, rep, prompt: c.prompt ?? c.input ?? c.id,
          tags: c.tags, attachments: c.attachments,
          meta: safeId !== String(c.id) || appRetry.count || judgeRetry.count
            ? { ...(c.meta ?? {}),
                ...(safeId !== String(c.id) ? { original_id: String(c.id) } : {}),
                ...(appRetry.count ? { retries: appRetry.count } : {}),
                ...(judgeRetry.count ? { judge_retries: judgeRetry.count } : {}) }
            : c.meta,
          model: run.model, usage: run.usage, stop_reason: run.stop_reason,
          // The report excludes truncated rows from means by status.
          status: run.status ?? (run.stop_reason === 'max_tokens' ? 'truncated' : 'ok'),
          judge_model: g.judge_model ?? run.judge_model,
          judge_usage: g.judge_usage ?? run.judge_usage,
          latency_s, ...perfFrom(run),
          grade: g.grade, explanation: g.explanation,
        };
        appendFileNoFollow(resultsPath, JSON.stringify(row) + '\n');
        rowWritten = true; // Later write failures must not double-count usage.
        if (run.transcript)
          writeFileNoFollow(join(vdir, 'traces', `${safeId}_rep${rep}.json`),
            JSON.stringify(run.transcript, null, 2));
        // Freeze baseline references once for pairwise scoring.
        if (args.variant === 'baseline' && run.output != null
            && !REF_EXTS.some(ext => lexists(join(refDir, safeId) + ext))) {
          mkdirNoFollow(refDir);
          writeFileNoFollow(join(refDir, safeId),
            typeof run.output === 'string' ? run.output : JSON.stringify(run.output));
        }
        ok++;
      } catch (e) {
        fail++;
        if (rowWritten) {
          eprint(`  [${args.variant}] ${c.id} rep${rep} scored, but a post-row write failed: ${e?.message || e}`);
          continue;
        }
        // Keep failures out of results.jsonl so resume retries them.
        appendFileNoFollow(errorsPath, JSON.stringify({
          prompt_id: safeId, rep,
          ...(safeId !== String(c.id) ? { original_id: String(c.id) } : {}),
          failure_class: e?.failure_class ?? 'error',
          error: String(e?.message || e),
          retries: appRetry.count, judge_retries: judgeRetry.count,
          model: lastRun?.model, usage: lastRun?.usage,
          judge_model: e?.judge_model ?? lastRun?.judge_model,
          judge_usage: e?.judge_usage ?? lastRun?.judge_usage,
          latency_s: (Date.now() - t0) / 1000,
        }) + '\n');
        eprint(`  [${args.variant}] ${c.id} rep${rep} FAILED: ${e?.message || e}`);
      }
    }
  }
  const t0 = Date.now();
  const progress = () => {
    const done = ok + fail, total = tasks.length;
    const el = (Date.now() - t0) / 1000;
    const eta = done ? Math.round((el / done) * (total - done)) : null;
    const line = `[${args.variant}] ${done}/${total} done (${ok} ok, ${fail} failed), `
      + `${Math.round(el)}s elapsed` + (eta != null ? `, ~${eta}s left` : '');
    eprint(line);
    try { writeFileNoFollow(join(vdir, 'progress.txt'), line + '\n'); } catch {}
  };
  const tick = setInterval(progress, 30_000);
  workersStarted = true;
  await Promise.all(Array.from({ length: Math.max(1, args.concurrency) }, worker));
  clearInterval(tick); progress();
  eprint(`[${args.variant}] done - ${ok} ok, ${fail} failed -> ${resultsPath}`);
  process.exit(fail ? 1 : 0);
}

let workersStarted = false;
main().catch(e => {
  const m = String(e?.message || e);
  if (workersStarted) { eprint('stopped mid-run (rows already written are kept; re-run to resume): ' + m); process.exit(1); }
  eprint(m.startsWith('refusing to ') ? m : 'refusing to run: ' + m);
  process.exit(2);
});
