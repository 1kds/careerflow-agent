const $ = id => document.getElementById(id);
let busy = false, lastResult = null, currentView = 'discovery';
let serverConfig = null, selectedJob = null, discoveryCache = null;
const autoSyncTried = new Set();
const status = (message, error = false) => { $('status').textContent = message; $('status').className = error ? 'error' : ''; };
const discoveryStatus = (message, error = false) => { $('discovery-status').textContent = message; $('discovery-status').className = error ? 'inline-status error' : 'inline-status'; };
function lock(value) {
  busy = value;
  for (const el of $('form').querySelectorAll('input,textarea,select,button')) el.disabled = value;
  $('analyze').textContent = value ? '처리 중입니다…' : '내 경험과 공고 비교하기 →';
}
async function post(path, data) {
  const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '요청에 실패했습니다.');
  return body;
}
async function get(path) {
  const response = await fetch(path);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '조회에 실패했습니다.');
  return body;
}
function element(tag, text) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; return node; }
function action(text, fn, className='secondary') {
  const button = element('button', text); button.type = 'button'; button.className = className; button.addEventListener('click', fn); return button;
}
function safeExternalLink(url, label) {
  const link = element('a', label); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; return link;
}

// Interest based, persistent job catalogue.
function fillCategories(items) {
  $('category').replaceChildren();
  for (const item of items || []) { const option = element('option', item.label); option.value = item.id; $('category').append(option); }
}
function renderSources(sources) {
  $('source-list').replaceChildren();
  const ready = (sources || []).filter(item => item.configured).length;
  $('source-copy').textContent = ready ? `${ready}개 공식 출처가 연결되어 있어요. 실제 공고를 가져오면 가상 공고와 함께 표시됩니다.` : '공식 채용 API가 아직 연결되지 않았어요. 테스트용 가상 공고는 아래에서 바로 이용할 수 있습니다.';
  for (const source of sources || []) {
    const item = element('div', ''); item.className = 'source-item';
    const name = element('strong', source.name); const state = element('span', source.configured ? '연결됨' : '키 설정 필요');
    state.className = source.configured ? 'source-state ready' : 'source-state';
    item.append(name, state, safeExternalLink(source.setup_url, 'API 안내 ↗'));
    $('source-list').append(item);
  }
}
function renderJobs(data) {
  discoveryCache = data;
  $('catalog-title').textContent = `${data.label || '관심 분야'} 공고`;
  const demoCount = data.jobs.filter(job => job.source === 'demo').length;
  $('catalog-meta').textContent = data.jobs.length
    ? `총 ${data.jobs.length}개 · 테스트용 가상 공고 ${demoCount}개 · 실제 공고 ${data.jobs.length - demoCount}개`
    : '저장된 공고가 없습니다.';
  renderSources(data.sources);
  $('job-list').replaceChildren();
  if (!data.jobs.length) {
    const empty = element('section', ''); empty.className = 'empty-state panel';
    empty.append(element('strong', '아직 이 분야 공고가 없어요.'), element('p', '관심 분야를 바꾸거나 채용 API 키를 설정해 실제 공고를 추가해보세요.'));
    $('job-list').append(empty); return;
  }
  for (const job of data.jobs) {
    const card = element('article', ''); card.className = 'job-card';
    const top = element('div', ''); top.className = 'job-card-top';
    const heading = element('div', ''); heading.append(element('span', job.source_name || '채용 출처'), element('h3', job.position || '제목 미공개'));
    if (job.source === 'demo') heading.append(element('span', '테스트용 가상 공고'));
    top.append(heading, element('span', job.deadline ? `마감 ${job.deadline}` : job.source === 'demo' ? '상시 예시' : '마감일 미정'));
    const company = element('p', job.company || '회사 미공개'); company.className = 'job-company';
    const facts = [job.location, job.career, job.job_type, job.salary].filter(Boolean).join(' · ');
    card.append(top, company);
    if (facts) { const meta = element('p', facts); meta.className = 'job-facts'; card.append(meta); }
    if (job.posted_at) { const posted = element('p', `등록 ${job.posted_at}`); posted.className = 'job-posted'; card.append(posted); }
    const footer = element('div', ''); footer.className = 'job-card-actions';
    if (job.source === 'demo') footer.append(element('span', '실제 채용 정보가 아닙니다'));
    else if (job.source_url) footer.append(safeExternalLink(job.source_url, `${job.source_name || '출처'} 원문 ↗`));
    footer.append(action('이 공고로 이력서 비교', () => prepareJob(job.id), 'primary'));
    card.append(footer); $('job-list').append(card);
  }
}
async function loadDiscovery({autoSync=false}={}) {
  if (!$('category').value) return;
  const requestedCategory = $('category').value;
  try {
    const data = await get(`/api/discovery?category=${encodeURIComponent(requestedCategory)}`);
    if (requestedCategory !== $('category').value) return;
    if (data.category !== $('category').value) $('category').value = data.category;
    renderJobs(data);
    if (autoSync && !autoSyncTried.has(data.category) && (data.sources || []).some(source => source.configured)) {
      const age = data.last_synced_at ? Date.now() - Date.parse(data.last_synced_at) : Infinity;
      if (!Number.isFinite(age) || age > 6 * 60 * 60 * 1000) { autoSyncTried.add(data.category); await syncJobs(true); }
    }
  } catch (error) { discoveryStatus(error.message, true); }
}
async function syncJobs(automatic=false) {
  if (busy) return;
  if (!(serverConfig?.job_sources || []).some(source => source.configured)) {
    discoveryStatus('사람인·고용24 API 키가 아직 없습니다. 테스트용 가상 공고는 그대로 이용할 수 있어요.');
    return;
  }
  const category = $('category').value;
  $('sync-jobs').disabled = true; $('refresh-list').disabled = true; $('category').disabled = true;
  discoveryStatus(automatic ? '연결된 출처에서 공고를 확인하고 있어요…' : '공식 출처에서 공고를 수집해 저장하고 있어요…');
  try {
    const result = await post('/api/discovery/sync', {category});
    renderJobs({category, label:discoveryCache?.label, jobs:result.jobs, last_synced_at:result.last_synced_at, sources:discoveryCache?.sources || serverConfig?.job_sources || []});
    const reports = (result.reports || []).map(report => report.error ? `${report.source}: ${report.error}` : `${report.source}: 조회 완료`).join(' · ');
    const succeeded = (result.reports || []).some(report => report.count > 0);
    discoveryStatus(succeeded ? `${result.saved_count}개 공고를 보관함에 저장했어요.${reports ? ` ${reports}` : ''}` : (reports || '연결된 공고 출처가 없습니다. API 키 설정을 확인해주세요.'), !succeeded);
  } catch (error) { discoveryStatus(error.message, true); }
  finally { $('sync-jobs').disabled = false; $('refresh-list').disabled = false; $('category').disabled = false; }
}
$('category').addEventListener('change', async () => {
  if (busy) return;
  try { await post('/api/preferences', {category:$('category').value}); await loadDiscovery({autoSync:true}); }
  catch (error) { discoveryStatus(error.message, true); }
});
$('sync-jobs').addEventListener('click', () => syncJobs(false));
$('refresh-list').addEventListener('click', () => loadDiscovery());

