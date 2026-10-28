import fs from 'node:fs';
const output = {checked_at:new Date().toISOString(), target:'wr0789', method:'XActions guest', status:'unverified', complete:false, posts:[], errors:[]};
try {
  const {Scraper} = await import('xactions/client');
  const x = new Scraper();
  const p = await x.getProfile('wr0789');
  output.profile = {username:p?.username||'wr0789', id:p?.id||null, name:p?.name||null};
  let n=0;
  for await (const t of x.getTweets('wr0789', 20)) {
    if (n++ >= 20) break;
    const id=String(t.id||t.tweetId||'');
    output.posts.push({id, url:id ? 'https://x.com/wr0789/status/'+id:null, created_at:t.timeParsed||t.timestamp||t.createdAt||null, excerpt:String(t.text||'').slice(0,120)});
  }

  // Control account helps distinguish target-specific failure from guest timeline outage.
  try {
    const control = new Scraper();
    let controlCount = 0;
    for await (const t of control.getTweets('NASA', 3)) {
      if (++controlCount >= 3) break;
    }
    output.control_account = {username:'NASA', tweets_received:controlCount};
  } catch (controlErr) {
    output.control_account = {username:'NASA', error_name:controlErr?.name || 'Error', error_message:String(controlErr?.message||controlErr).slice(0,150)};
  }
  output.status = output.posts.length?'partial_guest_data':'empty_or_blocked';
  output.message = output.posts.length?'Guest timeline returned data, replies/completeness not verified.':'Zero posts received. This does NOT establish that the account did not post.';
} catch(err) {
  output.status='guest_error';
  output.errors.push({name:err?.name||'Error',message:String(err?.message||err).slice(0,220)});
}
fs.mkdirSync('state',{recursive:true});
fs.writeFileSync('state/guest-probe.json', JSON.stringify(output,null,2)+'\n');
console.log('GUEST_PROBE',output.status,'posts',output.posts.length,'errors',output.errors.map(e=>e.name));
