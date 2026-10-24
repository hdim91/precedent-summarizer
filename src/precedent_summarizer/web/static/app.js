/* All offsets are Python Unicode code points, NOT JavaScript UTF-16 indices.
 splitByRanges('가😀나다', [{start:1,end:3}]) =>
 [{text:'가',highlight:false,start:0,end:1},
  {text:'😀나',highlight:true,start:1,end:3},
  {text:'다',highlight:false,start:3,end:4}].
 Overlapping/adjacent ranges merge; invalid and null offsets are ignored.
 Joining every returned text always reproduces the original exactly. */
function splitByRanges(text, ranges) {
  const chars = Array.from(text);
  const valid = ranges.filter(r => Number.isInteger(r.start) && Number.isInteger(r.end) &&
    r.start >= 0 && r.end > r.start && r.end <= chars.length).map(r => ({start:r.start,end:r.end})).sort((a,b)=>a.start-b.start);
  const merged = [];
  for (const r of valid) {
    const last = merged[merged.length-1];
    if (last && r.start <= last.end) last.end = Math.max(last.end,r.end);
    else merged.push(r);
  }
  const result = []; let at=0;
  function part(start,end,highlight) {if(end>start) result.push({text:chars.slice(start,end).join(''),highlight,start,end});}
  for(const r of merged) {part(at,r.start,false);part(r.start,r.end,true);at=r.end;}
  part(at,chars.length,false);
  return result;
}
// Evidence follows the same block order as the summary renderer, not API order.
function evidenceDisplayOrder(summary, ranges) {
  const paths=[];
  if(summary.disposition)paths.push('disposition');
  for(const [i] of (summary.rulings||[]).entries())paths.push('rulings['+i+']');
  if(summary.facts)paths.push('facts');
  if(summary.lower_court)paths.push('lower_court');
  for(const key of ['cited_statutes','cited_precedents','separate_opinions'])
    for(const [i] of (summary[key]||[]).entries())paths.push(key+'['+i+']');
  return paths.flatMap(path=>ranges.map((r,index)=>({r,index}))
    .filter(({r})=>r.path.startsWith(path+'.evidence['))
    .sort((a,b)=>Number(a.r.path.match(/\[(\d+)\]$/)?.[1]||0)-Number(b.r.path.match(/\[(\d+)\]$/)?.[1]||0))
    .map(({index})=>index));
}
// Offsets use code points. displayOrder contains API span indices in visible order.
// minimapPositions('가😀나다',[{start:1,end:3}],[0]) =>
// [{index:0,number:1,start:1,end:3,percent:25}]. Null positions keep their display number
// reserved, but do not create a minimap dot.
function minimapPositions(text, ranges, displayOrder=ranges.map((_,index)=>index)) {
  const length=Array.from(text).length;
  if(!length)return [];
  return displayOrder.flatMap((index,position)=>{
    const r=ranges[index];
    return r && Number.isInteger(r.start) && Number.isInteger(r.end) &&
      r.start>=0 && r.end>r.start && r.end<=length
      ? [{index,number:position+1,start:r.start,end:r.end,percent:100*r.start/length}] : [];
  });
}
function courtDigestSections(data) {
  return [['holdings_clean','판시사항'],['official_summary_clean','판결요지']]
    .filter(([field])=>typeof data[field]==='string' && data[field].trim())
    .map(([field,title])=>({field,title,text:data[field]}));
}
if(typeof module !== 'undefined')module.exports={splitByRanges,minimapPositions,evidenceDisplayOrder,courtDigestSections};