function showSelectedJob(job) {
  selectedJob = job;
  $('company').value = job.company || '';
  $('position').value = job.position || '';
  $('url').value = job.source_url || '';
  $('deadline').value = job.deadline || '';
  $('posting').value = job.description || '';
  $('result').hidden = true; lastResult = null;
  const box = $('selected-job'); box.replaceChildren();
  const summary = element('div', ''); summary.className = 'selected-job-summary';
  summary.append(element('span', job.source_name || '채용 출처'), element('h2', `${job.company || '회사 미공개'} · ${job.position || '제목 미공개'}`));
  if (job.source === 'demo') summary.append(element('p', '테스트용 가상 공고입니다. 실제 기업·채용 정보가 아니며 원문 링크도 없습니다.'));
  const details = [job.location, job.career, job.job_type, job.deadline ? `마감 ${job.deadline}` : '마감일 미정'].filter(Boolean).join(' · ');
  summary.append(element('p', details)); if(job.source_url)summary.append(safeExternalLink(job.source_url, `${job.source_name || '채용 출처'} 원문 보기 ↗`));
  box.append(summary);
}
async function prepareJob(id) {
  if (busy) return;
  document.querySelectorAll('.job-card-actions button').forEach(button=>button.disabled=true);
  discoveryStatus('선택한 공고의 상세 내용을 불러오고 있어요…');
  try {
    const job = await post('/api/catalog/prepare', {job_id:id});
    showSelectedJob(job);
    if (job.source === 'demo') { $('mode').value='demo'; modeChanged(); }
    navigate('resume');
    status(job.source === 'demo'
      ? '가상 공고를 불러왔어요. 로컬 키워드 비교로 API 없이 체험할 수 있습니다.'
      : '공고 내용을 가져왔어요. 원문을 검토한 뒤 이력서를 입력해 주세요.');
  } catch (error) {
    discoveryStatus(`${error.message} 출처 원문 링크를 확인한 뒤 다시 시도해주세요.`, true);
  } finally { document.querySelectorAll('.job-card-actions button').forEach(button=>button.disabled=false); }
}
$('change-job').addEventListener('click', () => navigate('discovery'));

