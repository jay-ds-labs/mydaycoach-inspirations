import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
const base=new URL('.',import.meta.url);
const ledger=readFileSync(new URL('usage.mjs',base),'utf8').replace(/^export /gm,'');
const source=readFileSync(new URL('worker.js',base),'utf8').replace(/^import .*from '\.\/usage\.mjs';\n/,'');
if(/^import /m.test(source)||/^export /m.test(ledger))throw Error('Unexpected dependency in standalone Worker');
mkdirSync(new URL('dist/',base),{recursive:true});
const target=new URL('dist/worker.mjs',base);writeFileSync(target,ledger+'\n'+source);execFileSync(process.execPath,['--check',target.pathname]);
console.log('Created self-contained Inspire Worker with shared usage accounting.');
