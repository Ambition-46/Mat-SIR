import json
import math
import os
import re
import pymysql
from tempfile import TemporaryDirectory
from sql.settings import get_mysql_conf
from sql.intent_sql_executor import IntentSqlExecutor
from pathlib import Path
from types import SimpleNamespace
from apps.intent_engine.reuse import acceptance, THRESHOLD, MODEL as REUSE_MODEL
from apps.intent_engine.semantic_mapping import SemanticFieldMapper, MappingAPI, FieldMappingError

from .units import normalize_value, standard_units, normalize_sir

def connect():
    return pymysql.connect(**get_mysql_conf(), cursorclass=pymysql.cursors.DictCursor)


def catalog(db):
    with db.cursor() as cur:
        cur.execute("SELECT property_name,property_description FROM property_table")
        return {r['property_name']:r['property_description'] for r in cur.fetchall()}


class HistoricalMatcher(SemanticFieldMapper):
    def acceptance_score(self,winner,scores,llm,agree,fused):
        return acceptance(winner,scores,llm,agree)

def mapping_api(embedding_model, model=None):
    cfg=SimpleNamespace(api_base=os.environ['MODEL_API_BASE'],api_key=os.environ['MODEL_API_KEY'],
                        model=model or os.getenv('MODEL_NAME','qwen-plus'),mode='cloud')
    return MappingAPI(cfg,SimpleNamespace(INTENT_EMBEDDING_MODEL=embedding_model))

def mapper(properties,query=False,historical=False):
    api=mapping_api(os.getenv('EMBEDDING_MODEL','text-embedding-v2'), REUSE_MODEL if historical else (None if query else 'qwen-plus'))
    matcher_class=HistoricalMatcher if historical else SemanticFieldMapper
    threshold=THRESHOLD if historical else (.75 if query else .8498682050406933)
    return matcher_class(properties,api.nominate,api.embed,threshold,
                               vector_weight_agree=.5 if query else .75,vector_weight_disagree=.5)

def upload(db,payload,online):
    props=catalog(db)
    with db.cursor() as cur:
        cur.execute("SELECT p.property_name FROM matsir_history h JOIN property_table p USING(property_id)")
        history={r['property_name']:props[r['property_name']] for r in cur.fetchall()}
    standard={name:desc for name,desc in props.items() if name not in history}
    matchers=[mapper(standard)] if online else []
    if online and history: matchers.append(mapper(history,historical=True))
    cache={}
    dataset=payload['dataset']
    records=payload['records']
    if not isinstance(dataset,str) or not dataset.strip() or not isinstance(records,list) or not records:
        raise ValueError('Expected dataset name and records array')
    prepared=[]
    for record in records:
        source=str(record['id'])
        if not source or not record['fields']: raise ValueError('Missing record id or fields')
        for field in record['fields']:
            name=field['name'];desc=field.get('description','');unit=field.get('unit','');val=field['value']
            if not isinstance(name,str) or not name.strip() or not isinstance(val,(int,float,str)) or isinstance(val,bool):
                raise ValueError('Invalid observation')
            if isinstance(val,float) and not math.isfinite(val): raise ValueError('Nonfinite value')
            key=(name,desc)
            if key not in cache:
                if online:
                    prop=None
                    for match in matchers:
                        try:
                            prop=match.resolve([dict(field=name,description=desc)])[0]
                            break
                        except FieldMappingError as exc:
                            if str(exc) not in ('No standard field reaches the acceptance threshold','Expected one to five LLM candidates'):raise
                else: prop=name if name in props else None
                cache[key]=prop
            prepared.append((source,name,desc,unit,val,cache[key]))
    classifications = []
    if online and prepared:
        from classification.predict import classify
        samples = {}
        for _, name, desc, _, value, _ in prepared:
            values = samples.setdefault((name, desc), [])
            if len(values) < 5 and str(value) not in values:
                values.append(str(value))
        inputs = [dict(original_field=name, description=desc, sample_values=values)
                  for (name, desc), values in samples.items()]
        predictions = classify(inputs, mapping_api('text-embedding-v2').embed)
        classifications = [dict(field=name, description=desc, **role)
                           for (name, desc), role in zip(samples, predictions)]
    roles={(r['field'],r['description']):r['role'] for r in classifications}
    pending_count=0
    with db.cursor() as cur:
        ids={}
        for source,name,desc,unit,val,prop in prepared:
            if source not in ids:
                cur.execute("INSERT INTO matsir_source(dataset,source_id) VALUES (%s,%s) ON DUPLICATE KEY UPDATE source_id=source_id",(dataset,source))
                cur.execute("SELECT data_id FROM matsir_source WHERE dataset=%s AND source_id=%s FOR UPDATE",(dataset,source))
                eid=cur.fetchone()['data_id']
                if eid is None:
                    cur.execute("INSERT INTO entity_table(title,object,operate,result) VALUES (%s,'0','0','0')",(dataset,))
                    eid=cur.lastrowid
                    cur.execute("UPDATE matsir_source SET data_id=%s WHERE dataset=%s AND source_id=%s",(eid,dataset,source))
                ids[source]=eid
            eid=ids[source]
            cur.execute("SELECT property_name,description,unit,role FROM matsir_field WHERE data_id=%s AND field=%s",(eid,name))
            old=cur.fetchone()
            if old and old['description']==desc and old['unit']==unit:
                prop=prop or old['property_name']
            role=roles.get((name,desc)) or (old or {}).get('role')
            cur.execute("REPLACE INTO matsir_field(data_id,field,description,unit,raw_value,property_name,role) VALUES (%s,%s,%s,%s,%s,%s,%s)",(eid,name,desc,unit,json.dumps(val,ensure_ascii=False),prop,role))
            pending_count+=prop is None
        for eid in ids.values():
            sync_values(cur,eid)
    db.commit()
    return dict(records=len(records),observations=len(prepared),pending=pending_count,classifications=classifications)


