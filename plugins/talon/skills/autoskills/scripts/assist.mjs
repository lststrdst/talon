#!/usr/bin/env node
import {
  existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync,
  readdirSync, renameSync, rmSync, statSync, writeFileSync,
} from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const VERSION = '0.4.1';
const REGISTRY_URL = 'https://raw.githubusercontent.com/midudev/autoskills/b4489cbdc36ba8c9de8f4dd844bab0b6b559579f/packages/autoskills/skills-registry';
const MAX_FILES = 80;
const MAX_FILE_BYTES = 2 * 1024 * 1024;
const MAX_BUNDLE_BYTES = 8 * 1024 * 1024;
const MAX_INSTRUCTION_BYTES = 24 * 1024;
const TIMEOUT_MS = 20_000;

function parseArgs() {
  const [command, ...args] = process.argv.slice(2);
  const allowed = command === 'suggest'
    ? ['project', 'query', 'package']
    : ['skill', 'package', 'cache'];
  if (!['suggest', 'prepare'].includes(command)) {
    throw new Error('Use suggest --project PATH --query "keywords" or prepare --skill SLUG.');
  }
  const options = {};
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index].replace(/^--/, '');
    const value = args[index + 1];
    if (!args[index].startsWith('--') || !allowed.includes(key) || value === undefined || key in options) {
      throw new Error(`Invalid option ${args[index]}.`);
    }
    options[key] = value;
  }
  if (command === 'suggest' && !options.project) throw new Error('--project is required.');
  if (command === 'prepare' && !options.skill) throw new Error('--skill is required.');
  return { command, options };
}

function securityStatus(entry) {
  return entry.securityCheck?.status ?? 'unknown';
}

function suggest(options, lib, registry) {
  const project = resolve(options.project);
  if (!statSync(project).isDirectory()) throw new Error('Project must be a directory.');
  const stack = lib.detectTechnologies(project);
  const stackSkills = new Set(lib.collectSkills(stack).map(skill => skill.skill));
  const words = [...new Set((options.query ?? '').toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [])];
  if (words.length > 8 || (options.query?.length ?? 0) > 200) {
    throw new Error('Use a short task query, ideally 2–4 keywords.');
  }
  const drawers = ['.agents', '.codex', ...Object.keys(lib.AGENT_FOLDER_MAP)];
  const candidates = Object.entries(registry.skills).map(([name, entry]) => {
    const tokens = name.toLowerCase().split(/[-_]/);
    const queryScore = words.reduce((score, word) => score
      + (tokens.includes(word) ? 10 : name.toLowerCase().includes(word) ? 6 : 0)
      + (entry.source.toLowerCase().includes(word) ? 1 : 0), 0);
    const score = queryScore > 0 ? queryScore + (stackSkills.has(entry.skillPath) ? 5 : 0) : 0;
    return { name, entry, score };
  }).filter(candidate => candidate.score > 0)
    .sort((left, right) => right.score - left.score || left.name.localeCompare(right.name, 'en'))
    .slice(0, 3)
    .map(({ name, entry }) => ({
      name,
      source: entry.source,
      security: securityStatus(entry),
      bundleHash: entry.bundleHash,
      fileCount: entry.files.length,
      installed: [project, homedir()].some(root => drawers.some(drawer => {
        try { lstatSync(join(root, drawer, 'skills', name)); return true; }
        catch (error) { if (error.code === 'ENOENT') return false; throw error; }
      })),
    }));
  return { project, stack: stack.detected.map(tech => tech.id).sort(), candidates };
}

function validateEntry(name, entry) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(name) || !entry) {
    throw new Error('Unknown exact registry skill.');
  }
  if (securityStatus(entry) !== 'ok' || entry.review?.status === 'flagged') {
    throw new Error('Preparation requires an explicit securityCheck status of ok.');
  }
  if (!Array.isArray(entry.files) || entry.files.length < 1 || entry.files.length > MAX_FILES) {
    throw new Error(`Preparation requires 1–${MAX_FILES} files; review larger bundles separately.`);
  }
  if (entry.skillPath !== `${entry.source}/${name}` || !/^[a-f0-9]{64}$/.test(entry.bundleHash)) {
    throw new Error('Invalid registry identity.');
  }
  const seen = new Set();
  for (const file of entry.files) {
    if (typeof file !== 'string' || /[\\\x00-\x1f:]/.test(file)
      || file.split('/').some(part => !part || part === '.' || part === '..')
      || seen.has(file.toLowerCase()) || !/^[a-f0-9]{64}$/.test(entry.sha256?.[file])) {
      throw new Error('Invalid or duplicate registry filename or hash.');
    }
    seen.add(file.toLowerCase());
  }
  if (!entry.files.includes('SKILL.md')) throw new Error('Registry bundle has no SKILL.md.');
  const hash = createHash('sha256').update(entry.files
    .map(file => `${file}:${entry.sha256[file]}`).sort().join('\n')).digest('hex');
  if (hash !== entry.bundleHash) throw new Error('Registry bundle hash is inconsistent.');
}