// Local PDF text extraction. The resume is not sent anywhere until the user starts analysis.
async function upload(file) {
  if (!file || busy) return;
  if (!file.name.toLowerCase().endsWith('.pdf') || file.size > 5*1024*1024) return status('5MB 이하의 PDF 파일을 선택해주세요.', true);
  lock(true); status('PDF에서 텍스트를 추출하고 있어요. 외부 AI에는 전송하지 않습니다.');
  try {
    const bytes = new Uint8Array(await file.arrayBuffer()); let binary='';
    for (let i=0; i<bytes.length; i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
    const result = await post('/api/pdf',{data:btoa(binary)});
    $('resume').value=result.text; $('filename').textContent=file.name;
    status('추출 완료. 내용과 개인정보를 확인한 뒤 분석해주세요.'); $('result').hidden=true;
  } catch(error) { status(error.message,true); }
  finally { lock(false); $('pdf').value=''; }
}
$('pdf').addEventListener('change',event=>upload(event.target.files[0]));
$('drop').addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();if(!busy)$('pdf').click();}});
for(const event of ['dragenter','dragover']) $('drop').addEventListener(event,e=>{e.preventDefault();$('drop').classList.add('over');});
for(const event of ['dragleave','drop']) $('drop').addEventListener(event,e=>{e.preventDefault();$('drop').classList.remove('over');if(event==='drop')upload(e.dataTransfer.files[0]);});

