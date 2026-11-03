/* Read-only study view. Opening or switching cases never makes model calls. */
let representationData=null, representationView='study', representationCase=null, representationMutation='higher_1';
const studyFormat=v=>v==null?'—':Number(v).toFixed(2);
const studyPercent=v=>v==null?'—':(100*Number(v)).toFixed(1)+'%';
function matrixTable(values,label){return `<figure><figcaption>${escape(label)}</figcaption><div class="matrix-scroll"><table class="matrix" aria-label="${escape(label)}">${values.map(row=>`<tr>${row.map(v=>`<td>${escape(v)}</td>`).join('')}</tr>`).join('')}</table></div></figure>`;}
function energyLevels(c){
  const levels=c.D.map((row,i)=>row[i]);
  return `<figure class="study-note"><figcaption>Oracle view · same four energy levels in every basis · schematic spacing</figcaption><svg viewBox="0 0 650 170" role="img" aria-label="Four invariant energy levels and their middle splitting" style="width:100%;max-height:180px">${levels.map((v,i)=>{const y=140-i*38;return `<line x1="185" x2="325" y1="${y}" y2="${y}" stroke="#355d48" stroke-width="3"/><text x="15" y="${y+5}" fill="#26342d" font-size="15">E${i} = ${escape(v)}</text>`;}).join('')}<path d="M335 64 H350 V102 H335" fill="none" stroke="#9f6e4c" stroke-width="2"/><text x="370" y="88" fill="#9f6e4c" font-size="18">Middle gap Δ = ${escape(c.validation.gap)}</text><text x="370" y="113" fill="#647466" font-size="12">Chosen energy units; levels shown schematically</text></svg><p>Audit display: the general-rational baseline receives H and trace invariants. Only the labelled certificate condition supplies the full Q,D pair.</p></figure>`;
}
function studyChart(groups){
  const g=groups.filter(g=>g.d_prime!=null), max=Math.max(1,...g.map(v=>v.d_prime)),min=Math.min(0,...g.map(v=>v.d_prime));
  const x=i=>50+i*650/Math.max(1,g.length-1),y=v=>135-(v-min)/(max-min)*100;
  return `<svg viewBox="0 0 760 180" class="study-chart" role="img" aria-label="Discriminability by representation; higher values indicate better separation of wrong and correct claims"><path d="M50 25 V135 H720" fill="none" stroke="#b3bca8"/><text x="5" y="19">d′</text><text x="16" y="37">${max.toFixed(1)}</text><text x="16" y="137">${min.toFixed(1)}</text><path d="${g.map((v,i)=>(i?'L':'M')+x(i)+' '+y(v.d_prime)).join(' ')}" fill="none" stroke="#355d48" stroke-width="2"/>${g.map((v,i)=>`<circle cx="${x(i)}" cy="${y(v.d_prime)}" r="4" fill="#355d48"/><text x="${x(i)}" y="157" text-anchor="middle">${v.level==null?escape(v.label):'L'+v.level+(v.condition==='certificate'?' + certificate':'')}</text><text x="${x(i)}" y="${y(v.d_prime)-9}" text-anchor="middle">${studyFormat(v.d_prime)}</text>`).join('')}</svg>`;
}
function renderRepresentation(){
  const panel=$('#representation-study'), data=representationData;if(!data)return;
  const selected=data.completed;
  if(!selected){panel.hidden=true;return;}
  panel.hidden=false;
  const groups=selected.groups,completedBasis=true,useCurrent=false;
  panel.innerHTML=`<div class="study-heading"><div><div class="eyebrow">COMPLETE FIXED REPRESENTATION STUDY</div><h2>Change the basis. Keep the claim.</h2><p>Twelve underlying spectra · ${selected.usable_verdicts.toLocaleString()}/${selected.planned_verdicts.toLocaleString()} usable verdicts</p></div><span class="mini-badge">SAVED LIVE MEASUREMENTS</span></div><div id="representation-body"></div>`;
  const body=$('#representation-body');
  body.innerHTML=studyChart(groups.filter(g=>g.condition!=='certificate'))+`<div class="matrix-scroll"><table class="study-table"><thead><tr><th>Representation</th><th>Hits / wrong claims</th><th>False alarms / correct controls</th><th>d′</th><th>Failed</th><th>Confidence on false accepts</th></tr></thead><tbody>${groups.map(g=>`<tr><td>${g.level==null?'':'L'+g.level+' · '}${escape(g.label)}</td><td>${g.hits}/${g.errors} · ${studyPercent(g.hit_rate)}</td><td>${g.false_alarms}/${g.controls} · ${studyPercent(g.false_alarm_rate)}</td><td>${studyFormat(g.d_prime)}</td><td>${g.failed}</td><td>${studyPercent(g.false_accept_confidence)}</td></tr>`).join('')}</tbody></table></div>
  <p class="study-note">Higher d′ means better separation of wrong and correct claims. Extreme rates receive a finite-sample correction. Named levels do not guarantee a monotonic complexity scale. Unusable outputs are excluded and shown separately.</p>
  ${selected.certificate_effect?`<p class="study-note"><strong>Paired certificate intervention:</strong> detection change ${points(selected.certificate_effect.certificate_minus_baseline.hit_rate)}, false-alarm change ${points(selected.certificate_effect.certificate_minus_baseline.false_alarm_rate)}, d′ change ${studyFormat(selected.certificate_effect.certificate_minus_baseline.d_prime)}. A correct certificate supplies answer-bearing structure; recovery alone does not show that the model independently checked every identity.</p>`:''}
  ${completedBasis?'<p class="study-note">These are saved live measurements. The fully dense Hadamard condition also succeeds: density alone does not explain the failure. No new model calls occur when browsing these results. Full prompt and raw-response provenance remains in the original review archive.</p>':!useCurrent?'<p class="study-note">This earlier pilot establishes only the diagonal/dense comparison. Tables pool both question wordings; the case inspector uses gap-only wording.</p>':''}
  <div class="study-case-controls"><label for="study-spectrum">Underlying spectrum</label><select id="study-spectrum"></select><div id="study-levels"></div></div><div id="study-case"></div>`;
  const cases=selected.cases;
  const bases=[...new Set(cases.map(c=>c.spectrum_id))];
  representationCase=cases.find(c=>c.id===representationCase?.id)||cases.find(c=>c.spectrum_id==='basis-spectrum-005'&&c.level===0)||cases[0];
  $('#study-spectrum').innerHTML=bases.map(id=>`<option value="${escape(id)}" ${id===representationCase.spectrum_id?'selected':''}>${escape(id)}</option>`).join('');
  $('#study-spectrum').onchange=()=>{representationCase=cases.find(c=>c.spectrum_id===$('#study-spectrum').value&&c.level===representationCase.level&&c.condition===representationCase.condition)||cases.find(c=>c.spectrum_id===$('#study-spectrum').value);renderStudyCase(selected);};
  renderStudyCase(selected);
}
function renderStudyCase(data){
  const c=representationCase, choices=data.cases.filter(p=>p.spectrum_id===c.spectrum_id);
  $('#study-levels').innerHTML=choices.map(p=>`<button data-study-case="${escape(p.id)}" class="${p.id===c.id?'active':''}">${p.condition==='certificate'?'Add certificate':'L'+p.level+' · '+escape(p.label)}</button>`).join('');
  $$('[data-study-case]').forEach(b=>b.onclick=()=>{representationCase=choices.find(p=>p.id===b.dataset.studyCase);renderStudyCase(data);});
  $('#study-case').innerHTML=`<div class="truth-strip"><strong>✓ QᵀQ = I</strong><strong>✓ H = QDQᵀ</strong><strong>✓ Same energy levels</strong><strong>✓ Same characteristic polynomial</strong><strong>Exact gap ${escape(c.validation.gap)}</strong></div>
    ${energyLevels(c)}<div class="study-matrices">${matrixTable(c.D,'Original D')}${matrixTable(c.Q,'Exact basis Q')}${matrixTable(c.H,'Presented H')}</div>
    <p class="study-note">These identities were checked by exact arithmetic in the tool. They are shown to the verifier only in the certificate condition. Switching representations preserves the candidate's numerical value.</p>
    <div class="study-case-controls"><label for="study-candidate">Same candidate claim</label><select id="study-candidate">${c.cells.map(cell=>`<option value="${escape(cell.id)}" ${cell.type===representationMutation?'selected':''}>${escape(cell.label)} · ${escape(cell.candidate)}</option>`).join('')}</select></div><div id="study-candidate-result"></div>`;
  const show=()=>{
    const cell=c.cells.find(cell=>cell.id===$('#study-candidate').value);
    representationMutation=cell.type;
    $('#study-candidate-result').innerHTML=`<div class="study-outcome"><strong>Claim ${escape(cell.candidate)}</strong><span>${cell.control?'Correct control':'Incorrect exact value'}</span><strong>${studyPercent(cell.rejection_rate)} ${cell.control?'false alarms':'detected'}</strong><span>${cell.usable} usable · ${cell.failed} failed</span></div><div id="study-reasons"></div>`;
    if(!c.experiment_id){const examples=(cell.examples||[]);$('#study-reasons').innerHTML=examples.map(t=>`<p class="study-note"><strong>${t.ordinal==null?'':'Trial '+(t.ordinal+1)+' · '}${t.status&&t.status!=='ok'?'Unusable':t.valid?'PASS':'REJECT'}${t.confidence==null?'':' · '+studyPercent(t.confidence)+' confidence'}.</strong> ${escape(t.reason)}</p>`).join('');return;}
    api(`/api/experiments/${c.experiment_id}`).then(e=>{if(representationCase.id!==c.id||$('#study-candidate').value!==cell.id)return;const trials=e.results[cell.id]?.trials||[];$('#study-reasons').innerHTML=trials.map(t=>`<p class="study-note"><strong>${t.status!=='ok'?'Unusable':t.valid?'PASS':'REJECT'}${t.confidence==null?'':' · '+studyPercent(t.confidence)+' confidence'}</strong> ${escape(t.reason||t.error)}</p>`).join('');}).catch(error=>toast(error.message));
  };
  $('#study-candidate').onchange=show;
  show();
}
async function loadRepresentation(){try{representationData=await api('/api/representation');renderRepresentation();}catch(error){toast('Study summary unavailable: '+error.message);}}
