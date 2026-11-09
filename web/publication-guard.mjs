import { existsSync, realpathSync } from 'node:fs';
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

function canonical(path) {
  let current = resolve(path);
  const missing = [];
  while (!existsSync(current)) {
    const parent = dirname(current);
    if (parent === current) throw Error('Cannot resolve publication destination');
    missing.unshift(current.slice(parent.length + (parent.endsWith(sep) ? 0 : 1)));
    current = parent;
  }
  return resolve(realpathSync(current), ...missing);
}

export function rejectUnverifiedSiteOutput(dest) {
  const here = dirname(fileURLToPath(import.meta.url));
  const site = canonical(resolve(here, '../site'));
  const rel = relative(site, canonical(dest));
  if (rel === '' || (rel !== '..' && !rel.startsWith('..' + sep) && !isAbsolute(rel))) {
    throw Error('publication blocked: warehouse provenance cannot yet be verified');
  }
}
