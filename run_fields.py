"""Run field matching against the standard vocabulary or a growing reviewed catalog."""
import sys,json,time,logging,os
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor,as_completed
from apps.intent_engine.reuse import acceptance, THRESHOLD
import gzip
from apps.intent_engine.semantic_mapping import SemanticFieldMapper, MappingAPI, FieldMappingError
P=Path(__file__).resolve().parent
api=SimpleNamespace(base=os.environ["MODEL_API_BASE"],key=os.environ["MODEL_API_KEY"],embedding_model="text-embedding-v2")
def read_input(name):
 with gzip.open(P/"inputs"/(name+".json.gz"),"rt") as stream:
  return json.load(stream)
MODE=sys.argv[1];MODEL='qwen-plus'
if MODE not in ('static','dynamic'):raise ValueError('Expected static or dynamic')
inputs=read_input('static_inputs');vocabulary=read_input('static_vocabulary')
settings=SimpleNamespace(INTENT_API_ATTEMPTS=4,INTENT_MAPPING_TIMEOUT=90,INTENT_EMBEDDING_MODEL=api.embedding_model)
def make_api(events):return MappingAPI(SimpleNamespace(api_base=api.base,api_key=api.key,model=MODEL,mode='cloud',api_events=events),settings)
def save(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));temp.replace(path)
if MODE=='static':
 catalog={r['name']:r['description'] for r in vocabulary}
 tasks=[{'sample_id':r['sample_id'],'source':r,'catalog':catalog,'id_by_name':{n:n for n in catalog}} for r in inputs]
 threshold=.8498682050406933
else:
 rows=read_input('dynamic_inputs');tasks=[];bank=[]
 for row in rows:
  bank.extend(row['reviewed_additions'])
  names=[r['name'] for r in bank];catalog={};id_by_name={}
  for r in bank:
   name=r['name'] if names.count(r['name'])==1 else r['name']+' [entry '+r['id']+']'
   catalog[name]=r['description'];id_by_name[name]=r['id']
  tasks.append({'sample_id':row['sample_id'],'source':row['source'],'catalog':catalog,'id_by_name':id_by_name})
 profiles = {"original": .8449642479419708, "reuse120-dev": .8859228696498564, "reuse120-explore": THRESHOLD, "dev-calibrated": .8704374672594225,
             "exploratory-135": .8714193437317926}
 profile = os.environ.get("DYNAMIC_PROFILE", "reuse120-explore")
 threshold = profiles[profile]
folder=P/'fields'/MODE
if MODE == 'dynamic' and profile != 'original':
 folder=P/'fields'/('dynamic-'+profile)
class TracedMapper(SemanticFieldMapper):
 def acceptance_score(self,winner,scores,llm,agree,fused):
  if MODE != 'dynamic' or profile not in ('reuse120-dev','reuse120-explore'):
   return super().acceptance_score(winner,scores,llm,agree,fused)
  def margin(values):
   return values[winner]-max((v for k,v in values.items() if k!=winner),default=0)
  if profile=='reuse120-dev':
   return .5*scores[winner]+.5*llm[winner]+.1*margin(llm)
  return acceptance(winner,scores,llm,agree)
 def _vector_scores(self,fields):
  output=super()._vector_scores(fields);self.record['vector_scores']=output;return output

def one(task):
 target=folder/'predictions'/(task['sample_id']+'.json')
 if target.exists():return json.loads(target.read_text())
 rec={'sample_id':task['sample_id'],'model':MODEL,'run':'unified-20261110','mode':MODE,'threshold':threshold,'prediction':None,'success':False,'events':[]}
 source=task['source'];fields=[{'field':source['original_field'],'description':source['description']}];rec['source_fields']=fields
 if not task['catalog']:
  rec.update(prediction='NEW',success=True,empty_history=True);save(target,rec);return rec
 a=make_api(rec['events'])
 def nominate(fields,catalog):
  output=a.nominate(fields,catalog);rec['llm_candidates']=output;return output
 m=TracedMapper(task['catalog'],nominate,a.embed,threshold,vector_weight_agree=.75,vector_weight_disagree=.5);m.record=rec
 t=time.perf_counter()
 try:
  winner=m.resolve(fields)[0];rec.update(prediction=task['id_by_name'][winner],success=True)
 except FieldMappingError as e:
  rec['error']=str(e)
  if str(e)=='No standard field reaches the acceptance threshold' or (str(e)=='Expected one to five LLM candidates' and rec.get('llm_candidates')==[[]]):rec.update(prediction='NEW',success=True)
 except Exception as e:rec['error']=type(e).__name__
 rec['elapsed_seconds']=time.perf_counter()-t
 rec['id_by_name']=task['id_by_name'];save(target,rec);return rec
save(folder/'protocol.json',{'model':MODEL,'mode':MODE,'n':len(tasks),'threshold':threshold,'weights':{'agree':.75,'disagree':.5},'historical_predictions_reused':False,'class_hard_filter':False,'unit_filter':False,'format_repair':False,'complete':False})
with ThreadPoolExecutor(max_workers=4) as pool:
 for i,f in enumerate(as_completed([pool.submit(one,t) for t in tasks]),1):
  r=f.result()
  if i%10==0:print(MODE,i,'/',len(tasks),'last',r['sample_id'],'success',r['success'],flush=True)
meta=json.loads((folder/'protocol.json').read_text());meta['complete']=True;save(folder/'protocol.json',meta)
