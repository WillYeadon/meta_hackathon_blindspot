/* Generate SCREEN_CONTENT.md using the actual UI renderers and bundled results. */
import fs from 'node:fs';import path from 'node:path';import vm from 'node:vm';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=name=>fs.readFileSync(path.join(root,name),'utf8');
const source=fs.existsSync(path.join(root,'data/final-panel-results.json'))?'data/final-panel-results.json':'data/final-panel-public.json';
const context={document:{addEventListener(){}},$:()=>({addEventListener(){}}),console,escape:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))};
vm.createContext(context);vm.runInContext(read('static/demo.js'),context);vm.runInContext(read('static/screen-content.js'),context);
context.representation=JSON.parse(read('data/basis-study-results.json'));context.results=JSON.parse(read(source));
vm.runInContext('demoState.representation=representation;demoState.results=results',context);
const index=read('static/index.html');
const section=className=>index.match(new RegExp('<section class="'+className+'">([\\s\\S]*?)<\\/section>'))?.[0]||'';
context.content={introHTML:section('intro demo-intro'),workflowHTML:index.match(/<ol class="workflow"[\s\S]*?<\/ol>/)?.[0]||'',aboutHTML:section('build-story'),scopeHTML:section('current-scope')};
const markdown=vm.runInContext('screenContentMarkdown(content)',context);const target=process.argv[2]?path.resolve(process.argv[2]):path.join(root,'SCREEN_CONTENT.md');
fs.writeFileSync(target,markdown);console.log(`Screen content exported to ${target}`);
