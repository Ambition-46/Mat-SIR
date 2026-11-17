import gzip
import json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent;D=P/'inputs'
labels=json.loads(gzip.decompress((P/"inputs"/"static_labels.json.gz").read_bytes()));vocab=json.loads(gzip.decompress((P/"inputs"/"static_vocabulary.json.gz").read_bytes()));names={r['name'] for r in vocab}
def read(mode):return {p.stem:json.loads(p.read_text()) for p in (P/'fields'/mode/'predictions').glob('*.json')}
def binary(rows):
 tp=sum(r['truth']=='NEW' and r['prediction']=='NEW' for r in rows);fp=sum(r['truth']!='NEW' and r['prediction']=='NEW' for r in rows);fn=sum(r['truth']=='NEW' and r['prediction'] not in ('NEW',None) for r in rows);tn=sum(r['truth']!='NEW' and r['prediction'] not in ('NEW',None) for r in rows)
 p=tp/(tp+fp) if tp+fp else 0;failed_new=sum(x['truth']=='NEW' and x['prediction'] is None for x in rows);failed_known=sum(x['truth']!='NEW' and x['prediction'] is None for x in rows);r=tp/(tp+fn+failed_new) if tp+fn+failed_new else 0
 return {'n':len(rows),'TP':tp,'FP':fp,'FN':fn,'TN':tn,'failed':sum(x['prediction'] is None for x in rows),'failed_new':failed_new,'failed_known':failed_known,'P_new':p,'R_new':r,'F1_new':2*p*r/(p+r) if p+r else 0,'accuracy':(tp+tn)/len(rows)}
raw=read('static');out={'static_coverage':len(raw),'static_complete':len(raw)==984}
if len(raw)==984:
 rows=[]
 for l in labels:
  x=raw[l['sample_id']];rows.append({'sample_id':l['sample_id'],'split':l['split'],'truth':l['expected_field'] if l['expected_field'] in names else 'NEW','prediction':x['prediction'],'success':x['success']})
 test=[r for r in rows if r['split']=='test'];assert len(test)==781
 known=[r for r in test if r['truth']!='NEW'];unknown=[r for r in test if r['truth']=='NEW']
 out['static']={'n':781,'correct':sum(r['truth']==r['prediction'] for r in test),'accuracy':sum(r['truth']==r['prediction'] for r in test)/781,'known_n':len(known),'known_hits':sum(r['truth']==r['prediction'] for r in known),'unknown_n':len(unknown),'unknown_rejected':sum(r['prediction']=='NEW' for r in unknown),'new_detection':binary(test)}
 (P/'static_rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
import os
profile=os.environ.get('DYNAMIC_PROFILE','paper')
raw=read('dynamic' if profile=='original' else 'dynamic-'+profile);out.update(dynamic_coverage=len(raw),dynamic_complete=len(raw)==731)
if len(raw)==731:
 lab=json.loads(gzip.decompress((D/'dynamic_labels.json.gz').read_bytes()));rows=[{**l,'prediction':raw[l['sample_id']]['prediction']} for l in lab]
 for split in ['all','test']:
  selected=rows if split=='all' else [r for r in rows if r['split']=='test'];repeat=[r for r in selected if r['repeat']];first=[r for r in selected if not r['repeat']]
  out['dynamic_'+split]={'repeat_n':len(repeat),'hits':sum(r['prediction']==r['gold_id'] for r in repeat),'hit_rate':sum(r['prediction']==r['gold_id'] for r in repeat)/len(repeat),'first_n':len(first),'first_correct_new':sum(r['prediction']=='NEW' for r in first),'first_false_reuse':sum(r['prediction'] not in (None,'NEW') for r in first),'failed':sum(r['prediction'] is None for r in selected)}
 (P/'dynamic_rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
(P/'field_metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))
