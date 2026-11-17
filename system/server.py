"""Local browser interface and JSON API."""
import argparse
import json
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
from .service import connect, pending, upload, review, query, full_rows, parse

PAGE="""<!doctype html><meta charset=utf-8><title>Mat-SIR</title><style>body{font:16px system-ui;max-width:900px;margin:5vh auto;padding:20px}section{padding:16px 0;border-top:1px solid #ddd}input,button{padding:8px}#q{width:65%}pre{white-space:pre-wrap;background:#f4f6f7;padding:16px}</style>
<h1>Mat-SIR 材料数据库</h1><section><h2>上传材料记录</h2><input type=file id=f accept=".json"><button id=u>导入 JSON</button></section>
<section><h2>查询材料</h2><input id=q value="tensile_strength > 500 MPa AND yield_strength > 300 MPa"><button id=i>预览 SIR</button> <button id=b>查询</button> <button id=h hidden>查看命中记录明细</button></section>
<section><h2>审核未匹配字段</h2><button id=p>查看待审记录</button><p><input id=e placeholder="实体 ID"><input id=n placeholder="原字段"><input id=k placeholder="标准属性"><input id=d placeholder="属性描述"><button id=a>确认映射</button></p></section><pre id=o></pre>
<script>let hits=[];async function call(path,data){try{let resp=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});let result=await resp.json();o.textContent=JSON.stringify(result,null,2);return result}catch(err){o.textContent=String(err)}}
u.onclick=async()=>{try{await call('/upload',JSON.parse(await f.files[0].text()))}catch(err){o.textContent=String(err)}};
i.onclick=()=>call('/api/intent/parse',{question:q.value});b.onclick=async()=>{h.hidden=true;const result=await call('/query',{question:q.value});hits=(result?.records||[]).map(r=>r.id);h.hidden=!hits.length};h.onclick=()=>call('/api/datasets/full_rows',{id_list:hits.slice(0,500)});p.onclick=()=>call('/pending',{});a.onclick=()=>call('/review',{entity_id:Number(e.value),field:n.value,property:k.value,description:d.value});</script>"""

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--online',action='store_true')
    args=parser.parse_args()
    from .mysql_import import initialize
    initialize()
    class Handler(BaseHTTPRequestHandler):
        def reply(self,code,body,kind):
            self.send_response(code);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body)
        def do_GET(self):
            self.reply(200,PAGE.encode(),'text/html; charset=utf-8') if self.path=='/' else self.send_error(404)
        def do_POST(self):
            try:
                if self.headers.get_content_type()!='application/json':raise ValueError('Expected application/json')
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<=32*1024*1024: raise ValueError('Invalid request size')
                payload=json.loads(self.rfile.read(size))
                with closing(connect()) as db:
                    if self.path=='/upload':result=upload(db,payload,args.online)
                    elif self.path=='/query':result=query(db,payload['question'],args.online)
                    elif self.path=='/review':result=review(db,payload)
                    elif self.path=='/api/intent/parse':result={'sir':parse(payload['question'],db,args.online)}
                    elif self.path=='/api/datasets/full_rows':result={'success':True,'data':full_rows(db,payload['id_list'])}
                    elif self.path=='/pending':result=pending(db)
                    else:return self.send_error(404)
                code=200
            except Exception as exc:
                code=400;result={'error':str(exc)}
            self.reply(code,json.dumps(result,ensure_ascii=False).encode(),'application/json; charset=utf-8')
    HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__=='__main__':main()