function verifyBundle(directory, name, entry, installer) {
  const files = [];
  let bytes = 0;
  function walk(current, prefix = '') {
    if (lstatSync(current).isSymbolicLink()) throw new Error('Cached bundle contains a symlink.');
    for (const item of readdirSync(current, { withFileTypes: true })) {
      const relative = prefix + item.name;
      const path = join(current, item.name);
      if (item.isDirectory()) walk(path, `${relative}/`);
      else {
        if (!item.isFile()) throw new Error('Cached bundle contains a nonregular file.');
        const size = statSync(path).size;
        if (relative === 'SKILL.md' && size > MAX_INSTRUCTION_BYTES) {
          throw new Error('SKILL.md exceeds 24 KiB; recommend this skill for separate review.');
        }
        bytes += size;
        if (size > MAX_FILE_BYTES || bytes > MAX_BUNDLE_BYTES) throw new Error('Bundle exceeds byte budget.');
        files.push(relative);
      }
    }
  }
  walk(directory);
  if (files.sort().join('\n') !== [...entry.files].sort().join('\n')) {
    throw new Error('Cached bundle file list differs from the registry.');
  }
  // The upstream verifier expects <registry>/<skill>; both prepared layouts follow it.
  const verdict = installer.verifyRegistryEntry(name, entry, resolve(directory, '..'));
  if (!verdict.ok) throw new Error(`Bundle verification failed: ${verdict.reason}`);
}

async function acquireLock(directory, key, signal) {
  const prefix = `${key}--`;
  const owner = `${prefix}${process.pid}-${randomUUID()}.json`;
  const marker = join(directory, owner);
  const pending = `${marker}.tmp`;
  const release = () => {
    rmSync(marker, { force: true });
    rmSync(pending, { force: true });
  };
  function peers() {
    const result = [];
    for (const file of readdirSync(directory)) {
      if (!file.startsWith(prefix) || !file.endsWith('.json')) continue;
      const pid = Number(file.slice(prefix.length).split('-')[0]);
      if (!Number.isSafeInteger(pid) || pid < 1) throw new Error('Invalid cache lock owner.');
      const path = join(directory, file);
      try { process.kill(pid, 0); }
      catch (error) {
        if (error.code !== 'ESRCH' && error.code !== 'EPERM') throw error;
        if (error.code === 'ESRCH') { rmSync(path, { force: true }); continue; }
      }
      let ticket = 0;
      try {
        const value = JSON.parse(readFileSync(path, 'utf8')).ticket;
        if (Number.isSafeInteger(value) && value > 0) ticket = value;
      } catch (error) {
        if (error.code === 'ENOENT') continue;
        if (!(error instanceof SyntaxError)) throw error;
      }
      result.push({ file, ticket });
    }
    return result;
  }
  try {
    // Ticket zero announces selection. Unique markers make dead-owner cleanup race-safe.
    writeFileSync(marker, JSON.stringify({ ticket: 0 }), { flag: 'wx', mode: 0o600 });
    const ticket = Math.max(0, ...peers().map(peer => peer.ticket)) + 1;
    writeFileSync(pending, JSON.stringify({ ticket }), { flag: 'wx', mode: 0o600 });
    renameSync(pending, marker);
    const deadline = Date.now() + TIMEOUT_MS + 5_000;
    while (peers().some(peer => peer.file !== owner && (peer.ticket === 0
      || peer.ticket < ticket || (peer.ticket === ticket && peer.file < owner)))) {
      signal.throwIfAborted();
      if (Date.now() > deadline) throw new Error(`Preparation lock timed out for ${key}; retry with a fresh --cache if its owner is stalled.`);
      await delay(100, undefined, { signal });
    }
    signal.throwIfAborted();
    return release;
  } catch (error) {
    release();
    throw error;
  }
}