def sync_values(cur,eid):
    # Only entities owned by the upload service reach this function.
    cur.execute("DELETE FROM value_table WHERE data_id=%s",(eid,))
    cur.execute("SELECT f.raw_value,f.unit,f.role,p.property_id,p.property_name FROM matsir_field f JOIN property_table p ON p.property_name=f.property_name WHERE f.data_id=%s",(eid,))
    observations=cur.fetchall()
    units=standard_units(cur)
    masks=dict(object=0,operate=0,result=0)
    for row in observations:
        pid=row['property_id']
        value=json.loads(row['raw_value'])
        target=units.get(row['property_name'])
        value=normalize_value(value,row['unit'],target)
        cur.execute("INSERT INTO value_table(data_id,property_id,property_name,value) VALUES (%s,%s,%s,%s)",(eid,pid,row['property_name'],str(value)))
        if row['role']:
            if pid>=1024: raise ValueError('Property ID exceeds entity role bitmap capacity')
            masks[row['role']]|=1<<pid
    cur.execute("UPDATE entity_table SET object=%s,operate=%s,result=%s WHERE data_id=%s",tuple(format(v,'b') for v in masks.values())+(eid,))


def pending(db):
    with db.cursor() as cur:
        cur.execute("SELECT data_id AS entity_id,field,description,unit,raw_value FROM matsir_field WHERE property_name IS NULL")
        rows=cur.fetchall()
        for row in rows: row['value']=json.loads(row.pop('raw_value'))
        return rows


def review(db,p):
    eid=p['entity_id']
    with db.cursor() as cur:
        cur.execute("SELECT data_id FROM matsir_source WHERE data_id=%s FOR UPDATE",(eid,))
        if not cur.fetchone(): raise ValueError('Unknown uploaded entity')
        cur.execute("SELECT property_id FROM property_table WHERE property_name=%s",(p['property'],))
        if not cur.fetchone():
            cur.execute("INSERT INTO property_table(property_name,property_description) VALUES (%s,%s)",(p['property'],p['description']))
            cur.execute("INSERT INTO matsir_history VALUES (%s)",(cur.lastrowid,))
        cur.execute("UPDATE matsir_field SET property_name=%s WHERE data_id=%s AND field=%s AND property_name IS NULL",(p['property'],eid,p['field']))
        if cur.rowcount!=1: raise ValueError('Pending observation not found')
        sync_values(cur,eid)
    db.commit()
    return dict(approved=1)