function modeHint() {
  const mode=$('mode').value;
  $('modehint').textContent=mode==='demo'?'키워드 비교는 AI 평가가 아니며 외부로 전송하지 않습니다.':!serverConfig?'키 설정 상태를 확인하지 못했습니다. 서버 환경변수를 확인해주세요.':serverConfig.providers[mode]?.configured?'API 키 설정됨 (유효성은 분석 시 확인). 검토한 텍스트를 AI에 전송해 요구역량과 경험을 비교합니다.':'API 키 미설정. Gemini는 서버를 종료하고 python -m careerflow.web --ask-key 로 다시 실행해주세요. OpenAI는 OPENAI_API_KEY 설정이 필요합니다.';
}
function modeChanged() { const ai=$('mode').value!=='demo'; $('consent-wrap').hidden=!ai; $('consent').checked=false; modeHint(); }
$('mode').addEventListener('change',modeChanged);
$('sample').addEventListener('click',()=>{
  const demoJob={source_name:'CareerFlow 샘플',source_url:'',company:'넥스트랩 (가상 기업)',position:'AI 엔지니어',deadline:'',location:'서울',career:'경력 무관',
    description:'[주요 업무]\n사내 문서 RAG 시스템 개발 및 Python 기반 AI 서비스 구현\nFastAPI 기반 백엔드 API 개발\n\n[자격 요건]\nPython 및 SQL 활용 경험\nGit을 이용한 협업 경험\n\n[우대 사항]\nLangChain 기반 검색 파이프라인 개발 경험\nDocker 컨테이너 및 AWS 배포 경험'};
  showSelectedJob(demoJob);
  $('resume').value='지원자: 샘플 지원자 (가상 데이터)\n\n[프로젝트 경험]\nPython과 LangChain을 이용해 금융 문서 RAG 챗봇을 개발했습니다.\nFastAPI로 검색 API를 구현하고 Git으로 변경 사항을 관리했습니다.\nSQL과 SQLite로 대화 기록을 저장했습니다.\n\n[학습 경험]\nPyTorch를 활용해 시계열 모델을 비교했습니다.';
  $('filename').textContent='샘플 이력서 · 가상 데이터'; $('mode').value='demo'; modeChanged(); navigate('resume');
  status('가상 자료를 넣었어요. 분석 방식과 전송 동의를 확인한 뒤 비교 버튼을 눌러보세요.');
});
$('form').addEventListener('submit',async event=>{
  event.preventDefault(); if(busy)return;
  if(!selectedJob) return status('먼저 채용공고 찾기에서 공고를 선택해주세요.',true);
  if($('mode').value!=='demo'&&!$('consent').checked)return status('AI 분석에는 외부 전송 동의가 필요합니다.',true);
  const payload=Object.fromEntries(['resume','posting','company','position','deadline','mode'].map(id=>[id,$(id).value]));
  payload.consent=$('consent').checked; payload.source_url=$('url').value;
  lock(true); $('result').hidden=true; status(payload.mode==='demo'?'입력 문서에서 키워드를 비교하고 있어요.':'AI가 문서를 읽고 도구를 실행하고 있어요. 최대 6라운드로 제한하며 완료까지 시간이 걸릴 수 있어요.');
  try {
    const data=await post('/api/analyze',payload); lastResult={...data,source_url:$('url').value}; $('summary').textContent=data.summary; $('matches').replaceChildren();
    for(const match of data.matches||[]) {
      const row=element('div',''); row.className='match'; const title=element('strong',match.skill); const tag=element('span',match.found?'키워드 근거 발견':'이력서에서 미발견'); tag.className='state'+(match.found?' found':''); row.append(title,tag);
      for(const text of ['공고 · '+match.job,'이력서 · '+(match.resume||'기재된 근거가 없습니다. 실제 경험이 있다면 보완해주세요.')])row.append(element('p',text));
      $('matches').append(row);
    }
    if(data.matches?.length===0)$('matches').append(element('p','비교 목록에 포함한 키워드와 일치하는 표현이 없습니다. 의미 기반 분석은 AI 분석을 선택해주세요.'));
    $('events').replaceChildren();
    for(const event of data.events||[]) $('events').append(element('li',typeof event==='string'?event:`${event.tool} · ${event.ok?'완료':'검증 실패 또는 제한'}`));
    $('result').hidden=false; status('비교 완료. 공고와 분석 결과를 로컬 보관함에 저장했어요.'); $('result').scrollIntoView({behavior:'smooth',block:'start'});
  } catch(error) { status(error.message,true); }
  finally { lock(false); }
});
$('download').addEventListener('click',()=>{
  if(!lastResult)return;
  const blob=new Blob([JSON.stringify(lastResult,null,2)],{type:'application/json'}); const downloadUrl=URL.createObjectURL(blob);
  const link=document.createElement('a');link.href=downloadUrl;link.download='careerflow-result.json';link.click();setTimeout(()=>URL.revokeObjectURL(downloadUrl),1000);
});
$('reset').addEventListener('click',()=>{
  if(busy)return; $('resume').value=''; $('pdf').value=''; $('filename').textContent='이력서 PDF를 여기에 놓아주세요';
  $('result').hidden=true; lastResult=null; modeChanged(); status('이력서 입력과 분석 결과를 초기화했습니다. 선택한 공고는 유지됩니다.');
});
modeChanged();