async function prepare(options, installer, registry) {
  const name = options.skill;
  const entry = Object.hasOwn(registry.skills, name) ? registry.skills[name] : null;
  validateEntry(name, entry);
  const cache = resolve(options.cache ?? join(homedir(), '.cache', 'talon', 'task-skills'));
  const parent = join(cache, entry.bundleHash);
  const destination = join(parent, name);
  const locks = join(cache, '.locks');
  mkdirSync(locks, { recursive: true, mode: 0o700 });
  let releaseLock;
  let temporary;
  let cached = false;
  const controller = new AbortController();
  const abort = () => controller.abort(new Error('Preparation interrupted.'));
  process.once('SIGINT', abort);
  process.once('SIGTERM', abort);
  try {
    releaseLock = await acquireLock(locks, `${entry.bundleHash}-${name}`, controller.signal);
    if (existsSync(destination)) {
      verifyBundle(destination, name, entry, installer);
      cached = true;
    } else {
      temporary = mkdtempSync(join(cache, '.prepare-'));
      const project = join(temporary, 'project');
      mkdirSync(project, { mode: 0o700 });
      process.env.AUTOSKILLS_CACHE_DIR = join(temporary, 'downloads');
      const allowedUrls = new Set(entry.files.map(file => `${REGISTRY_URL}/${[name, ...file.split('/')]
        .map(encodeURIComponent).join('/')}`));
      let downloadedBytes = 0;
      const timer = setTimeout(() => controller.abort(new Error('Download timed out after 20 seconds.')), TIMEOUT_MS);
      try {
        const result = await installer.installSkill(entry.skillPath, ['universal'], {
          projectDir: project,
          registryDir: join(temporary, 'empty-registry'),
          registryBaseUrl: REGISTRY_URL,
          // Ignore upstream headers so inherited GitHub credentials never reach this request.
          fetchImpl: async url => {
            if (!allowedUrls.has(String(url))) throw new Error('Unexpected registry URL.');
            const response = await fetch(url, {
              signal: controller.signal, redirect: 'error', credentials: 'omit',
              headers: { 'User-Agent': 'talon-autoskills' },
            });
            if (!response.ok) return response;
            let fileBytes = 0;
            const chunks = [];
            for await (const chunk of response.body) {
              fileBytes += chunk.length;
              downloadedBytes += chunk.length;
              if (fileBytes > MAX_FILE_BYTES || downloadedBytes > MAX_BUNDLE_BYTES) {
                controller.abort(new Error('Download exceeds byte budget.'));
                throw new Error('Download exceeds byte budget.');
              }
              chunks.push(chunk);
            }
            return new Response(Buffer.concat(chunks));
          },
        });
        if (!result.success) throw new Error(result.stderr || result.output);
      } finally {
        clearTimeout(timer);
        controller.abort();
      }
      const bundle = join(project, '.agents', 'skills', name);
      verifyBundle(bundle, name, entry, installer);
      mkdirSync(parent, { recursive: true, mode: 0o700 });
      renameSync(bundle, destination);
    }
    const skillPath = join(destination, 'SKILL.md');
    const instructions = readFileSync(skillPath, 'utf8');
    const header = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(instructions)?.[1] ?? '';
    const declaredName = /^name:\s*["']?([A-Za-z0-9_-]+)["']?\s*$/m.exec(header)?.[1] ?? null;
    return {
      name, declaredName, source: entry.source, security: 'ok', bundleHash: entry.bundleHash,
      fileCount: entry.files.length, cached, skillPath,
      instructionBytes: Buffer.byteLength(instructions),
    };
  } finally {
    controller.abort();
    process.removeListener('SIGINT', abort);
    process.removeListener('SIGTERM', abort);
    if (temporary) rmSync(temporary, { recursive: true, force: true });
    releaseLock?.();
  }
}

try {
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (major < 22 || (major === 22 && minor < 6)) throw new Error('Node.js 22.6+ is required.');
  const { command, options } = parseArgs();
  const packageDirectory = resolve(options.package ?? join(homedir(), '.local', 'share', 'talon', 'autoskills', VERSION, 'package'));
  const packageInfo = JSON.parse(readFileSync(join(packageDirectory, 'package.json'), 'utf8'));
  if (packageInfo.name !== 'autoskills' || packageInfo.version !== VERSION) {
    throw new Error(`Expected installed autoskills@${VERSION}.`);
  }
  const lib = await import(pathToFileURL(join(packageDirectory, 'dist', 'lib.js')));
  const installer = await import(pathToFileURL(join(packageDirectory, 'dist', 'installer.js')));
  const registry = installer.loadRegistry();
  if (!registry?.skills) throw new Error('Installed registry is missing.');
  const result = command === 'suggest'
    ? suggest(options, lib, registry)
    : await prepare(options, installer, registry);
  console.log(JSON.stringify(result));
} catch (error) {
  console.log(JSON.stringify({ error: error.message }));
  process.exitCode = 1;
}
