
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
            if (child.isDirectory()) { fs.mkdirSync(dc, { recursive: true }); stack.push([sc, dc]); }
            else {
              let buf = fs.readFileSync(sc);
              const isText = /\.(html|css|js|json|txt|xml|svg)$/i.test(child.name);
              if (isText) {
                let txt = buf.toString('utf8');
                for (const [k, v] of Object.entries(replacements)) txt = txt.split(k).join(String(v));
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
          for (const [k, v] of Object.entries(replacements)) txt = txt.split(k).join(String(v));
          buf = Buffer.from(txt, 'utf8');
        }
        fs.writeFileSync(dst, buf);
      }
    }
  }

  async function run() {
    await build({
      entryPoints: ['src/main.ts', 'src/board.ts'],
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
    await copyPublicWithReplace({
      '__APP_JS__': '/assets/main.js',
      '__INTEGRITY__': sri(path.join(assetsDir, 'main.js')),
      '__BOARD_JS__': '/assets/board.js',
      '__BOARD_INTEGRITY__': sri(path.join(assetsDir, 'board.js')),
    });
    console.log('Build complete → dist/');
  }
  run().catch(err => { console.error(err); process.exit(1); });