if(typeof document !== 'undefined') {
  const $ = id=>document.getElementById(id);
  const el = (tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;return n;};
  const badge = (text,cls='')=>el('span',text,'badge '+cls);
  const modelName = model=>/opus/i.test(model||'')?'Opus':/sonnet/i.test(model||'')?'Sonnet':(model||'요약 없음');
  const labels = {v1:'v1 · 블라인드',v1o:'v1o · 판결요지 참고'};
  async function api(url,signal) {const response=await fetch(url,{signal,headers:{Accept:'application/json'}});if(!response.ok)throw new Error(response.status===404?'해당 판례 또는 요약을 찾을 수 없습니다.':'자료를 불러오지 못했습니다. 잠시 후 다시 시도하세요.');return response.json();}
  function error(node,err){node.hidden=false;node.replaceChildren(el('p',err.message));const retry=el('button','다시 불러오기');retry.type='button';retry.addEventListener('click',()=>location.reload());node.append(retry);}
  function skeleton(node,lines=3){node.replaceChildren();for(let i=0;i<lines;i++)node.append(el('span',null,'skeleton'+(i===lines-1?' short':'')));}
  const evidenceNumber = n=>n<=20?String.fromCodePoint(0x2460+n-1):String(n);
  function dispositionClass(type){return /각하/.test(type)?'dismissed':/파기자판/.test(type)?'reversed-final':/파기|인용/.test(type)?'reversed':/기각/.test(type)?'affirmed':'other';}

  function dateCell(p){const n=el('span',p.decision_date||p.decision_date_inferred||'날짜 미상');if(!p.decision_date&&p.decision_date_inferred)n.append(' ',badge('추정'));return n;}
  const form=$('search-form');
  if(form){
    let controller;
    const keys=['q','year_from','year_to','case_type','data_source','has_summary','version'];
    function hydrate(){
      const p=new URLSearchParams(location.search);
      for(const k of keys)form.elements[k].value=p.get(k)||(k==='version'?'v1':'');
      const active=keys.filter(k=>k!=='q' && p.get(k) && !(k==='version'&&p.get(k)==='v1'));
      form.querySelector('.filter-panel').open=active.length>0;
      const chips=$('active-filters');chips.replaceChildren();
      const names={year_from:'선고연도부터',year_to:'선고연도까지',case_type:'사건종류',data_source:'출처',has_summary:'요약',version:'버전'};
      for(const k of active){
        const value=k==='has_summary'?(p.get(k)==='true'?'있음':'없음'):k==='version'?(labels[p.get(k)]||p.get(k)):p.get(k);
        const chip=el('button',names[k]+': '+value+' ×','filter-chip');chip.type='button';
        chip.setAttribute('aria-label',names[k]+' 필터 해제');chip.addEventListener('click',()=>{const next=new URLSearchParams(location.search);next.delete(k);next.set('page','1');history.pushState(null,'','/?'+next);listing();});chips.append(chip);
      }
      chips.hidden=!active.length;
    }
    async function listing(){
      hydrate();if(controller)controller.abort();controller=new AbortController();const currentController=controller;
      const p=new URLSearchParams(location.search);for(const key of [...p.keys()])if(!keys.includes(key)&&key!=='page')p.delete(key);
      p.set('size','20');if(!p.has('version'))p.set('version','v1');
      $('list-error').hidden=true;$('result-count').textContent='불러오는 중';$('results-body').setAttribute('aria-busy','true');const loadingRow=el('tr');const loadingCell=el('td');loadingCell.colSpan=7;skeleton(loadingCell);loadingRow.append(loadingCell);$('results-body').replaceChildren(loadingRow);
      try{
        const data=await api('/api/precedents?'+p,currentController.signal);
        const rows=[];
        for(const item of data.items){
          const tr=el('tr');const columns=['선고일','사건번호','사건명','사건종류','출처','요약 상태','한 줄 요약'];let column=0;const td=()=>{const n=el('td');n.dataset.label=columns[column++];tr.append(n);return n;};
          td().append(dateCell(item));td().textContent=item.case_no||'사건번호 없음';
          const a=el('a',item.case_name||'사건명 없음');a.href='/precedents/'+encodeURIComponent(item.prec_id)+'?'+new URLSearchParams({return:location.search});td().append(a);
          td().textContent=item.case_type_name||'—';td().textContent=item.data_source||'—';
          const status=td();status.append(item.summary_model?badge(modelName(item.summary_model),/opus/i.test(item.summary_model)?'opus':'sonnet'):el('span','요약 없음','muted'));
          if(item.detail_status==='unavailable')status.append(el('div','본문 미제공 ('+(item.data_source||'출처 미상')+')','unavailable'));
          const excerpt=el('span',item.one_line||'—','summary-excerpt');td().append(excerpt);rows.push(tr);
        }
        if(!rows.length){const tr=el('tr');const cell=el('td','검색 결과가 없습니다. 검색어나 필터를 바꿔보세요.','empty');cell.colSpan=7;tr.append(cell);rows.push(tr);}
        $('results-body').replaceChildren(...rows);$('result-count').textContent='총 '+data.total.toLocaleString('ko-KR')+'건';
        const nav=$('pagination');nav.replaceChildren();const pages=Math.max(1,Math.ceil(data.total/20));
        function link(page,text,current=false){const a=el('a',text);const next=new URLSearchParams(location.search);next.set('page',String(page));a.href='/?'+next;if(current)a.setAttribute('aria-current','page');a.addEventListener('click',event=>{if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;event.preventDefault();history.pushState(null,'',a.href);listing();});nav.append(a);}
        if(data.page>1)link(data.page-1,'이전');
        for(let i=Math.max(1,data.page-2);i<=Math.min(pages,data.page+2);i++)link(i,String(i),i===data.page);
        if(data.page<pages)link(data.page+1,'다음');
      }catch(err){if(err.name!=='AbortError'){error($('list-error'),err);$('result-count').textContent='조회 실패';$('results-body').replaceChildren();$('pagination').replaceChildren();}}
      finally{if(!currentController.signal.aborted)$('results-body').removeAttribute('aria-busy');}
    }
    form.addEventListener('submit',event=>{event.preventDefault();const p=new URLSearchParams();for(const k of keys){const value=form.elements[k].value.trim();if(value)p.set(k,value);}p.set('page','1');history.pushState(null,'','/?'+p);listing();});
    window.addEventListener('popstate',listing);
    // Keep URL-selected sources available before asynchronous stats arrive.
    const selectedSource=new URLSearchParams(location.search).get('data_source');
    if(selectedSource){const o=el('option',selectedSource);o.value=selectedSource;$('data_source').append(o);}
    api('/api/stats').then(data=>{
      const box=$('stats');box.replaceChildren();
      function stat(label,value){const n=el('div',null,'stat');n.append(el('strong',value.toLocaleString('ko-KR')),el('span',label));box.append(n);}
      stat('전체 판례',Object.values(data.precedents).reduce((a,b)=>a+b,0));stat('본문 보유',data.precedents.ok||0);
      if(!data.summaries.length)stat('요약',0);
      for(const s of data.summaries)stat((labels[s.version]||s.version)+' · '+modelName(s.model),s.n);
      for(const source of Object.keys(data.by_source).sort()){if([...$('data_source').options].some(o=>o.value===source))continue;const o=el('option',source);o.value=source;$('data_source').append(o);}
    }).catch(err=>{$('stats').textContent='통계를 불러오지 못했습니다. 검색은 계속 사용할 수 있습니다.';});
    listing();
  }
  const detail=$('detail-page');
  if(detail){
    let text='',spans=[],displayOrder=[],requestNumber=0;
    const buttons=[];
    const returnQuery=new URLSearchParams(location.search).get('return');
    if(returnQuery&&returnQuery.startsWith('?'))$('back-link').href='/'+returnQuery;
    const original=$('original-text');skeleton(original,8);skeleton($('summary-content'),5);
    function paint(ranges){original.replaceChildren(...splitByRanges(text,ranges).map(part=>part.highlight?el('mark',part.text):document.createTextNode(part.text)));}
    function focusRange(span){
      const valid=splitByRanges(text,[span]).some(p=>p.highlight);
      if(!valid){$('evidence-status').textContent='원문 위치 미확인';return;}
      paint([span]);const mark=original.querySelector('mark');
      if(mark){mark.tabIndex=-1;mark.focus({preventScroll:true});mark.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
    }
    function selectEvidence(s,button){buttons.forEach(n=>n.setAttribute('aria-pressed','false'));if(button)button.setAttribute('aria-pressed','true');$('evidence-status').textContent=s.quote;focusRange(s);}
    function minimap(){
      const rail=$('evidence-minimap');rail.replaceChildren();
      for(const point of minimapPositions(text,spans,displayOrder)){
        const s=spans[point.index];const number=evidenceNumber(point.number);
        const b=el('button',null,'minimap-dot');b.type='button';b.style.top=point.percent+'%';
        b.title=number+' '+s.quote;b.setAttribute('aria-label','근거 '+point.number+': '+s.quote);
        b.setAttribute('aria-pressed','false');b.addEventListener('click',()=>selectEvidence(s,b));buttons.push(b);rail.append(b);
      }
      rail.hidden=!rail.children.length;
    }
    $('clear-highlight').addEventListener('click',()=>{paint([]);buttons.forEach(b=>b.setAttribute('aria-pressed','false'));$('evidence-status').textContent='강조를 해제했습니다.';});
    function evidence(parent,path){
      const found=displayOrder.map(index=>spans[index]).filter(s=>s.path.startsWith(path+'.evidence['));
      for(let i=0;i<found.length;i++){
        const s=found[i],number=displayOrder.indexOf(spans.indexOf(s))+1,b=el('button',evidenceNumber(number),'evidence-button');b.type='button';b.title=s.quote;b.setAttribute('aria-pressed','false');
        if(s.start===null||s.end===null){parent.append(el('span',evidenceNumber(number)+' 원문 위치 미확인','small muted'));continue;}
        b.setAttribute('aria-label','근거 '+number+': '+s.quote);
        b.addEventListener('click',()=>selectEvidence(s,b));buttons.push(b);parent.append(b);
      }
    }
    async function summary(version){
      const ticket=++requestNumber;const box=$('summary-content');skeleton(box,5);spans=[];displayOrder=[];buttons.length=0;minimap();$('case-disposition').replaceChildren();paint([]);
      for(const tab of $('summary-tabs').children){const selected=tab.dataset.version===version;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;}
      box.setAttribute('aria-labelledby','tab-'+version);
      try{
        const data=await api('/api/precedents/'+encodeURIComponent(detail.dataset.precId)+'/summary/'+encodeURIComponent(version));if(ticket!==requestNumber)return;
        spans=data.evidence_spans||[];const s=data.summary;displayOrder=evidenceDisplayOrder(s,spans);buttons.length=0;minimap();box.replaceChildren();
        const verify=data.verify||{};const v=el('div',null,'verification');
        const order={match:'일치',mismatch:'불일치',no_order_section:'주문 구획 없음',unknown_type:'유형 미확인'};
        v.append(badge(verify.passed===true?'✓ 검증 통과':verify.passed===false?'! 검증 미통과':'검증 정보 없음',verify.passed===true?'verified':verify.passed===false?'unverified':''),badge('인용 '+(verify.evidence_found??'—')+'/'+(verify.evidence_total??'—'),'seal'),badge('주문 '+(order[verify.disposition_check]||verify.disposition_check||'정보 없음'),'seal'),badge(modelName(data.model),/opus/i.test(data.model)?'opus':'sonnet'));box.append(v);
        box.append(el('p',s.one_line,'summary-lead'));
        function block(title,body,path){const n=el('section',null,'summary-block');n.append(el('h3',title));for(const line of body)if(line)n.append(el('p',line));if(path)evidence(n,path);box.append(n);return n;}
        if(s.disposition){const n=block('결론',[s.disposition.text],'disposition');n.insertBefore(badge(s.disposition.type,dispositionClass(s.disposition.type)),n.children[1]||null);$('case-disposition').replaceChildren(badge(s.disposition.type,dispositionClass(s.disposition.type)));}
        const issues=s.issues||[];
        for(const [i,r] of (s.rulings||[]).entries()){const issue=issues.find(x=>x.id===r.issue_id);block('쟁점 '+(i+1)+' · '+(issue?.question||r.issue_id),['판단: '+r.conclusion,'이유: '+r.reasoning],'rulings['+i+']');}
        if(!(s.rulings||[]).length&&issues.length)block('쟁점',issues.map(i=>i.question));
        if(s.facts)block('사실관계',[s.facts.summary],'facts');
        if(s.lower_court)block('원심 판단',[s.lower_court.summary],'lower_court');
        for(const [i,c] of (s.cited_statutes||[]).entries())block('인용 조문',[c.statute],'cited_statutes['+i+']');
        for(const [i,c] of (s.cited_precedents||[]).entries())block('인용 판례',[c.case_no],'cited_precedents['+i+']');
        for(const [i,c] of (s.separate_opinions||[]).entries())block(c.kind,[c.summary],'separate_opinions['+i+']');
        if((s.not_in_text||[]).length)block('원문에 없는 정보',s.not_in_text);
      }catch(err){if(ticket===requestNumber)error(box,err);}
    }
    api('/api/precedents/'+encodeURIComponent(detail.dataset.precId)).then(data=>{
      text=data.full_text_clean||'';paint([]);if(!text)original.textContent=data.detail_status==='unavailable'?'본문 미제공 ('+(data.data_source||'출처 미상')+')':'수록된 본문이 없습니다.';
      $('case-number').textContent=data.case_no||'사건번호 없음';$('case-title').textContent=data.case_name||'사건명 없음';document.title=(data.case_no||'판례')+' · 판례 연구실';
      const meta=$('case-meta');
      for(const [key,value] of [['사건번호',data.case_no],['법원',data.court_name],['선고일',null],['사건종류',data.case_type_name],['출처',data.data_source]]){const n=el('div');n.append(el('dt',key));const dd=el('dd',value||'—');if(key==='선고일')dd.replaceChildren(dateCell(data));n.append(dd);meta.append(n);}
      for(const section of data.sections||[]){const b=el('button','【'+section.header+'】');b.type='button';b.addEventListener('click',()=>{buttons.forEach(n=>n.setAttribute('aria-pressed','false'));$('evidence-status').textContent='원문 구획: '+section.header;focusRange({start:section.start,end:section.end});});$('section-nav').append(b);}
      const versions=(data.summaries||[]).filter(s=>['v1','v1o'].includes(s.version));
      const digest=versions.length?[]:courtDigestSections(data);
      for(const [field,label] of [['holdings_clean','판시사항'],['official_summary_clean','판결요지 (법원 작성)'],['ref_statutes_clean','참조조문'],['ref_precedents_clean','참조판례']]){if(digest.some(item=>item.field===field))continue;const n=el('details');const heading=el('summary',label);heading.append(badge('법원 작성','court-label'));n.append(heading,el('pre',data[field]||'수록된 내용 없음'));$('court-materials').append(n);}
      for(const s of versions){const b=el('button',labels[s.version]);b.type='button';b.id='tab-'+s.version;b.dataset.version=s.version;b.setAttribute('role','tab');b.setAttribute('aria-controls','summary-content');b.addEventListener('click',()=>summary(s.version));b.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const tabs=[...$('summary-tabs').children];const i=tabs.indexOf(b);const next=event.key==='Home'?tabs[0]:event.key==='End'?tabs.at(-1):tabs[(i+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length];next.focus();next.click();});$('summary-tabs').append(b);}
      if(versions.length)summary(versions[0].version);
      else {
        $('summary-tabs').hidden=true;$('summary-panel').querySelector('.panel-heading .muted').hidden=true;const box=$('summary-content');box.removeAttribute('role');
        box.replaceChildren();
        if(digest.length){
          $('summary-title').replaceChildren(el('small','COURT DIGEST'),document.createTextNode('법원 작성 요지'));
          box.append(el('p','법원 작성 요지 · 자동 요약 아님','court-digest-label'));
          for(const item of digest){const section=el('section',null,'summary-block court-digest');section.append(el('h3',item.title),el('p',item.text));box.append(section);}
        }else{
          const card=el('div',null,'waiting-card');card.append(el('h3','요약 대기 중 — 원문을 확인하세요'),el('p','자동 요약과 법원 작성 요지가 아직 수록되지 않았습니다. 판결 원문과 참조 자료를 확인하세요.'));box.append(card);
        }
      }
    }).catch(err=>{error($('detail-error'),err);$('case-title').textContent='판례를 불러올 수 없습니다.';$('summary-content').textContent='요약을 확인할 수 없습니다.';});
  }
}
