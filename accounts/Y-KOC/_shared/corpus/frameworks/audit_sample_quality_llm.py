from __future__ import annotations

import argparse, json, subprocess
from pathlib import Path


def call_llm(item: dict) -> dict:
    prompt = f"""
你是内容样本审核员。请根据以下候选文章信息进行样本质量审核。
只输出 JSON：
{{
  "rewriteable": "Y|N",
  "hook_strength": 0-5,
  "structure_progression": 0-5,
  "rhythm_reusable": 0-5,
  "quality_note": "一句话"
}}

候选信息：
- title: {item.get('title','')}
- preview: {item.get('preview','')}
- author: @{item.get('author','')}
- url: {item.get('url','')}
- type: {item.get('type_new') or item.get('type_guess')}
""".strip()
    cmd=["openclaw","agent","--json","--session-id","sample-audit","--message",prompt]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=180)
    if p.returncode!=0:
        raise RuntimeError(p.stderr or p.stdout)
    raw=(p.stdout or '').strip()
    s,e=raw.find('{'),raw.rfind('}')
    obj=json.loads(raw[s:e+1])
    txt=((obj.get('payloads') or [{}])[0].get('text') or '').strip()
    s2,e2=txt.find('{'),txt.rfind('}')
    out=json.loads(txt[s2:e2+1])
    return out


def percentile(vals, x):
    if not vals:
        return 0
    arr=sorted(vals)
    k=sum(1 for v in arr if v<=x)
    return round(100*k/len(arr),1)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--in',dest='inp',required=True)
    ap.add_argument('--out',required=True)
    args=ap.parse_args()

    data=json.loads(Path(args.inp).read_text(encoding='utf-8'))
    items=data.get('items',[])
    scores=[float(i.get('score',0) or 0) for i in items]

    audited=[]
    for i,it in enumerate(items,1):
      try:
        a=call_llm(it)
      except Exception as e:
        a={"rewriteable":"N","hook_strength":0,"structure_progression":0,"rhythm_reusable":0,"quality_note":f"fallback:{e}"}
      row=dict(it)
      row['audit']=a
      row['engagement_percentile_30d']=percentile(scores,float(it.get('score',0) or 0))
      row['sample_quality_score']= round(
        (1 if a.get('rewriteable')=='Y' else 0)*2 +
        float(a.get('hook_strength',0))+
        float(a.get('structure_progression',0))+
        float(a.get('rhythm_reusable',0))+
        (row['engagement_percentile_30d']/25),2)
      audited.append(row)
      print(f"[{i}/{len(items)}] {it.get('url')} done")

    # per type standard pool
    by={}
    for r in audited:
      t=r.get('type_new') or r.get('type_guess') or 'unknown'
      by.setdefault(t,[]).append(r)
    standard={}
    for t,arr in by.items():
      arr=sorted(arr,key=lambda x:x['sample_quality_score'],reverse=True)
      standard[t]=arr[:5]

    out={"count":len(audited),"items":audited,"standard_pool":{k:[x['url'] for x in v] for k,v in standard.items()}}
    Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

    md=['# SAMPLE_QUALITY_AUDIT','']
    for t in sorted(standard.keys()):
      md.append(f"## {t}")
      for x in standard[t]:
        md.append(f"- {x['url']} | q={x['sample_quality_score']} | rw={x['audit'].get('rewriteable')} | pctl={x['engagement_percentile_30d']}")
      md.append('')
    Path(args.out).with_suffix('.md').write_text('\n'.join(md),encoding='utf-8')
    print(args.out)
    print(str(Path(args.out).with_suffix('.md')))

if __name__=='__main__':
    main()
