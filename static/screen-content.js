/* Export the actual rendered demo copy and numbers for script review. No calls. */
function screenDecode(value){
  const named={amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' '};
  return String(value).replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi,(_,key)=>key[0]==='#'?String.fromCodePoint(key[1].toLowerCase()==='x'?parseInt(key.slice(2),16):parseInt(key.slice(1),10)):named[key.toLowerCase()]);
}
function screenInline(html){
  return screenDecode(html.replace(/<mfrac>\s*<mn>(.*?)<\/mn>\s*<mn>(.*?)<\/mn>\s*<\/mfrac>/gs,' $1/$2 ')
    .replace(/<small\b[^>]*>/gi,' · ').replace(/<[^>]*>/g,' ')).replace(/\s+/g,' ').trim();
}
function screenHTMLMarkdown(html){
  let text=html.replace(/<svg\b[^>]*>[\s\S]*?<\/svg>/gi,svg=>{const label=svg.match(/aria-label="([^"]*)"/);return `\n[Diagram: ${screenDecode(label?.[1]||'exact basis/spectrum visualisation')}]\n`;});
  text=text.replace(/<table\b[^>]*>([\s\S]*?)<\/table>/gi,(_,table)=>{
    const rows=[...table.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)].map(row=>[...row[1].matchAll(/<t[dh]\b[^>]*>([\s\S]*?)<\/t[dh]>/gi)].map(cell=>screenInline(cell[1]).replace(/\|/g,'\\|')));
    if(!rows.length)return '';
    const caption=table.match(/<caption\b[^>]*>([\s\S]*?)<\/caption>/i);
    if(!/<thead\b/i.test(table))rows.unshift(rows[0].map((_,i)=>`Column ${i+1}`));
    return `\n\n${caption?screenInline(caption[1])+'\n\n':''}| ${rows[0].join(' | ')} |\n| ${rows[0].map(()=> '---').join(' | ')} |\n${rows.slice(1).map(row=>'| '+row.join(' | ')+' |').join('\n')}\n\n`;
  });
  text=text.replace(/<h[123]\b[^>]*>([\s\S]*?)<\/h[123]>/gi,(_,heading)=>'\n\n### '+screenInline(heading)+'\n\n')
    .replace(/<summary\b[^>]*>([\s\S]*?)<\/summary>/gi,(_,summary)=>'\n\nOptional panel — '+screenInline(summary)+'\n\n')
    .replace(/<figcaption\b[^>]*>([\s\S]*?)<\/figcaption>/gi,(_,caption)=>'\n\n'+screenInline(caption)+'\n\n')
    .replace(/<option\b[^>]*>([\s\S]*?)<\/option>/gi,(_,option)=>' '+screenInline(option)+'; ')
    .replace(/<li\b[^>]*>/gi,'\n- ')
    .replace(/<mfrac>\s*<mn>(.*?)<\/mn>\s*<mn>(.*?)<\/mn>\s*<\/mfrac>/gs,' $1/$2 ')
    .replace(/<br\s*\/?>/gi,'\n').replace(/<\/(?:p|div|figure|details|fieldset|blockquote|footer|section|ol)>/gi,'\n\n')
    .replace(/<[^>]*>/g,' ');
  return screenDecode(text).split('\n').map(line=>line.replace(/[\t ]+/g,' ').trim()).join('\n').replace(/\n{3,}/g,'\n\n').trim();
}
function screenContentMarkdown({introHTML='',workflowHTML='',aboutHTML='',scopeHTML=''}={}){
  if(!demoState.results||!demoState.representation)throw Error('Load the saved study before exporting.');
  const previous={model:demoState.model,condition:demoState.condition};
  try{
    const sections=['# Blindspot screen content','',
      'This is the application content for reviewing the video script. It is generated from the same HTML/render functions and saved results as the screen. It describes content rather than appearance; screenshots are useful for layout feedback. All optional proof panels are included even when closed on screen. No API calls are made.','',
      '## Science context for the introduction','',
      'The test matrix can be interpreted as a four-level Hamiltonian. Its ordered eigenvalues are energy levels E₀ ≤ E₁ ≤ E₂ ≤ E₃. The target is the middle splitting Δ = E₂ − E₁, rather than necessarily the ground-state gap. The recorded API prompts described coupled modes and an exact spectral claim; the Hamiltonian is a physical interpretation. A basis change changes the representation, not the physical levels or the claim’s truth.','',
      'The demonstration uses spectrum 005: [0, 623/208, 625/208, 8], in consistent chosen energy units. The exact splitting is 1/104 = 100/10400. The candidate 101/10400 is exactly 1% too large. Level spacing in the graphic is schematic. This example was chosen after collection for illustration; aggregate measurements include every frozen case.','',
      'An exact oracle supplies calibration cases for the AI reviewer. Trusted checkpoints in this study are the exact outer levels, E₀ = 0 and E₃ = 8. Together with the supplied traces they determine the middle splitting. Their rescue does not uniquely reveal the model’s internal mechanism, and obtaining such facts in a real workflow has its own cost.','',
      '## Landing screen', '', screenHTMLMarkdown(introHTML+workflowHTML), ''];
    const renderers=[demoIntro,demoBasis,demoDensity,demoCheckpoints];
    for(let i=0;i<renderers.length;i++)sections.push(`## Screen ${i+1} ${demoSteps[i]}`,'',screenHTMLMarkdown(renderers[i]()),'');
    for(const condition of ['dense','outer_anchors']){
      demoState.model='spark_low';demoState.condition=condition;
      sections.push(`## Screen 5 Choose a verifier — ${condition==='dense'?'matrix and trace invariants':'with trusted checkpoints'}`,'',screenHTMLMarkdown(demoDecision()),'');
      sections.push('### Other selected-verifier readouts','');
      for(const model of ['spark_high','wonder_high']){
        demoState.model=model;const match=demoDecision().match(/<div class="decision-assessment"[^>]*>([\s\S]*?)<\/div>/);
        if(match)sections.push(screenHTMLMarkdown(match[1]),'');
      }
    }
    sections.push('## About the build','',screenHTMLMarkdown(aboutHTML),'','## Current scope and extension pattern','',screenHTMLMarkdown(scopeHTML),'',
      '## Evidence and review boundaries','',
      'These are saved live measurements. Higher-model settings have one attempt per cell, while Spark-low has twenty. Missing higher-model verdicts reached the completion-token limit. The family was discovered adaptively; held-out spectra within it do not establish general scientific-review competence. The exact question is whether a reviewer can reliably distinguish right from wrong on these controlled cases.','',
      'For a script review, upload this file with your local video script and FINAL_FINDINGS.md. Ask the assistant to keep the scientific meaning, distinguish the oracle from model-visible information, and avoid implying quantum hardware, privileged introspection or arbitrary-paper review.','');
    return sections.join('\n');
  }finally{demoState.model=previous.model;demoState.condition=previous.condition;}
}
function enableScreenContentExport(){const button=$('#export-screen-content');if(button)button.disabled=false;}
const screenExportButton=$('#export-screen-content');
if(screenExportButton)screenExportButton.addEventListener('click',()=>{
  try{
    const text=screenContentMarkdown({introHTML:$('.demo-intro').outerHTML,workflowHTML:$('.workflow').outerHTML,aboutHTML:$('.build-story').outerHTML,scopeHTML:$('.current-scope').outerHTML});
    const url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='SCREEN_CONTENT.md';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    toast('Screen content downloaded. It includes all five steps and both comparison conditions.');
  }catch(error){toast(error.message);}
});
