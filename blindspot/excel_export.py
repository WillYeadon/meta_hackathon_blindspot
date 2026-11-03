"""Portable Excel export for the installed Python app (standard-library OOXML).

workbook_spec is also consumed by the workbook authoring/preview workflow.
Only explicit formulas become formulas; model text is always an inline string.
"""
from io import BytesIO
import json
import math
import re
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile, ZIP_DEFLATED
from .metrics import aggregate
from .perturbations import TYPES


def column(n):
    result = ''
    while n:
        n, remainder = divmod(n-1,26); result = chr(65+remainder)+result
    return result


def workbook_spec(payload):
    e,p = payload['experiment'],payload['problem']
    results=e.get('results',{})
    cells=sorted(p['cells'],key=lambda c:(c['step'],c['is_control'],c['type']))
    spec=[]
    def sheet(name,widths,freeze=0):
        s=dict(name=name,cells={},widths=widths,heights={},freeze=freeze,formats=[],scales=[])
        spec.append(s);return s
    def put(s,row,col,value,style='body',formula=None):
        s['cells'][f'{column(col)}{row}']=dict(value=value,style=style,formula=formula)
    maps=sheet('Blind-spot map',[32]+[16]*len(p['steps']))
    detail=sheet('Cells',[34,8,26,12,14,12,12,13,14,14,14,14,14,48,65,65,65],6)
    trials=sheet('Trials',[34,10,12,12,12,80,29,29,12],5)
    reference=sheet('Reference',[10,28,85,85],7)
    put(maps,2,1,'THE BLIND-SPOT MAP','title')
    for row,value in [(3,p['title']),(4,f"{e['config']['model']}   |   {e['config']['mode'].upper()}   |   {e['config']['trials']} planned trials per cell"),
                      (5,'Controls show false-positive rates; lower is better. Dash = unavailable, not zero.'),
                      (6,'Gaps are prediction minus observation, in percentage points.')]:put(maps,row,1,value,'note')
    if e.get('basis_study'):put(maps,7,1,'Fixed basis study: '+e['basis_context']['condition']+' | Exact spectrum preserved; no new advance forecasts.','note')
    elif e.get('focus_study'):put(maps,7,1,'Fixed paired matrix evaluation | All prespecified cases included; presentations share underlying spectra.','note')
    elif e.get('search_stage'):put(maps,7,1,'Search stage: '+e['search_stage']+' | Discovery, confirmation and parameter holdout must be reported separately.','note')
    criterion='Mathematical correctness' if e.get('verifier_protocol')=='truth' else 'Original step criterion'
    put(maps,8,1,criterion+f" | {e['config'].get('max_completion_tokens',4096):,} completion-token cap",'note')
    for row,value in [(2,'Cell results'),(3,'One row per fixed perturbation. Rates exclude unusable trials.'),(4,f"Source export: {e['id']} | {e['created_at']}")]:put(detail,row,1,value,'title' if row==2 else 'note')
    headers=['Cell ID','Step','Perturbation','Control','Forecast','Rejected','Usable trials','Failed trials','Observed','Gap (pp)','Absolute gap (pp)','95% lower','95% upper','Exact edit','Original claim','Candidate claim','Prediction reason']
    for j,h in enumerate(headers,1):put(detail,6,j,h,'header')
    row_by_id={}
    for row,c in enumerate(cells,7):
        row_by_id[c['id']]=row
        record=results.get(c['id'],{});m=aggregate(record,c['is_control']);pred=record.get('prediction') or {}
        vals=[c['id'],c['step'],c['type_label'],c['is_control'],m['predicted'],m['rejected_trials'],m['valid_trials'],m['failed_trials'],m['observed'],
              None if m['calibration_gap'] is None else 100*m['calibration_gap'],None if m['absolute_calibration_error'] is None else 100*m['absolute_calibration_error'],
              (m['wilson_95'] or [None,None])[0],(m['wilson_95'] or [None,None])[1],c['mutation']['description'],
              c['original']['lhs']+' = '+c['original']['expr'],c['candidate']['lhs']+' = '+c['candidate']['expr'],pred.get('reason','')]
        for j,v in enumerate(vals,1):put(detail,row,j,v,'percent' if j in [5,9,12,13] else 'decimal' if j in [10,11] else 'body')
        put(detail,row,9,m['observed'],'percent',f'=IF(G{row}=0,"",F{row}/G{row})')
        put(detail,row,10,vals[9],'decimal',f'=IF(AND(ISNUMBER(E{row}),ISNUMBER(I{row})),100*(E{row}-I{row}),"")')
        put(detail,row,11,vals[10],'decimal',f'=IF(ISNUMBER(J{row}),ABS(J{row}),"")')
        detail['heights'][row]=58
    detail['filter']=f'A6:Q{6+len(cells)}'
    types=[(k,l) for k,l in TYPES if any(c['type']==k for c in cells)]
    types += [(c['type'],c['type_label']) for c in cells if c['type'] not in dict(types) and c['type'] not in dict(TYPES)]
    types=list(dict(types).items())
    for section,(label,letter,kind) in enumerate([('Observed detection / control rejection','I','rate'),('Predicted detection / control rejection','E','rate'),('Calibration gap (percentage points)','J','gap'),('Absolute calibration error (percentage points)','K','absolute')]):
        start=9+section*(len(types)+4)
        put(maps,start,1,label,'section')
        put(maps,start+1,1,'Perturbation','header')
        for step in p['steps']:put(maps,start+1,step['index']+1,f"Step {step['index']}",'header')
        for r,(kind_id,type_label) in enumerate(types,start+2):
            control=all(c['is_control'] for c in cells if c['type']==kind_id)
            put(maps,r,1,type_label+(' (control)' if control and 'control' not in type_label.lower() else ''),'body')
            for step in p['steps']:
                c=next((x for x in cells if x['type']==kind_id and x['step']==step['index']),None)
                if not c:put(maps,r,step['index']+1,'—','na');continue
                source=f"'Cells'!{letter}{row_by_id[c['id']]}"
                value=detail['cells'][f'{letter}{row_by_id[c["id"]]}']['value']
                put(maps,r,step['index']+1,value,'percent' if kind=='rate' else 'decimal',f'=IF(ISNUMBER({source}),{source},"")')
            maps['heights'][r]=26
            maps['scales'].append(dict(range=f'B{r}:{column(len(p["steps"])+1)}{r}',kind=kind,control=control))
    put(trials,2,1,'Individual verifier trials','title')
    put(trials,3,1,f"Source: run {e['id']}. False in Valid means the model rejected the step.",'note')
    for j,h in enumerate(['Cell ID','Trial','Status','Valid','Confidence','Reason / error','Started UTC','Completed UTC','Cached'],1):put(trials,5,j,h,'header')
    row=6
    for c in cells:
        for t in results.get(c['id'],{}).get('trials',[]):
            values=[c['id'],t.get('ordinal',0)+1,t.get('status'),t.get('valid'),t.get('confidence'),t.get('reason',t.get('error','')),t.get('started_at'),t.get('completed_at'),t.get('cached')]
            for j,v in enumerate(values,1):put(trials,row,j,v,'percent' if j==5 else 'body')
            trials['heights'][row]=48;row+=1
    trials['filter']=f'A5:I{max(5,row-1)}'
    put(reference,2,1,'Problem and reference solution','title')
    put(reference,3,2,'Problem');put(reference,3,3,p['question']);reference['heights'][3]=110
    put(reference,5,2,'Assumptions');put(reference,5,3,p['assumptions']);reference['heights'][5]=80
    for j,h in enumerate(['Step','Title','Working','Claim (SymPy notation)'],1):put(reference,7,j,h,'header')
    for row,step in enumerate(p['steps'],8):
        for j,v in enumerate([step['index'],step['label'],step['text'],step['lhs']+' = '+step['expr']],1):put(reference,row,j,v)
        reference['heights'][row]=65
    return spec


