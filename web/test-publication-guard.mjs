import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
for (const destination of [resolve(here, '../site'), resolve(here, '../site/guard-test')]) {
  const result = spawnSync(process.execPath, [
    resolve(here, 'render.mjs'),
    resolve(here, 'not-a-real-brief.html'),
    resolve(here, '../docs/s3c'),
    destination,
  ], { encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /publication blocked: warehouse provenance/);
}
console.log('PASS: production site and child writes refused before reading a brief');