// Separate archive and task views from job search and resume analysis.
const management=element('section',''); management.className='panel management'; management.hidden=true;
management.innerHTML='<h2 id="manage-title"></h2><p id="manage-status" role="status"></p><div id="manage-list"></div><div id="job-detail"></div>';
document.querySelector('.content').append(management);
function manageStatus(message){$('manage-status').textContent=message;}
let view='discovery';
async function navigate(next) {
  if(busy)return; currentView=next; view=next;
  $('discovery-page').hidden=next!=='discovery'; $('resume-page').hidden=next!=='resume';
  management.hidden=next!=='jobs'&&next!=='tasks';
  const titles={discovery:'채용공고 찾기',resume:'이력서 분석',jobs:'공고 보관함',tasks:'준비 할 일'};
  $('page-title').textContent=titles[next]||titles.discovery;
  document.querySelectorAll('.sidebar .nav').forEach(button=>button.classList.toggle('active',button.dataset.view===next));
  if(next==='discovery'){if(discoveryCache)renderJobs(discoveryCache);else await loadDiscovery({autoSync:true});return;}
  if(next==='resume'){if(!selectedJob)status('먼저 채용공고 찾기에서 공고를 선택해주세요.');return;}
  $('manage-list').replaceChildren(); $('job-detail').replaceChildren(); manageStatus('불러오는 중…');
  $('manage-title').textContent=next==='jobs'?'공고 보관함':'준비 할 일';
  try {
    if(next==='jobs') {
      const data=await get('/api/jobs');
      for(const job of data.jobs){const row=element('div','');row.className='match';row.append(element('h3',`${job.company||'회사 미입력'} · ${job.position||'직무 미입력'}`),element('p',`마감: ${job.deadline||'미지정'} · 저장: ${job.updated_at} UTC`),action('분석 결과 및 할 일 준비',()=>openJob(job.id)));$('manage-list').append(row);}
      manageStatus(data.jobs.length?'저장된 결과 조회는 API를 호출하지 않습니다.':'아직 분석 결과가 없습니다. 채용공고를 고르고 이력서를 비교해보세요.');
    } else {
      const data=await get('/api/tasks'); const selected=new Set(data.tasks.filter(task=>task.status==='done').map(task=>task.id));let pending=0;
      const toolbar=element('div','');toolbar.className='task-toolbar';
      const deleteButton=action('선택 삭제',async()=>{
        if(!selected.size||!window.confirm(`선택한 할 일 ${selected.size}개를 삭제할까요?`))return;deleteButton.disabled=true;
        try{const result=await post('/api/tasks/delete',{task_ids:[...selected]});if(view==='tasks'){await navigate('tasks');manageStatus(`${result.deleted_count}개를 삭제했습니다. 공고는 유지되며 보관함에서 다시 등록할 수 있습니다.`);}}
        catch(error){manageStatus(error.message);deleteButton.disabled=false;}
      });
      function selectionChanged(){deleteButton.disabled=!selected.size||pending>0;}
      toolbar.append(deleteButton);$('manage-list').append(toolbar);selectionChanged();
      for(const task of data.tasks){
        const row=element('div','');row.className='match';const label=element('label','');const box=document.createElement('input');box.type='checkbox';box.checked=task.status==='done';
        box.addEventListener('change',async()=>{box.disabled=true;pending++;selectionChanged();try{await post('/api/tasks/status',{task_id:task.id,status:box.checked?'done':'todo'});if(box.checked)selected.add(task.id);else selected.delete(task.id);manageStatus('진행 상태를 저장했습니다. 삭제를 누르면 체크된 할 일을 삭제합니다.');}catch(error){box.checked=!box.checked;manageStatus(error.message);}finally{box.disabled=false;pending--;selectionChanged();}});
        label.append(box,document.createTextNode(' '+task.title));row.append(label,element('p',`${task.company||'회사 미입력'} · ${task.position||'직무 미입력'} | 기한 ${task.due_date}`));$('manage-list').append(row);
      }
      manageStatus(data.tasks.length?'체크하면 완료로 저장됩니다. 삭제 버튼을 누르면 체크된 할 일을 삭제합니다.':'등록된 할 일이 없습니다. 공고 보관함에서 분석 결과를 열어 등록해주세요.');
    }
  } catch(error) { manageStatus(error.message); }
}
async function openJob(id) {
  try {
    const job=await get('/api/jobs/'+id); if(view!=='jobs')return; const detail=$('job-detail');detail.replaceChildren();
    detail.append(element('h3',`${job.company||'회사 미입력'} · ${job.position||'직무 미입력'}`));
    const summary=element('p',job.result.summary);summary.className='saved-summary';detail.append(summary);
    const original=element('details','');original.append(element('summary','저장된 공고 원문'),element('p',job.posting));detail.append(original);
    detail.append(element('h3','준비 할 일 등록'),element('p','AI 비교 결과를 바탕으로 만든 후보입니다. 실제 경험이 없다는 뜻은 아닙니다. 기한을 선택하고 등록 버튼을 누르세요.'));
    function taskForm(suggestion){
      const form=document.createElement('form');form.className='match';
      if(suggestion)form.append(element('strong',suggestion.title),element('p',suggestion.reason));else form.append(element('h3','직접 할 일 추가'));
      const titleLabel=element('label','할 일 내용');const title=document.createElement('input');title.name='title';title.maxLength=300;title.required=true;title.value=suggestion?suggestion.title.slice(0,300):'';titleLabel.append(title);if(!suggestion)form.append(titleLabel);
      const controls=element('div','');controls.className='task-controls';const dueLabel=element('label','기한');const due=document.createElement('input');due.type='date';due.required=true;due.value=job.deadline||'';if(job.deadline)due.max=job.deadline;dueLabel.append(due);controls.append(dueLabel);
      const button=element('button','준비 할 일 등록하기');button.type='submit';button.className='primary';controls.append(button);form.append(controls);
      function syncRegistration(){const existing=(job.tasks||[]).find(task=>task.title===title.value.trim());button.disabled=!!existing;due.disabled=!!existing;button.textContent=existing?'등록 완료':'준비 할 일 등록하기';if(existing)due.value=existing.due_date;}
      syncRegistration();form.addEventListener('registration-updated',syncRegistration);
      form.addEventListener('submit',async event=>{event.preventDefault();button.disabled=true;try{const result=await post('/api/tasks',{job_id:job.id,title:title.value,due_date:due.value,approved:true});job.tasks.push({id:result.task_id,title:title.value.trim(),due_date:result.due_date});detail.querySelectorAll('form').forEach(item=>item.dispatchEvent(new Event('registration-updated')));manageStatus(result.already_registered?'이미 등록된 할 일입니다. 기존 기한을 유지합니다.':'준비 할 일에 등록했어요. 왼쪽 메뉴에서 확인할 수 있습니다.');}catch(error){manageStatus(error.message);syncRegistration();}});
      form.addEventListener('input',syncRegistration);return form;
    }
    for(const suggestion of job.result.suggestions||[])detail.append(taskForm(suggestion));detail.append(taskForm(null));detail.scrollIntoView({behavior:'smooth'});
  } catch(error) { manageStatus(error.message); }
}
document.querySelectorAll('.sidebar .nav').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.view)));
$('result').append(action('공고 보관함에서 준비 이어가기',()=>navigate('jobs')));

async function initialize() {
  try {
    serverConfig=await get('/api/config'); fillCategories(serverConfig.interests); renderSources(serverConfig.job_sources); modeHint();
    const data=await get('/api/discovery'); $('category').value=data.category; await loadDiscovery({autoSync:true});
  } catch(error) { discoveryStatus(error.message,true); modeHint(); }
}
initialize();
