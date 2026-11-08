/**
 * Cloudflare Worker: authenticated start endpoint for GitHub Actions generation.
 * Set secrets: APP_REFRESH_TOKEN, GITHUB_DISPATCH_TOKEN.
 * Set vars: ALLOWED_ORIGIN (optional; native Android ignores CORS).
 * Deploy with wrangler deploy. Never ship these secrets in an APK.
 */
const REPO="jay-ds-labs/mydaycoach-inspirations";
const WORKFLOW="generate-inspirations.yml";
function json(data,status=200){return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json","cache-control":"no-store"}})}
async function githubFile(env,file){
 const response=await fetch("https://api.github.com/repos/"+REPO+"/contents/"+file+"?ref=main",{
  headers:{"Authorization":"Bearer "+env.GITHUB_DISPATCH_TOKEN,"Accept":"application/vnd.github.raw+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"MyDayCoach-Content-Backend","Cache-Control":"no-cache"}
 });
 if(!response.ok)throw Error("GitHub status HTTP "+response.status);
 let data=await response.json();
 if(data && data.encoding==="base64" && typeof data.content==="string"){
  data=JSON.parse(atob(data.content.replace(/\s/g,"")));
 }
 return data;
}
async function latestStatus(env){
 const data=await githubFile(env,"refresh-status.json");
 if(!data || typeof data.state!=="string" || !Number.isInteger(data.completed))throw Error("Invalid generation status");
 return data;
}
function safeEqual(a,b){if(!a||!b||a.length!==b.length)return false;let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);return diff===0}
export default {
 async fetch(request,env){
  const url=new URL(request.url);
  if(url.pathname==="/health" && request.method==="GET")return json({ok:true,service:"mydaycoach-inspire"});
  if(!((url.pathname==="/start" && request.method==="POST") || ((url.pathname==="/status" || url.pathname==="/feed") && request.method==="GET")))return json({error:"Not found"},404);
  if(!env.APP_REFRESH_TOKEN)return json({error:"Server authentication is not configured"},503);
  const auth=request.headers.get("authorization")||"";
  if(!safeEqual(auth,"Bearer "+env.APP_REFRESH_TOKEN))return json({error:"Unauthorized"},401);
  if(!env.GITHUB_DISPATCH_TOKEN)return json({error:"Server is not configured"},503);
  if(url.pathname==="/status"){
   try{return json(await latestStatus(env));}
   catch(error){return json({error:"Unable to read live generation status"},502);}
  }
  if(url.pathname==="/feed"){
   try{
    const feed=await githubFile(env,"library.json");
    if(feed.schemaVersion!==1 || !Array.isArray(feed.items))throw Error("Invalid feed");
    return json(feed);
   }catch(_){return json({error:"Unable to read inspiration feed"},502);}
  }
  // Do not dispatch another job while an active batch is still running.
  try{
   const state=await latestStatus(env);
   if(state.state==="running"){
    const started=Date.parse(state.startedAt||"");
    if(Number.isFinite(started) && Date.now()-started<4*60*60*1000)
     return json({state:"running",message:"Generation already running"},200);
   }
  }catch(_){}
  const response=await fetch("https://api.github.com/repos/"+REPO+"/actions/workflows/"+WORKFLOW+"/dispatches",{
   method:"POST",
   headers:{"Authorization":"Bearer "+env.GITHUB_DISPATCH_TOKEN,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"MyDayCoach-Content-Backend","Content-Type":"application/json"},
   body:JSON.stringify({ref:"main"})
  });
  if(response.status!==204)return json({error:"Could not start generation",githubStatus:response.status},502);
  return json({state:"queued",total:15,message:"Content generation queued"},202);
 }
};
