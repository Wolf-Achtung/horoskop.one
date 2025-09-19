import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const outdir = path.resolve(__dirname, '..', 'dist');
const publicDir = path.resolve(__dirname, '..', 'public');

if (!fs.existsSync(outdir)) fs.mkdirSync(outdir, { recursive: true });

function sri(filePath) {
  const data = fs.readFileSync(filePath);
  const hash = crypto.createHash('sha384').update(data).digest('base64');
  return `sha384-${hash}`;
}

async function copyPublicWithReplace(replacements) {
  const entries = fs.readdirSync(publicDir, { withFileTypes: true });
  for (const e of entries) {
    const src = path.join(publicDir, e.name);
    const dst = path.join(outdir, e.name);
    if (e.isDirectory()) {
      fs.mkdirSync(dst, { recursive: true });
      const stack = [[src, dst]];
      while (stack.length) {
        const [s,d] = stack.pop();
        for (const child of fs.readdirSync(s, { withFileTypes: true })) {
          const sc = path.join(s, child.name);
          const dc = path.join(d, child.name);
          if (child.isDirectory()) {
            fs.mkdirSync(dc, { recursive: true });
            stack.push([sc, dc]);
          } else {
            let buf = fs.readFileSync(sc);
            const isText = /\.(html|css|js|json|txt|xml|svg)$/i.test(child.name);
            if (isText) {
              let txt = buf.toString('utf8');
              for (const [key, value] of Object.entries(replacements)) {
                txt = txt.split(key).join(String(value));
              }
              buf = Buffer.from(txt, 'utf8');
            }
            fs.writeFileSync(dc, buf);
          }
        }
      }
    } else {
      let buf = fs.readFileSync(src);
      const isText = /\.(html|css|js|json|txt|xml|svg)$/.test(e.name);
      if (isText) {
        let txt = buf.toString('utf8');
        for (const [key, value] of Object.entries(replacements)) {
          txt = txt.split(key).join(String(value));
        }
        buf = Buffer.from(txt, 'utf8');
      }
      fs.writeFileSync(dst, buf);
    }
  }
}

async function run() {
  await build({
    entryPoints: ['src/main.ts'],
    outdir: 'dist/assets',
    bundle: true,
    sourcemap: false,
    minify: true,
    target: ['es2019'],
    format: 'iife',
    platform: 'browser',
    loader: { '.svg': 'text' },
    logLevel: 'info'
  });

  const assetsDir = path.resolve(outdir, 'assets');
  const files = fs.readdirSync(assetsDir).filter(f => f.endsWith('.js'));
  const jsFile = files[0];
  const integrity = sri(path.join(assetsDir, jsFile));

  await copyPublicWithReplace({
    '__APP_JS__': `/assets/${jsFile}`,
    '__INTEGRITY__': integrity
  });

  const headersSrc = path.resolve(__dirname, '..', '_headers');
  if (fs.existsSync(headersSrc)) fs.copyFileSync(headersSrc, path.join(outdir, '_headers'));
  console.log('Build complete → dist/');
}

run().catch(err => { console.error(err); process.exit(1); });
