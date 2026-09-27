const $ = id => document.getElementById(id);
let busy = false, lastResult = null;
let serverConfig = null;
const status = (message, error = false) => { $('status').textContent = message; $('status').className = error ? 'error' : ''; };
function lock(value) { busy = value; for (const el of $('form').querySelectorAll('input,textarea,select,button')) el.disabled = value; for (const id of ['sample','reset']) $(id).disabled=value; $('analyze').textContent = value ? '처리 중입니다…' : '내 경험과 공고 비교하기 →'; }
async function post(path, data) { const r = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}); const body = await r.json(); if (!r.ok) throw new Error(body.error || '요청에 실패했습니다.'); return body; }
async function upload(file) {
  if (!file || busy) return;
  if (!file.name.toLowerCase().endsWith('.pdf') || file.size > 5*1024*1024) return status('5MB 이하의 PDF 파일을 선택해주세요.', true);
  lock(true); status('PDF에서 텍스트를 추출하고 있어요. 외부 AI에는 전송하지 않습니다.');
  try { const bytes = new Uint8Array(await file.arrayBuffer()); let binary=''; for(let i=0;i<bytes.length;i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192)); const result=await post('/api/pdf',{data:btoa(binary)}); $('resume').value=result.text; $('filename').textContent=file.name; status('추출 완료. 내용과 개인정보를 확인한 뒤 분석해주세요.'); $('result').hidden=true; }
  catch(e) { status(e.message,true); } finally { lock(false); $('pdf').value=''; }
}
$('pdf').addEventListener('change',e=>upload(e.target.files[0]));
$('drop').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();if(!busy)$('pdf').click();}});
for(const event of ['dragenter','dragover']) $('drop').addEventListener(event,e=>{e.preventDefault();$('drop').classList.add('over');});
for(const event of ['dragleave','drop']) $('drop').addEventListener(event,e=>{e.preventDefault();$('drop').classList.remove('over');if(event==='drop')upload(e.dataTransfer.files[0]);});
$('scrape').addEventListener('click',async()=>{
 if(busy)return;
 const url=$('url').value.trim();
 if(!url)return status('먼저 채용공고 원문 URL을 입력해주세요.',true);
 lock(true);status('공개 페이지를 읽고 공고 내용을 추출하고 있어요. AI API는 호출하지 않습니다.');
 try{
  const data=await post('/api/scrape',{url});
  $('company').value=data.company||'';$('position').value=data.position||'';$('posting').value=data.posting||'';$('deadline').value=data.deadline||'';$('url').value=data.source_url||url;
  $('result').hidden=true;lastResult=null;
  status(`${data.source_name||'웹사이트'}에서 공고를 가져왔어요. 회사·직무·마감일과 본문을 검토한 뒤 분석을 시작하세요.`);
 }catch(e){status(e.message,true);}finally{lock(false);}
});
function modeHint(){const mode=$('mode').value;$('modehint').textContent=mode==='demo'?'키워드 비교는 AI 평가가 아니며 외부로 전송하지 않습니다.':!serverConfig?'키 설정 상태를 확인하지 못했습니다. 서버 환경변수를 확인해주세요.':serverConfig.providers[mode]?.configured?'API 키 설정됨 (유효성은 분석 시 확인). 검토한 텍스트를 AI에 전송해 요구역량과 경험을 비교합니다.':'API 키 미설정. Gemini는 서버를 종료하고 python -m careerflow.web --ask-key 로 다시 실행해주세요. OpenAI는 OPENAI_API_KEY 설정이 필요합니다.';}
function modeChanged(){const ai=$('mode').value!=='demo';$('consent-wrap').hidden=!ai;$('consent').checked=false;modeHint();}
$('mode').addEventListener('change',modeChanged);
$('sample').addEventListener('click',()=>{
 $('resume').value='지원자: 샘플 지원자 (가상 데이터)\n\n[프로젝트 경험]\nPython과 LangChain을 이용해 금융 문서 RAG 챗봇을 개발했습니다.\nFastAPI로 검색 API를 구현하고 Git으로 변경 사항을 관리했습니다.\nSQL과 SQLite로 대화 기록을 저장했습니다.\n\n[학습 경험]\nPyTorch를 활용해 시계열 모델을 비교했습니다.';
 $('posting').value='[주요 업무]\n사내 문서 RAG 시스템 개발 및 Python 기반 AI 서비스 구현\nFastAPI 기반 백엔드 API 개발\n\n[자격 요건]\nPython 및 SQL 활용 경험\nGit을 이용한 협업 경험\n\n[우대 사항]\nLangChain 기반 검색 파이프라인 개발 경험\nDocker 컨테이너 및 AWS 배포 경험';
 $('company').value='넥스트랩 (가상 기업)';$('position').value='AI 엔지니어';$('url').value='';$('deadline').value='';$('filename').textContent='샘플 이력서 · 가상 데이터';modeChanged();$('result').hidden=true;status('가상 자료를 넣었어요. 선택한 분석 방식과 전송 동의를 확인한 뒤 비교 버튼을 눌러보세요.');
});
$('form').addEventListener('submit',async e=>{
 e.preventDefault();if(busy)return;
 if($('mode').value!=='demo'&&!$('consent').checked)return status('AI 분석에는 외부 전송 동의가 필요합니다.',true);
 const payload=Object.fromEntries(['resume','posting','company','position','deadline','mode'].map(id=>[id,$(id).value]));payload.consent=$('consent').checked;payload.source_url=$('url').value;
 lock(true);$('result').hidden=true;status(payload.mode==='demo'?'입력 문서에서 키워드를 비교하고 있어요.':'AI가 문서를 읽고 도구를 실행하고 있어요. 최대 6라운드로 제한하며 완료까지 시간이 걸릴 수 있어요.');
 try {const data=await post('/api/analyze',payload);lastResult={...data,source_url:$('url').value};$('summary').textContent=data.summary;$('matches').replaceChildren();
  for(const m of data.matches||[]){const row=document.createElement('div');row.className='match';const title=document.createElement('strong');title.textContent=m.skill;const tag=document.createElement('span');tag.className='state'+(m.found?' found':'');tag.textContent=m.found?'키워드 근거 발견':'이력서에서 미발견';row.append(title,tag);for(const text of ['공고 · '+m.job,'이력서 · '+(m.resume||'기재된 근거가 없습니다. 실제 경험이 있다면 보완해주세요.')]){const p=document.createElement('p');p.textContent=text;row.append(p);}$('matches').append(row);}
  if(data.matches?.length===0){const p=document.createElement('p');p.textContent='고정 기술 목록과 일치하는 키워드가 없습니다. 의미 기반 비교는 AI 분석을 선택해주세요.';$('matches').append(p);}
  $('events').replaceChildren();for(const event of data.events){const li=document.createElement('li');li.textContent=typeof event==='string'?event:`${event.tool} · ${event.ok?'완료':'검증 실패 또는 제한'}`;$('events').append(li);}
  $('result').hidden=false;status('비교 완료. 공고와 분석 결과를 로컬 보관함에 저장했어요.');$('result').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(e){status(e.message,true);}finally{lock(false);}
});
$('download').addEventListener('click',()=>{if(!lastResult)return;const blob=new Blob([JSON.stringify(lastResult,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='careerflow-result.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('reset').addEventListener('click',()=>{if(busy)return;$('form').reset();$('filename').textContent='이력서 PDF를 여기에 놓아주세요';$('result').hidden=true;lastResult=null;modeChanged();status('입력과 결과를 초기화했습니다.');});
modeChanged();
fetch('/api/config').then(r=>{if(!r.ok)throw new Error();return r.json();}).then(config=>{serverConfig=config;modeHint();}).catch(()=>modeHint());

// Local management screens. User/model text is always rendered as text, never HTML.
const management = document.createElement('section');
management.className='panel management'; management.hidden=true;
management.innerHTML='<h2 id="manage-title"></h2><p id="manage-status" role="status"></p><div id="manage-list"></div><div id="job-detail"></div>';
document.querySelector('.content').prepend(management);
const preparation = [...document.querySelector('.content').children].filter(el=>el!==management);
function manageStatus(message){$('manage-status').textContent=message;}
function element(tag,text){const node=document.createElement(tag);node.textContent=text;return node;}
function action(text,fn){const button=element('button',text);button.type='button';button.className='secondary';button.addEventListener('click',fn);return button;}
async function get(path){const response=await fetch(path);const data=await response.json();if(!response.ok)throw new Error(data.error||'조회 실패');return data;}
let view='prepare';
async function navigate(next){
 if(busy)return;view=next;management.hidden=next==='prepare';preparation.forEach(el=>{if(!el.dataset.originalHidden)el.dataset.originalHidden=el.hidden?'yes':'no';el.hidden=next!=='prepare'||el.dataset.originalHidden==='yes';});
 if(next==='prepare'){$('result').hidden=!lastResult;return;}
 $('manage-list').replaceChildren();$('job-detail').replaceChildren();manageStatus('불러오는 중…');
 $('manage-title').textContent=next==='jobs'?'공고 보관함':'준비 할 일';
 try{
  if(next==='jobs'){
   const data=await get('/api/jobs');
   for(const job of data.jobs){const row=element('div','');row.className='match';row.append(element('h3',`${job.company||'회사 미입력'} · ${job.position||'직무 미입력'}`),element('p',`마감: ${job.deadline||'미지정'} · 저장: ${job.updated_at} UTC`),action('분석 결과 및 할 일 준비',()=>openJob(job.id)));$('manage-list').append(row);}
   manageStatus(data.jobs.length?'저장된 결과 조회는 API를 호출하지 않습니다. 같은 회사·직무·본문의 재분석은 기존 결과를 갱신합니다.':'아직 저장된 공고가 없습니다. 먼저 지원 준비하기에서 분석해주세요.');
  }else{
   const data=await get('/api/tasks');
   const selected=new Set(data.tasks.filter(task=>task.status==='done').map(task=>task.id));let pending=0;
   const toolbar=element('div','');toolbar.className='task-toolbar';
   const deleteButton=action('삭제',async()=>{
    if(!selected.size||!window.confirm(`선택한 할 일 ${selected.size}개를 삭제할까요?`))return;
    deleteButton.disabled=true;
    try{const result=await post('/api/tasks/delete',{task_ids:[...selected]});if(view==='tasks'){await navigate('tasks');manageStatus(`${result.deleted_count}개를 삭제했습니다. 공고는 유지되며 보관함에서 다시 등록할 수 있습니다.`);}}
    catch(e){manageStatus(e.message);deleteButton.disabled=false;}
   });
   function selectionChanged(){deleteButton.disabled=!selected.size||pending>0;}
   toolbar.append(deleteButton);$('manage-list').append(toolbar);selectionChanged();
   for(const task of data.tasks){const row=element('div','');row.className='match';const label=element('label','');const box=document.createElement('input');box.type='checkbox';box.checked=task.status==='done';box.addEventListener('change',async()=>{box.disabled=true;pending++;selectionChanged();try{await post('/api/tasks/status',{task_id:task.id,status:box.checked?'done':'todo'});if(box.checked)selected.add(task.id);else selected.delete(task.id);manageStatus('진행 상태를 저장했습니다. 삭제를 누르면 체크된 할 일을 삭제합니다.');}catch(e){box.checked=!box.checked;manageStatus(e.message);}finally{box.disabled=false;pending--;selectionChanged();}});label.append(box,document.createTextNode(' '+task.title));row.append(label,element('p',`${task.company||'회사 미입력'} · ${task.position||'직무 미입력'} | 기한 ${task.due_date}`));$('manage-list').append(row);}
   manageStatus(data.tasks.length?'체크하면 완료로 저장됩니다. 삭제 버튼을 누르면 체크된 할 일을 삭제합니다.':'등록된 할 일이 없습니다. 공고 보관함에서 공고를 열어 등록해주세요.');
  }
 }catch(e){manageStatus(e.message);}
}
async function openJob(id){
 try{
  const job=await get('/api/jobs/'+id);if(view!=='jobs')return;const detail=$('job-detail');detail.replaceChildren();
  detail.append(element('h3',`${job.company||'회사 미입력'} · ${job.position||'직무 미입력'}`));
  const summary=element('p',job.result.summary.replace(/^#{1,6}[^\n]*다음에 할 수 있는 행동[^\n]*\n[\s\S]*?(?=^#{1,6}\s|(?![\s\S]))/gm,'').trim());summary.className='saved-summary';detail.append(summary);
  const original=element('details','');original.append(element('summary','저장된 공고 원문'),element('p',job.posting));detail.append(original);
  detail.append(element('h3','준비 할 일 등록'),element('p','AI 비교 결과를 바탕으로 만든 후보입니다. 실제 경험이 없다는 뜻은 아닙니다. 기한을 선택하고 등록 버튼을 누르세요.'));
  function taskForm(suggestion){
   const form=document.createElement('form');form.className='match';
   if(suggestion){form.append(element('strong',suggestion.title),element('p',suggestion.reason));}
   else{form.append(element('h3','직접 할 일 추가'));}
   const titleLabel=element('label','할 일 내용');const title=document.createElement('input');title.name='title';title.maxLength=300;title.required=true;title.value=suggestion?suggestion.title.slice(0,300):'';titleLabel.append(title);if(!suggestion)form.append(titleLabel);
   const controls=element('div','');controls.className='task-controls';
   const dueLabel=element('label','기한');const due=document.createElement('input');due.type='date';due.required=true;due.value=job.deadline||'';if(job.deadline)due.max=job.deadline;dueLabel.append(due);controls.append(dueLabel);
   const button=element('button','준비 할 일 등록하기');button.type='submit';button.className='primary';controls.append(button);form.append(controls);
   function syncRegistration(){const existing=(job.tasks||[]).find(task=>task.title===title.value.trim());button.disabled=!!existing;due.disabled=!!existing;button.textContent=existing?'등록 완료':'준비 할 일 등록하기';if(existing)due.value=existing.due_date;}
   syncRegistration();
   form.addEventListener('registration-updated',syncRegistration);
   form.addEventListener('submit',async e=>{e.preventDefault();button.disabled=true;try{const result=await post('/api/tasks',{job_id:job.id,title:title.value,due_date:due.value,approved:true});job.tasks.push({id:result.task_id,title:title.value.trim(),due_date:result.due_date});detail.querySelectorAll('form').forEach(f=>f.dispatchEvent(new Event('registration-updated')));manageStatus(result.already_registered?'이미 등록된 할 일입니다. 기존 기한을 유지합니다.':'준비 할 일에 등록했어요. 왼쪽 메뉴에서 확인할 수 있습니다.');}catch(err){manageStatus(err.message);syncRegistration();}});
   form.addEventListener('input',syncRegistration);
   return form;
  }
  for(const suggestion of job.result.suggestions||[])detail.append(taskForm(suggestion));
  detail.append(taskForm(null));detail.scrollIntoView({behavior:'smooth'});
 }catch(e){manageStatus(e.message);}
}
document.querySelectorAll('.sidebar .nav').forEach((old,index)=>{const names=['지원 준비하기','공고 보관함','준비 할 일'];const button=action(names[index],()=>{if(busy)return;document.querySelectorAll('.sidebar .nav').forEach(el=>el.classList.remove('active'));button.classList.add('active');navigate(['prepare','jobs','tasks'][index]);});button.className='nav'+(index===0?' active':'');old.replaceWith(button);});
const notice=element('p','공고와 분석 결과는 이 컴퓨터의 웹 전용 DB에 저장됩니다. 이력서 원문은 영구 보관하지 않지만 분석 결과에는 입력한 개인정보가 포함될 수 있으니 제거 후 이용해주세요.');notice.className='hint';$('form').prepend(notice);
document.querySelectorAll('.principles p')[1].textContent='원하는 할 일만 등록 버튼으로 추가해요.';
$('result').append(action('공고 보관함에서 준비 이어가기',()=>navigate('jobs')));
