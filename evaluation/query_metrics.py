"""Result-set metrics; reference SQL is executed on the same database contents."""
import math

def score(actual,gold,*,success=True,aggregate=False):
    if aggregate:
        exact=success and len(actual)==len(gold)==1 and (actual[0]==gold[0] if actual[0] is None or gold[0] is None else math.isclose(float(actual[0]),float(gold[0]),rel_tol=1e-9,abs_tol=1e-12))
        return dict(ex=int(exact),tp=int(exact),pred_n=len(actual) if success else 0,gold_n=1,precision=float(exact),recall=float(exact),f1=float(exact))
    a=set(actual) if success else set();g=set(gold);tp=len(a&g)
    p=tp/len(a) if a else float(success and not g)
    r=tp/len(g) if g else float(success and not a)
    return dict(ex=int(success and a==g),tp=tp,pred_n=len(a),gold_n=len(g),precision=p,recall=r,f1=2*p*r/(p+r) if p+r else 0.)

def summarize(rows):
    n=len(rows);tp=sum(r['tp'] for r in rows);pred=sum(r['pred_n'] for r in rows);gold=sum(r['gold_n'] for r in rows)
    return dict(n=n,EX=sum(r['ex'] for r in rows)/n,macro_precision=sum(r['precision'] for r in rows)/n,macro_recall=sum(r['recall'] for r in rows)/n,micro_recall=tp/gold if gold else None,macro_f1=sum(r['f1'] for r in rows)/n,micro_precision=tp/pred if pred else None)

if __name__=='__main__':
    assert score([],[],success=False)['ex']==0
    assert score([],[])['ex']==1
    assert score([1,2],[2,3])['f1']==.5
    assert score([2.00000000001],[2],aggregate=True)['ex']==1
    print('Metric checks passed')
