import gzip
import json
from pathlib import Path
P=Path(__file__).resolve().parent;labels=json.loads(gzip.decompress((P/'inputs/static_labels.json.gz').read_bytes()));names={r['name'] for r in json.loads(gzip.decompress((P/'inputs/static_vocabulary.json.gz').read_bytes()))}
raw={p.stem:json.loads(p.read_text()) for p in (P/'fields/static/predictions').glob('*.json')};assert len(raw)==984
out=[]
for step in range(1,20):
 alpha=step*.05;correct=knownhit=newhit=0
 for l in labels:
  if l['split']!='test':continue
  x=raw[l['sample_id']];truth=l['expected_field'] if l['expected_field'] in names else 'NEW';pred=None
  if x['success']:
   candidates=x.get('llm_candidates',[[]])[0]
   if not candidates:pred='NEW'
   else:
    scores=x['vector_scores'][0];fused={r['field']:alpha*r['score']+(1-alpha)*scores[r['field']] for r in candidates};winner=min(fused,key=lambda n:(-fused[n],n));pred=winner if fused[winner]>=.8498682050406933 else 'NEW'
  if pred==truth:
   correct+=1;knownhit+=truth!='NEW';newhit+=truth=='NEW'
 out.append({'llm_weight':alpha,'vector_weight':1-alpha,'threshold':.8498682050406933,'n':781,'correct':correct,'accuracy':correct/781,'known_hits':knownhit,'unknown_rejected':newhit})
(P/'weight_sweep.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
