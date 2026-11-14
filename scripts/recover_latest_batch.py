"""Resume only failed slots of an explicitly requested batch; checkpoint each outcome."""
import json
from pathlib import Path
from enrich_library import now,write
from final_review import finalize,ReviewError,article_structure
from generate_batch import generate,persist
ROOT=Path(__file__).resolve().parents[1]

def recover(library,reviews,status,checkpoint=lambda:None):
    existing={x['id']:x for x in library['items']}
    status.update(state='running',stage='recovery',completedAt=None,error=None)
    checkpoint()
    for index,outcome in enumerate(status['outcomes']):
        if outcome.get('eligible'):continue
        old=reviews['items'].get(outcome.get('id'),{})
        try:
            card=old.get('finalVersion')
            if not card:
                card=generate(outcome['category'],[x['title'] for x in library['items']])
            item,audit=finalize(card,allow_card_correction=True)
            # Keep the previous decisions for diagnosis; never discard the failed draft.
            if old:audit['previousAudits']=[*old.get('previousAudits',[]),{k:v for k,v in old.items() if k!='previousAudits'}]
            if audit['eligible']:
                if item['id'] in existing:
                    library['items']=[item if x['id']==item['id'] else x for x in library['items']]
                else:library['items'].append(item)
                existing[item['id']]=item
            else:audit['finalVersion']=item
            reviews['items'][item['id']]=audit
            status['outcomes'][index]={'id':item['id'],'category':outcome['category'],'state':audit['state'],'reasonCode':audit['reasonCode'],'reason':audit['reason'],'eligible':audit['eligible']}
        except ReviewError as error:
            status['outcomes'][index]={**outcome,'state':'review_failed','reasonCode':error.code,'reason':str(error),'eligible':False}
        status['completed']=len(status['outcomes'])
        status['generated']=sum(bool(x.get('id')) for x in status['outcomes'])
        status['reviewed']=sum(reviews['items'].get(x.get('id'),{}).get('completedReviews',0)>0 for x in status['outcomes'])
        status['approved']=sum(x['state']=='approved' for x in status['outcomes'])
        status['reviewFailed']=sum(x['state']=='review_failed' for x in status['outcomes'])
        status['recoveredAt']=now()
        checkpoint()
    status.update(state='completed',stage='done',completedAt=now())
    checkpoint()

def main():
    read=lambda name:json.loads((ROOT/name).read_text())
    status=read('refresh-status.json');request=read('recovery/latest-batch-request.json')
    if status.get('startedAt')!=request['batchStartedAt']:
        raise ValueError('Recovery request does not match the current batch; refusing to touch another batch')
    library=read('library.json');reviews=read('enrichment-review.json')
    by_id={item["id"]:item for item in library["items"]}
    for outcome in status["outcomes"]:
        if outcome.get("id") in request.get("repairArticleIds",[]) and not article_structure(by_id.get(outcome["id"],{}).get("detail","")):
            outcome["eligible"]=False
            outcome["state"]="review_failed"
            audit=reviews["items"].setdefault(outcome["id"],{})
            item=by_id[outcome["id"]]
            earlier=[a.get("finalVersion",{}).get("detail","") for a in audit.get("previousAudits",[])]
            full=[text for text in earlier if article_structure(text)]
            audit["finalVersion"]={**item,"detail":max(full,key=len) if full else item["detail"]}
    def checkpoint():
        write(ROOT/'library.json',library);write(ROOT/'enrichment-review.json',reviews);write(ROOT/'refresh-status.json',status);persist()
    try:recover(library,reviews,status,checkpoint)
    except Exception as error:
        status.update(state='failed',error=str(error)[:300],completedAt=now());checkpoint();raise
if __name__=='__main__':main()
