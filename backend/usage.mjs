// Shared by the coaching Worker and the separate Inspire Worker. No prompts or keys are stored.
export const USAGE_VERSION='mydaycoach-usage-1';
export const USAGE_RATE_VERSION='anthropic-haiku-5-5-2026-11-14';
export const USAGE_FEATURES=['LIFE','CAREER','LEARNING','NEWS','INSPIRE','LOCAL'];
const usageSchema=[
 `CREATE TABLE IF NOT EXISTS ai_usage_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,source TEXT NOT NULL,feature TEXT NOT NULL,purpose TEXT NOT NULL,occurred_at INTEGER NOT NULL,model TEXT NOT NULL,input_tokens INTEGER NOT NULL,output_tokens INTEGER NOT NULL,cache_read INTEGER NOT NULL,cache_write_5m INTEGER NOT NULL,cache_write_1h INTEGER NOT NULL,searches INTEGER NOT NULL,input_nano INTEGER NOT NULL,output_nano INTEGER NOT NULL,other_nano INTEGER NOT NULL,known INTEGER NOT NULL,measured INTEGER NOT NULL,complete INTEGER NOT NULL,rate_version TEXT NOT NULL)`,
 `CREATE INDEX IF NOT EXISTS ai_usage_time ON ai_usage_events(owner,occurred_at,id)`,
 `CREATE TABLE IF NOT EXISTS ai_usage_sources(owner TEXT NOT NULL,source TEXT NOT NULL,started_at INTEGER NOT NULL,last_seen INTEGER NOT NULL,PRIMARY KEY(owner,source))`
];
const usageReady=new WeakMap();
const usageOwner=e=>String(e.USAGE_OWNER_ID||'mydaycoach-owner-v1');
const usageN=n=>Number.isSafeInteger(n)&&n>=0?n:0;
const usageDb=e=>e.LEARNING_DB;
export async function usageEnsure(env,source){
 const db=usageDb(env);if(!db)throw Error('USAGE_DATABASE_NOT_CONFIGURED');
 if(!usageReady.has(db)){const p=(async()=>{for(const q of usageSchema)await db.prepare(q).run()})();usageReady.set(db,p);p.catch(()=>usageReady.delete(db));}
 await usageReady.get(db);
 if(source){const now=Date.now();await db.prepare('INSERT INTO ai_usage_sources(owner,source,started_at,last_seen) VALUES(?,?,?,?) ON CONFLICT(owner,source) DO UPDATE SET last_seen=excluded.last_seen').bind(usageOwner(env),source,now,now).run()}
 return db;
}
// Integer nano-USD avoids rounding tiny per-request charges to zero. Rates are snapshotted per call.
export function usagePrice(raw={},model='claude-haiku-5-5',request={}){
 const base=usageN(raw.input_tokens),read=usageN(raw.cache_read_input_tokens),created=usageN(raw.cache_creation_input_tokens);
 const hour=Math.min(created,usageN(raw.cache_creation?.ephemeral_1h_input_tokens));
 const five=created-hour;const output=usageN(raw.output_tokens),input=base+read+created;
 const searches=usageN(raw.server_tool_use?.web_search_requests),tier=input>100000?5:1;
 const geo=request.inference_geo==='us'?1.1:1;
 const measured=Number.isSafeInteger(raw.input_tokens)&&raw.input_tokens>=0&&Number.isSafeInteger(raw.output_tokens)&&raw.output_tokens>=0;
 const known=/^claude-haiku-5-5(?:-|$)/.test(model)&&!request.speed&&measured;
 return {input,output,cacheRead:read,cacheWrite5m:five,cacheWrite1h:hour,searches,measured,known,
  inputNano:known?Math.round((base*100+read*10+five*125+hour*200)*tier*geo):0,
  outputNano:known?Math.round(output*500*tier*geo):0,otherNano:known?searches*10000000:0,
  rateVersion:USAGE_RATE_VERSION};
}
export async function usageRecord(env,meta,raw,model,request={},complete=true){
 const db=await usageEnsure(env,meta.source),v=usagePrice(raw,model,request);
 const id=meta.id||crypto.randomUUID();
 await db.prepare('INSERT OR IGNORE INTO ai_usage_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').bind(
  meta.source+':'+id,usageOwner(env),meta.source,USAGE_FEATURES.includes(meta.feature)?meta.feature:'LOCAL',
  String(meta.purpose||'api').replace(/[^a-zA-Z0-9_./-]/g,'').slice(0,80),meta.occurredAt||Date.now(),model||'unknown',
  v.input,v.output,v.cacheRead,v.cacheWrite5m,v.cacheWrite1h,v.searches,v.inputNano,v.outputNano,v.otherNano,
  v.known?1:0,v.measured?1:0,complete?1:0,v.rateVersion).run();return v;
}
function usageMerge(a,b){return {...a,...b,...(b?.cache_creation?{cache_creation:{...a?.cache_creation,...b.cache_creation}}:{}),...(b?.server_tool_use?{server_tool_use:{...a?.server_tool_use,...b.server_tool_use}}:{})}}
// Observe the same stream the application consumes; never tee it or keep a cancelled model running.
export function usageFetch(env,feature,purpose,fetcher=fetch,source='coach'){
 if(!usageDb(env))return fetcher;
 return async(url,options={})=>{
  const path=String(url);if(!/^https:\/\/api\.anthropic\.com\/v1\/messages\/?$/.test(path))return fetcher(url,options);
  let request={};try{request=JSON.parse(options.body||'{}')}catch{}
  const meta={source,feature,purpose,occurredAt:Date.now()},fallbackId=crypto.randomUUID();
  let response;try{response=await fetcher(url,options)}catch(error){await usageRecord(env,{...meta,id:fallbackId},{},request.model,request,false).catch(()=>console.error('usage_record_failed'));throw error}
  meta.id=response.headers.get('request-id')||fallbackId;
  const save=(raw,model,done)=>usageRecord(env,meta,raw,model||request.model,request,done).catch(()=>{console.error('usage_record_failed');return null});
  if(!request.stream||!response.ok||!response.body){
   let parsed;try{parsed=await response.clone().json()}catch{}
   // Provider-side 4xx requests with no usage are not billed. Network/5xx missing usage stays visible as unknown.
   if(response.status>=400&&response.status<500&&!parsed?.usage)return response;
   await save(parsed?.usage||{},parsed?.model,response.ok);return response;
  }
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',raw={},model=request.model,finished=false,saved=false;
  const finish=async()=>{if(saved)return;saved=true;await save(raw,model,finished)};
  function observe(chunk,done=false){buffer=(buffer+decoder.decode(chunk||new Uint8Array(),{stream:!done})).replace(/\r\n/g,'\n');let i;while((i=buffer.indexOf('\n\n'))>=0){const frame=buffer.slice(0,i);buffer=buffer.slice(i+2);const text=frame.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trimStart()).join('\n');try{const e=JSON.parse(text);if(e.type==='message_start'){raw=usageMerge(raw,e.message?.usage||{});model=e.message?.model||model}if(e.type==='message_delta')raw=usageMerge(raw,e.usage||{});if(e.type==='message_stop')finished=true}catch{}}if(buffer.length>2000000)buffer='';}
  const body=new ReadableStream({async pull(controller){try{const r=await reader.read();observe(r.value,r.done);if(r.done){await finish();controller.close()}else controller.enqueue(r.value)}catch(error){await finish();controller.error(error)}},async cancel(reason){try{await reader.cancel(reason)}finally{await finish()}}});
  return new Response(body,{status:response.status,statusText:response.statusText,headers:response.headers});
 };
}
const usageJson=(j,status=200)=>new Response(JSON.stringify(j),{status,headers:{'content-type':'application/json','cache-control':'no-store'}});
function usageDate(s){if(!/^\d{4}-\d{2}-\d{2}$/.test(s||''))throw Error('INVALID_DATE');const d=new Date(s+'T00:00:00Z');if(!Number.isFinite(+d)||d.toISOString().slice(0,10)!==s)throw Error('INVALID_DATE');return s}
const usageDateFormatters=new Map();
export function usageDay(ms,tz){if(!usageDateFormatters.has(tz)){if(usageDateFormatters.size>=32)usageDateFormatters.delete(usageDateFormatters.keys().next().value);usageDateFormatters.set(tz,new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}))}const p=usageDateFormatters.get(tz).formatToParts(new Date(ms));return ['year','month','day'].map(k=>p.find(x=>x.type===k).value).join('-')}
export function usageWeek(day){const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7);return d.toISOString().slice(0,10)}
function usageEmpty(feature){return {feature,calls:0,inputTokens:0,outputTokens:0,cacheRead:0,cacheWrite5m:0,cacheWrite1h:0,searches:0,inputNano:0,outputNano:0,otherNano:0,totalNano:0,unmeasuredCalls:0,unpricedCalls:0,partialCalls:0}}
function usageAdd(a,b){for(const k of Object.keys(a))if(k!=='feature'&&typeof a[k]==='number')a[k]+=b[k]||0;return a}
export async function usageSummary(request,env){
 try{
 const u=new URL(request.url),tz=u.searchParams.get('tz')||'UTC';try{usageDay(Date.now(),tz)}catch{throw Error('INVALID_TIME_ZONE')}
 const start=u.searchParams.get('start')?usageDate(u.searchParams.get('start')):null,end=u.searchParams.get('end')?usageDate(u.searchParams.get('end')):usageDay(Date.now(),tz);
 if(start&&start>end)throw Error('INVALID_DATE_RANGE');const group=u.searchParams.get('group')||'daily';if(!['daily','weekly'].includes(group))throw Error('INVALID_GROUP');
 const f=u.searchParams.has('features')?u.searchParams.get('features').split(',').filter(Boolean):USAGE_FEATURES;const selected=[...new Set(f)];if(selected.some(x=>!USAGE_FEATURES.includes(x)))throw Error('INVALID_FEATURE');
 const db=await usageEnsure(env,'coach'),sources=(await db.prepare('SELECT source,started_at,last_seen FROM ai_usage_sources WHERE owner=? ORDER BY source').bind(usageOwner(env)).all()).results||[];
 const lower=start?Date.parse(start+'T00:00:00Z')-86400000:0,upper=Date.parse(end+'T00:00:00Z')+172800000;
 const byFeature=Object.fromEntries(selected.map(x=>[x,usageEmpty(x)])),byDay=new Map();let cursorTime=lower-1,cursorId='',page;
 do{page=(await db.prepare('SELECT * FROM ai_usage_events WHERE owner=? AND occurred_at>=? AND occurred_at<? AND (occurred_at>? OR (occurred_at=? AND id>?)) ORDER BY occurred_at,id LIMIT 1000').bind(usageOwner(env),lower,upper,cursorTime,cursorTime,cursorId).all()).results||[];
 for(const r of page){cursorTime=r.occurred_at;cursorId=r.id;if(!selected.includes(r.feature))continue;const day=usageDay(r.occurred_at,tz);if(start&&day<start||day>end)continue;
 const v={...usageEmpty(r.feature),calls:1,inputTokens:r.input_tokens,outputTokens:r.output_tokens,cacheRead:r.cache_read,cacheWrite5m:r.cache_write_5m,cacheWrite1h:r.cache_write_1h,searches:r.searches,inputNano:r.input_nano,outputNano:r.output_nano,otherNano:r.other_nano,totalNano:r.input_nano+r.output_nano+r.other_nano,unmeasuredCalls:r.measured?0:1,unpricedCalls:r.known?0:1,partialCalls:r.complete?0:1};
 usageAdd(byFeature[r.feature],v);const key=group==='weekly'?usageWeek(day):day;if(!byDay.has(key))byDay.set(key,{day:key,...usageEmpty('ALL')});usageAdd(byDay.get(key),v);
 }
 }while(page.length===1000);
 const total=Object.values(byFeature).reduce(usageAdd,usageEmpty('ALL'));
 const first=await db.prepare('SELECT MIN(occurred_at) AS first FROM ai_usage_events WHERE owner=?').bind(usageOwner(env)).first();
 return usageJson({version:USAGE_VERSION,currency:'USD',estimated:true,rateVersion:USAGE_RATE_VERSION,rateSource:'https://platform.claude.com/docs/en/models/haiku-5-5/overview',searchRateSource:'https://platform.claude.com/docs/en/about-claude/pricing',updatedAt:Date.now(),start:start||(first?.first?usageDay(first.first,tz):null),end,timezone:tz,group,features:selected,total,byFeature:Object.values(byFeature),series:[...byDay.values()].sort((a,b)=>a.day.localeCompare(b.day)),coverage:{sources,trackingSince:sources.length?Math.min(...sources.map(s=>s.started_at)):null,historyComplete:false,inspireSeen:sources.some(s=>s.source==='inspire'),note:'Recorded calls only. Unavailable historical usage is not reconstructed. Infrastructure bills are separate.'}});
 }catch(error){const code=String(error.message);return usageJson({error:code.startsWith('INVALID_')?code:code==='USAGE_DATABASE_NOT_CONFIGURED'?code:'USAGE_STORAGE_UNAVAILABLE'},code.startsWith('INVALID_')?400:503)}
}
export async function usageHealth(env,source){try{await usageEnsure(env,source);return {usageVersion:USAGE_VERSION,usageStorageReady:true}}catch{return {usageVersion:USAGE_VERSION,usageStorageReady:false}}}