def parse(question,db,online):
    props=catalog(db)
    if online:
        from django.conf import settings
        if not settings.configured:
            settings.configure(INTENT_PROPERTY_REFRESH_INTERVAL=float("inf"),INTENT_MODE='cloud',INTENT_CLOUD_API_KEY=os.environ['MODEL_API_KEY'],
                INTENT_CLOUD_API_BASE=os.environ['MODEL_API_BASE'],INTENT_CLOUD_MODEL=os.getenv('MODEL_NAME','qwen-plus'))
        from apps.intent_engine.parser import IntentParser,extraction_prompt
        parser=IntentParser()
        with db.cursor() as cur:
            cur.execute('SELECT DISTINCT title FROM entity_table')
            datasets='\n'.join(r['title'] for r in cur.fetchall())
        parser.system_prompt=extraction_prompt(parser.SYSTEM_PROMPT_TEMPLATE,datasets)
        raw=parser._parse_json(parser._call_llm(question))
        return mapper(props,True).map_sir(raw,question)
    conditions=[]
    for clause in re.split(r'\s+AND\s+',question.strip(),flags=re.I):
        m=re.fullmatch(r'([\w]+)\s*(>=|<=|>|<|=)\s*(-?\d+(?:\.\d+)?)\s*([^\s]*)',clause)
        if not m or m[1] not in props: raise ValueError('Offline syntax: tensile_strength > 500 MPa AND yield_strength > 300 MPa')
        conditions.append(dict(field=m[1],operator=m[2],value=float(m[3]),unit=m[4]))
    return dict(groups=[dict(conditions=conditions,logic_op='and')],group_logic_op='and')

def query(db,question,online):
    sir=parse(question,db,online)
    with db.cursor() as cur:
        sir=normalize_sir(sir,standard_units(cur))
    if online:
        with TemporaryDirectory() as tmp:
            engine=IntentSqlExecutor.from_intent_dict(sir,question,base_dir=Path(tmp))
            result=engine.run()
        ids=result['answer']['matched_data_ids']
        return dict(sir=sir,sql=result.get('sql',result.get('final_sql')),answer=result['answer'],
                    records=[dict(id=i) for i in ids])
    terms=[]; params=[]
    for c in sir['groups'][0]['conditions']:
        # Uploaded units are explicit; the original dump has no unit column.
        term=("EXISTS (SELECT 1 FROM value_table v LEFT JOIN matsir_field f ON f.data_id=v.data_id AND f.property_name=v.property_name "
              "WHERE v.data_id=e.data_id AND v.property_name=%s AND REGEXP_LIKE(v.value,'^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$') AND CAST(v.value AS DOUBLE) "+c['operator']+" %s")
        params.extend([c['field'],c['value']])
        # Values and query thresholds now share the registered standard unit.
        terms.append(term+')')
    sql='SELECT e.data_id AS id,e.title AS dataset,s.source_id FROM entity_table e LEFT JOIN matsir_source s USING(data_id) WHERE '+' AND '.join(terms)+' ORDER BY e.data_id'
    with db.cursor() as cur:
        cur.execute(sql,params)
        return dict(sir=sir,sql=sql,parameters=params,records=cur.fetchall())


def full_rows(db,ids):
    if not isinstance(ids,list) or len(ids)>500 or any(type(i) is not int for i in ids):
        raise ValueError('Expected at most 500 integer IDs')
    if not ids: return []
    marks=','.join(['%s']*len(ids))
    with db.cursor() as cur:
        cur.execute(f"SELECT e.data_id AS id,e.title AS dataset,s.source_id FROM entity_table e LEFT JOIN matsir_source s USING(data_id) WHERE e.data_id IN ({marks})",ids)
        records={r['id']:dict(**r,fields=[]) for r in cur.fetchall()}
        cur.execute(f"SELECT data_id,field,description,property_name AS property,raw_value,unit FROM matsir_field WHERE data_id IN ({marks}) ORDER BY field",ids)
        for r in cur.fetchall():
            r['value']=json.loads(r.pop('raw_value'))
            records[r.pop('data_id')]['fields'].append(r)
        cur.execute(f"SELECT v.data_id,v.property_name AS field,v.property_name AS property,p.property_description AS description,v.value,NULL AS unit FROM value_table v JOIN property_table p USING(property_id) LEFT JOIN matsir_source s USING(data_id) WHERE s.data_id IS NULL AND v.data_id IN ({marks}) ORDER BY v.property_id",ids)
        for r in cur.fetchall(): records[r.pop('data_id')]['fields'].append(r)
    return [records[i] for i in dict.fromkeys(ids) if i in records]
