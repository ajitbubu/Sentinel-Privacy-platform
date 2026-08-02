import { build } from 'esbuild';
import { gzipSync, brotliCompressSync } from 'node:zlib';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

mkdirSync('dist', { recursive: true });

// The budget exists because this script sits on the customer's critical
// rendering path. Anything that pushes it over gets questioned rather than
// waved through.
const BUDGET_GZIP = 15 * 1024;

await build({
  entryPoints: ['src/index.ts'],
  bundle: true,
  minify: true,
  format: 'iife',
  target: ['es2018'],       // covers Safari 12+, which still shows up in India
  outfile: 'dist/sentinel.js',
  legalComments: 'none',
});

const raw = readFileSync('dist/sentinel.js');
const gz = gzipSync(raw, { level: 9 });
const br = brotliCompressSync(raw);

const k = (b) => (b.length / 1024).toFixed(1) + ' KB';
console.log(`raw    ${k(raw)}`);
console.log(`gzip   ${k(gz)}   (budget ${(BUDGET_GZIP / 1024).toFixed(0)} KB)`);
console.log(`brotli ${k(br)}`);

writeFileSync('dist/sentinel.js.gz', gz);

if (gz.length > BUDGET_GZIP) {
  console.error(`\nover budget by ${((gz.length - BUDGET_GZIP) / 1024).toFixed(1)} KB`);
  process.exit(1);
}