def xlsx_bytes(payload):
    """Write typed cells, cached formulas, frozen headers and native colour scales."""
    sheets=workbook_spec(payload); output=BytesIO()
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    styles={'body':0,'title':1,'header':2,'percent':3,'decimal':4,'note':5,'section':6,'na':7}
    def clean(value):return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value))[:32767]
    with ZipFile(output,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1))+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name={quoteattr(s["name"])} sheetId="{i}" r:id="rId{i}"/>' for i,s in enumerate(sheets,1))+'</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        fonts='<fonts count="4"><font><sz val="11"/><name val="Arial"/><color rgb="FF26342D"/></font><font><b/><sz val="16"/><name val="Arial"/><color rgb="FF26342D"/></font><font><b/><sz val="11"/><name val="Arial"/><color rgb="FFFFFFFF"/></font><font><i/><sz val="10"/><name val="Arial"/><color rgb="FF61705E"/></font></fonts>'
        fills='<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF294331"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8EBE1"/><bgColor indexed="64"/></patternFill></fill></fills>'
        xfs=[]
        for font,fill,num,wrap in [(0,0,0,1),(1,0,0,0),(2,2,0,1),(0,0,10,0),(0,0,2,0),(3,0,0,0),(0,3,0,0),(3,3,0,0)]:
            xfs.append(f'<xf fontId="{font}" fillId="{fill}" borderId="0" numFmtId="{num}" xfId="0" applyAlignment="1" applyNumberFormat="1"><alignment vertical="center" wrapText="{wrap}"/></xf>')
        z.writestr('xl/styles.xml',f'<styleSheet xmlns="{ns}">{fonts}{fills}<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="8">'+''.join(xfs)+'</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for i,s in enumerate(sheets,1):
            rows={}
            for address,c in s['cells'].items():rows.setdefault(int(re.search(r'\d+',address)[0]),[]).append((address,c))
            parts=[f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0" showGridLines="0">']
            if s['freeze']:parts.append(f'<pane ySplit="{s["freeze"]}" topLeftCell="A{s["freeze"]+1}" activePane="bottomLeft" state="frozen"/>')
            parts.append('</sheetView></sheetViews><cols>'+''.join(f'<col min="{j}" max="{j}" width="{w}" customWidth="1"/>' for j,w in enumerate(s['widths'],1))+'</cols><sheetData>')
            for row,items in sorted(rows.items()):
                parts.append(f'<row r="{row}" ht="{s["heights"].get(row,24)}" customHeight="1">')
                for address,c in items:
                    v=c['value'];st=styles[c['style']];f=c['formula']
                    if f:
                        cache='' if v is None else escape(str(v));typ=' t="str"' if v is None else ''
                        parts.append(f'<c r="{address}" s="{st}"{typ}><f>{escape(f[1:])}</f><v>{cache}</v></c>')
                    elif type(v) is bool:parts.append(f'<c r="{address}" s="{st}" t="b"><v>{int(v)}</v></c>')
                    elif isinstance(v,(int,float)) and math.isfinite(v):parts.append(f'<c r="{address}" s="{st}"><v>{v}</v></c>')
                    elif v is None:parts.append(f'<c r="{address}" s="{st}"/>')
                    else:parts.append(f'<c r="{address}" s="{st}" t="inlineStr"><is><t xml:space="preserve">{escape(clean(v))}</t></is></c>')
                parts.append('</row>')
            parts.append('</sheetData>')
            if s.get('filter'):parts.append(f'<autoFilter ref="{s["filter"]}"/>')
            for priority,scale in enumerate(s['scales'],1):
                colors=['EDC9AF','FCFCF9','567448'];bounds=[0,.5,1]
                if scale['kind']=='gap':colors=['BCD2DF','FCFCF9','CF8B68'];bounds=[-100,0,100]
                elif scale['kind']=='absolute':colors=['FCFCF9','EAD8BA','CF8B68'];bounds=[0,50,100]
                elif scale['control']:colors.reverse()
                parts.append(f'<conditionalFormatting sqref="{scale["range"]}"><cfRule type="colorScale" priority="{priority}"><colorScale>'+''.join(f'<cfvo type="num" val="{v}"/>' for v in bounds)+''.join(f'<color rgb="FF{v}"/>' for v in colors)+'</colorScale></cfRule></conditionalFormatting>')
            parts.append('</worksheet>');z.writestr(f'xl/worksheets/sheet{i}.xml',''.join(parts))
    return output.getvalue()


if __name__=='__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser();parser.add_argument('export_json');parser.add_argument('output_xlsx')
    args=parser.parse_args();Path(args.output_xlsx).write_bytes(xlsx_bytes(json.loads(Path(args.export_json).read_text(encoding='utf-8'))))
