/* Offline UI data/renderer check. No browser dependency, network or Meta calls. */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=name=>fs.readFileSync(path.join(root,name),'utf8');
const representation=JSON.parse(read('data/basis-study-results.json'));
const results=JSON.parse(read('data/final-panel-public.json'));
const requested=[],elements=new Map(),documentEvents=[];
function element(key){if(!elements.has(key))elements.set(key,{innerHTML:'',hidden:false,open:false,handlers:{},addEventListener(type,fn){this.handlers[type]=fn},querySelector(){return {focus(){}}},focus(){},scrollIntoView(){}});return elements.get(key)}
const ctx={console,document:{addEventListener:(type,fn)=>documentEvents.push([type,fn])},
  $:element,representationData:null,renderRepresentation(){},loadFinalPanel:async()=>{},
  escape:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  api:async url=>{requested.push(url);if(url==='/api/representation')return {completed:representation};if(url==='/api/final-study')return results;throw Error('Unexpected request '+url)}};
vm.createContext(ctx);vm.runInContext(read('static/demo.js'),ctx);
await vm.runInContext('loadGuidedDemo()',ctx);
assert.deepEqual(requested,['/api/representation','/api/final-study']);
assert(!element('#verifier-demo').innerHTML.includes('Saved demo unavailable'));
for(let i=0;i<5;i++){
 vm.runInContext(`demoState.step=${i};renderGuidedDemo()`,ctx);
 const html=element('#verifier-demo').innerHTML;
 assert(!html.includes('undefined')&&!html.includes('NaN'));
 if(i===0){assert(html.includes('101/10400'));assert(html.includes('100/10400'));assert(html.includes('EXACTLY 1% TOO LARGE'))}
 if(i===1){assert(html.includes('FALSE PASS'));assert(html.includes('46.9%'));assert(html.includes('18.4%'));assert(html.includes('Same false claim'))}
 if(i===2)assert(html.includes('Hadamard')&&html.includes('100.0% detection'));
 if(i===3){assert(html.includes('20/20 correct rejections'));assert(html.includes('1680/1680'));assert(html.includes('3/480'));assert(html.includes('their acquisition cost'))}
 if(i===4){assert(html.includes('877'));assert(html.includes('44'));assert(html.includes('$0.343'));assert(html.includes('$37.04'));assert(html.includes('$5.35'))}
}
vm.runInContext("demoState.condition='outer_anchors';demoState.model='wonder_high';renderGuidedDemo()",ctx);
assert(element('#verifier-demo').innerHTML.includes('$0.050'));
assert.deepEqual(requested,['/api/representation','/api/final-study']);
assert(read('static/index.html').includes('<details id="research-provenance"'));
assert(!read('static/index.html').includes('legacy-workspace'));
assert(!read('static/index.html').includes('Original editable maps and earlier self-forecasts'));
assert(!read('static/mark.svg').includes('<circle'));
console.log('Guided demo checks passed: exact fixed claim, five stages, saved metrics, coverage, costs and GET-only loading.');
