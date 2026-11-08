import { lstatSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const bundleRoot = fileURLToPath(new URL('../dist/', import.meta.url))

// This is the reviewed M2 frontend disposition pattern set. Changes require a
// separate security review; CI and local verification intentionally share it.
const forbiddenPatterns = Object.freeze([
  '/nodes',
  'GATEWAY_ADMIN_PASSWORD',
  'M2_PRIVATE',
  'M2_SIGNING',
  'BEGIN PRIVATE KEY',
  'VITE_VAMS_ADMIN',
  'VITE_M2',
])

function collectFiles(directory) {
  const entries = readdirSync(directory, { withFileTypes: true })
    .sort((left, right) => (left.name < right.name ? -1 : left.name > right.name ? 1 : 0))
  const files = []

  for (const entry of entries) {
    const path = join(directory, entry.name)
    const metadata = lstatSync(path)
    if (metadata.isSymbolicLink()) {
      throw new Error(`bundle scan rejected symbolic link: ${relative(bundleRoot, path)}`)
    }
    if (metadata.isDirectory()) {
      files.push(...collectFiles(path))
    } else if (metadata.isFile()) {
      files.push(path)
    } else {
      throw new Error(`bundle scan rejected non-regular entry: ${relative(bundleRoot, path)}`)
    }
  }
  return files
}

const rootMetadata = lstatSync(bundleRoot)
if (!rootMetadata.isDirectory()) {
  throw new Error('production bundle scan requires a dist directory')
}

const bundleFiles = collectFiles(bundleRoot)
if (bundleFiles.length === 0) {
  throw new Error('production bundle scan requires at least one regular file')
}

const matches = []
for (const path of bundleFiles) {
  const contents = readFileSync(path, 'utf8')
  for (const pattern of forbiddenPatterns) {
    if (contents.includes(pattern)) {
      matches.push({ pattern, path: relative(dirname(bundleRoot), path) })
    }
  }
}

if (matches.length > 0) {
  for (const match of matches) {
    console.error(`production bundle scan rejected ${match.path}: ${match.pattern}`)
  }
  throw new Error(`production bundle credential-pattern scan found ${matches.length} match(es)`)
}

console.log(
  `Production bundle credential-pattern scan passed: files=${bundleFiles.length} patterns=${forbiddenPatterns.length}`,
)
