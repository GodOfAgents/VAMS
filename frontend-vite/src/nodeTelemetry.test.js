import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import {
  NODE_TELEMETRY_MESSAGE,
  resolveBrowserNodeTelemetry,
} from './nodeTelemetry.js';

const sourceDirectory = dirname(fileURLToPath(import.meta.url));

function assertUnavailable(state) {
  assert.deepEqual(state, {
    status: 'unavailable',
    requested: false,
    authoritative: false,
    simulated: false,
    nodes: [],
    message: NODE_TELEMETRY_MESSAGE,
  });
}

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    if (!['.js', '.jsx'].includes(extname(entry.name))) return [];
    if (entry.name.endsWith('.test.js')) return [];
    return [path];
  });
}

test('live UI modes remain unavailable and never request node telemetry', () => {
  for (const runtimeMode of ['staging', 'testnet', 'production']) {
    assertUnavailable(resolveBrowserNodeTelemetry({ runtimeMode }));
  }
});

test('gateway failures and malformed responses cannot become telemetry', () => {
  const outcomes = [
    { status: 401 },
    new Error('network unavailable'),
    { status: 200, body: { nodes: 'malformed' } },
  ];

  for (const outcome of outcomes) {
    assertUnavailable(resolveBrowserNodeTelemetry(outcome));
  }
});

test('local and demo labels do not activate a simulated fallback', () => {
  for (const runtimeMode of ['local', 'demo', undefined, '', 'TESTNET']) {
    assertUnavailable(resolveBrowserNodeTelemetry({ runtimeMode }));
  }
});

test('frontend source neither calls protected nodes nor references browser signing secrets', () => {
  const appSource = readFileSync(join(sourceDirectory, 'App.jsx'), 'utf8');
  assert.doesNotMatch(appSource, /fetch\s*\(\s*[`'"](?:[^`'"]*)\/nodes/);
  assert.doesNotMatch(appSource, /Node-(?:Mumbai|Frankfurt|Singapore)-/);

  const secretPatterns = [
    /VITE_[A-Z0-9_]*(?:SECRET|PRIVATE|PASSWORD|TOKEN|SIGNING|SIGNATURE|ADMIN|DID_KEY)/,
    /GATEWAY_ADMIN_PASSWORD/,
    /M2_(?:PRIVATE|SIGNING|SECRET|TOKEN|ADMIN)/,
    /BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY/,
  ];

  for (const path of sourceFiles(sourceDirectory)) {
    const source = readFileSync(path, 'utf8');
    for (const pattern of secretPatterns) {
      assert.doesNotMatch(source, pattern, `${path} references ${pattern}`);
    }
  }
});
