/* Framework-free UI. Every quantitative result comes from the Python report. */
'use strict';
const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const colors = ['#42795b','#8ba66a','#c4d49a','#e1e8c5','#b5c1a0','#758a6b','#c9c0a0','#a9b9b5','#8b9f99','#dee2d4','#66796b'];
const state = {report:null, selected:null, expanded:false, query:''};
const pct = (n, digits=2) => `${(n*100).toFixed(digits)}%`;
const shortDate = (s) => new Date(`${s}T12:00:00Z`).toLocaleDateString('en-US',{month:'short',year:'numeric',timeZone:'UTC'});
const money = (n) => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n);
function el(tag, attrs={}, text) {
  const n=document.createElementNS(NS,tag);
  Object.entries(attrs).forEach(([key,value])=>n.setAttribute(key,value));
  if(text!==undefined)n.textContent=text;
  return n;
}
function append(svg,tag,attrs,text){const n=el(tag,attrs,text);svg.append(n);return n;}
function linePath(points,x,y){return points.map((p,i)=>`${i?'L':'M'}${x(p,i).toFixed(2)},${y(p,i).toFixed(2)}`).join(' ');}
function addText(node,text,className){const span=document.createElement('span');span.textContent=text;if(className)span.className=className;node.append(span);return span;}

async function init(){
  try {
    const base=window.INDEXLENS_CONFIG?.apiBase?.replace(/\/$/,'')||'';
    const response=await fetch(base?`${base}/api/report`:'./data/report.json',{signal:AbortSignal.timeout(20000)});
    if(!response.ok)throw new Error('Report unavailable');
    const report=await response.json();
    if(report.schema_version!==1||!Array.isArray(report.portfolios)||!report.portfolios.length)throw new Error('Unsupported report');
    state.report=report;
    const sourceUrl=window.INDEXLENS_CONFIG?.sourceUrl;
    if(sourceUrl&&/^https:\/\/github\.com\//.test(sourceUrl))$('sourceLink').href=sourceUrl;
    else {$('sourceLink').textContent='Source package available';$('sourceLink').removeAttribute('href');}
    $('holdingRange').max=report.portfolios.length-1;
    ['holdingRange','autoButton','exportButton'].forEach(id=>$(id).disabled=false);
    const demo=report.dataset.kind==='synthetic';
    $('dataStatus').replaceChildren();const statusDot=document.createElement('i');$('dataStatus').append(statusDot,document.createTextNode(demo?'SIMULATED DEMO':`DATA THROUGH ${report.dataset.last_date}`));
    $('notice').replaceChildren();addText($('notice'),'◈');const message=document.createElement('p');
    const lead=document.createElement('strong');lead.textContent=demo?'Interactive demo — simulated data. ':'Historical research snapshot. ';message.append(lead);
    message.append(document.createTextNode(demo?'These are fictional stocks and returns, not S&P 500 performance. The Python data adapter can load real constituents and adjusted prices with an FMP key.':`SPY total-return proxy · current constituents · as of ${report.dataset.last_date}. Historical test-start weights; survivorship bias remains.`));$('notice').append(message);
    $('benchmarkHint').textContent=demo?'Demonstration only · fictional 500-stock universe':`${report.dataset.eligible_assets} eligible stocks · SPY total-return proxy`;
    $('performancePeriod').textContent=`${shortDate(report.windows.test.start)} – ${shortDate(report.windows.test.end)}`;
    $('costLabel').textContent=`${report.model.cost_bps} bps / traded dollar`;
    $('recommendationTitle').textContent=`${report.recommended_budget}-stock budget is the balance`;
    $('recommendationDetail').textContent='Equal importance for fewer holdings and lower validation error. Test results do not choose the portfolio.';
    $('weightsDate').textContent=`Weights at test start · ${report.model.weights_as_of}`;
    $('tradingDetails').textContent=`Fractional holdings in USD. Rebalance every ${report.model.rebalance_every_sessions} observed sessions; weights drift between rebalances. A ${report.model.cost_bps} bps cost applies to the initial purchase and each dollar bought or sold. Reinvestment is represented by adjusted returns. No taxes, bid–ask spread model, or market-impact model. No sale is assumed at the final date.`;
    $('windowDetails').replaceChildren();
    Object.entries(report.windows).forEach(([label,w])=>{const row=document.createElement('div');row.textContent=`${label[0].toUpperCase()+label.slice(1)}: ${w.start} → ${w.end} (${w.observations} observations)`;$('windowDetails').append(row);});
    $('warningsList').replaceChildren();
    report.warnings.forEach(w=>{const li=document.createElement('li');li.textContent=w;$('warningsList').append(li);});
    $('qualityDetails').textContent=JSON.stringify(report.dataset,null,2);
    selectBudget(report.recommended_budget);
  }catch(error){
    $('notice').classList.add('error');$('notice').textContent='The report could not be loaded. Serve the web folder over HTTP, or check that the Python build generated data/report.json. Reload to retry.';
    $('dataStatus').textContent='REPORT UNAVAILABLE';
  }
}

function selectBudget(budget){
  const r=state.report;const p=r.portfolios.find(x=>x.budget===budget);if(!p)return;
  state.selected=p;
  const index=r.portfolios.indexOf(p);const slider=$('holdingRange');slider.value=index;
  slider.style.background=`linear-gradient(to right,var(--green) ${index/(r.portfolios.length-1)*100}%,#e5eae1 ${index/(r.portfolios.length-1)*100}%)`;
  slider.setAttribute('aria-valuetext',`${p.budget} stock maximum`);
  $('holdingNumber').textContent=p.budget;
  $('metricHoldings').replaceChildren(document.createTextNode(p.holding_count));const total=document.createElement('small');total.textContent=`/ ${r.dataset.eligible_assets}`;$('metricHoldings').append(total);
  $('metricReduction').textContent=`${pct(1-p.holding_count/r.dataset.eligible_assets,0)} fewer holdings than the universe`;$('metricReduction').classList.add('positive');
  $('metricError').textContent=pct(p.test.tracking_error);
  $('metricCorrelation').textContent=p.test.correlation===null?'N/A':p.test.correlation.toFixed(3);
  const gap=p.test.cumulative_gap;$('metricGap').replaceChildren(document.createTextNode(`${gap>=0?'+':''}${(gap*100).toFixed(2)}`));const pp=document.createElement('small');pp.textContent='pp';$('metricGap').append(pp);$('metricGap').classList.toggle('negative',gap<0);
  $('tableCount').textContent=p.holding_count;
  $('autoButton').title=`Automatically selected holding budget: ${r.recommended_budget}`;
  drawPerformance();drawFrontier();drawSectors();drawTable();
}

function drawPerformance(){
  const svg=$('performanceChart'),series=state.selected.series;svg.replaceChildren();
  const W=700,H=270,m={l:40,r:14,t:17,b:31};
  let low=Math.min(...series.flatMap(p=>[p.portfolio,p.benchmark])),high=Math.max(...series.flatMap(p=>[p.portfolio,p.benchmark]));
  const spread=Math.max(high-low,1);low-=spread*.10;high+=spread*.12;
  const x=(i)=>m.l+i/(series.length-1)*(W-m.l-m.r),y=(v)=>H-m.b-(v-low)/(high-low)*(H-m.t-m.b);
  for(let i=0;i<5;i++){const value=low+(high-low)*i/4;append(svg,'line',{x1:m.l,x2:W-m.r,y1:y(value),y2:y(value),class:'grid-line'});append(svg,'text',{x:m.l-10,y:y(value)+4,'text-anchor':'end'},value.toFixed(0));}
  const defs=append(svg,'defs');const grad=append(defs,'linearGradient',{id:'areaFade',x1:0,x2:0,y1:0,y2:1});append(grad,'stop',{offset:'0%','stop-color':'#55926d','stop-opacity':'.12'});append(grad,'stop',{offset:'100%','stop-color':'#55926d','stop-opacity':'0'});
  const path=linePath(series,(p,i)=>x(i),p=>y(p.portfolio));
  append(svg,'path',{d:`${path} L${x(series.length-1)},${H-m.b} L${m.l},${H-m.b} Z`,fill:'url(#areaFade)'});
  append(svg,'path',{d:linePath(series,(p,i)=>x(i),p=>y(p.benchmark)),fill:'none',stroke:'#a8b2a2','stroke-width':'1.6','stroke-dasharray':'4 3','stroke-linejoin':'round','vector-effect':'non-scaling-stroke'});
  append(svg,'path',{d:path,fill:'none',stroke:'#357759','stroke-width':'1.8','stroke-linejoin':'round','vector-effect':'non-scaling-stroke'});
  for(let j=0;j<5;j++){const i=Math.round((series.length-1)*j/4);append(svg,'text',{x:x(i),y:H-7,'text-anchor':j===0?'start':j===4?'end':'middle'},shortDate(series[i].date));}
  const guide=append(svg,'line',{y1:m.t,y2:H-m.b,stroke:'#99ad8f','stroke-dasharray':'3 3',visibility:'hidden'});
  const dot=append(svg,'circle',{r:4,fill:'#357759',stroke:'white','stroke-width':2,visibility:'hidden'});
  svg.onpointermove=(event)=>{
    const rect=svg.getBoundingClientRect();const svgX=(event.clientX-rect.left)*W/rect.width;
    const i=Math.min(series.length-1,Math.max(0,Math.round((svgX-m.l)/(W-m.l-m.r)*(series.length-1))));const point=series[i];
    guide.setAttribute('x1',x(i));guide.setAttribute('x2',x(i));guide.setAttribute('visibility','visible');dot.setAttribute('cx',x(i));dot.setAttribute('cy',y(point.portfolio));dot.setAttribute('visibility','visible');
    const tip=$('chartTooltip');tip.replaceChildren();const title=document.createElement('strong');title.textContent=point.date;tip.append(title,document.createElement('br'),document.createTextNode(`Portfolio  ${point.portfolio.toFixed(2)}`),document.createElement('br'),document.createTextNode(`Benchmark  ${point.benchmark.toFixed(2)}`));tip.hidden=false;tip.style.left=`${Math.max(0,Math.min(rect.width-160,event.clientX-rect.left+13))}px`;tip.style.top='12px';
  };
  svg.onpointerleave=()=>{guide.setAttribute('visibility','hidden');dot.setAttribute('visibility','hidden');$('chartTooltip').hidden=true;};
}

function drawFrontier(){
  const svg=$('frontierChart');svg.replaceChildren();const ps=state.report.portfolios,W=390,H=250,m={l:43,r:18,t:32,b:40};
  const minK=Math.min(...ps.map(p=>p.budget)),maxK=Math.max(...ps.map(p=>p.budget));
  const minE=0,maxE=Math.max(...ps.map(p=>p.validation.tracking_rmse))*1.12;
  const x=k=>m.l+(k-minK)/(maxK-minK)*(W-m.l-m.r),y=e=>H-m.b-(e-minE)/(maxE-minE)*(H-m.t-m.b);
  append(svg,'text',{x:m.l,y:12,class:'axis-title'},'VALIDATION TRACKING RMSE');
  for(let j=0;j<4;j++){const v=maxE*j/3;append(svg,'line',{x1:m.l,x2:W-m.r,y1:y(v),y2:y(v),class:'grid-line'});append(svg,'text',{x:m.l-9,y:y(v)+4,'text-anchor':'end'},pct(v,1));}
  const recommended=ps.find(p=>p.budget===state.report.recommended_budget);
  append(svg,'line',{x1:x(recommended.budget),x2:x(recommended.budget),y1:m.t,y2:H-m.b,stroke:'#dce6cf','stroke-dasharray':'4 4'});
  append(svg,'path',{d:linePath(ps,p=>x(p.budget),p=>y(p.validation.tracking_rmse)),fill:'none',stroke:'#829c68','stroke-width':1.8});
  ps.forEach(p=>{
    const selected=p===state.selected;
    const group=append(svg,'g',{role:'button',tabindex:'0','aria-label':`${p.budget} holding budget, validation RMSE ${pct(p.validation.tracking_rmse)}${p.budget===state.report.recommended_budget?', recommended':''}`});
    append(group,'circle',{cx:x(p.budget),cy:y(p.validation.tracking_rmse),r:15,fill:'transparent'});
    if(selected)append(group,'circle',{cx:x(p.budget),cy:y(p.validation.tracking_rmse),r:10,fill:'#e5efda'});
    append(group,'circle',{cx:x(p.budget),cy:y(p.validation.tracking_rmse),r:selected?6:4.5,fill:selected?'#326b4c':'#9eb384',class:'frontier-dot'});
    group.onclick=()=>selectBudget(p.budget);group.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectBudget(p.budget);}};
    append(svg,'text',{x:x(p.budget),y:H-m.b+18,'text-anchor':'middle'},p.budget);
  });
  append(svg,'text',{x:(W+m.l-m.r)/2,y:H-4,'text-anchor':'middle',class:'axis-title'},'MAXIMUM NUMBER OF HOLDINGS');
}

function drawSectors(){
  const svg=$('sectorChart');svg.replaceChildren();const sectors=state.selected.sectors,total=2*Math.PI*80;let start=0;
  append(svg,'circle',{cx:110,cy:110,r:80,fill:'none',stroke:'#f0f3eb','stroke-width':22});
  sectors.forEach((s,i)=>{const length=s.weight*total;append(svg,'circle',{cx:110,cy:110,r:80,fill:'none',stroke:colors[i%colors.length],'stroke-width':22,'stroke-dasharray':`${Math.max(0,length-3)} ${total-Math.max(0,length-3)}`,'stroke-dashoffset':-start,transform:'rotate(-90 110 110)'});start+=length;});
  $('sectorCount').textContent=sectors.length;$('sectorLegend').replaceChildren();
  sectors.forEach((s,i)=>{const row=document.createElement('div');row.className='sector-row';const dot=document.createElement('i');dot.style.background=colors[i%colors.length];row.append(dot);addText(row,s.sector);addText(row,pct(s.weight,1));$('sectorLegend').append(row);});
}

function validCapital(){const value=Number($('capital').value);return Number.isFinite(value)&&value>=1&&value<=1e9?value:null;}
function drawTable(){
  if(!state.selected)return;
  const body=$('holdingsBody');body.replaceChildren();const capital=validCapital();
  const matches=state.selected.holdings.filter(h=>`${h.symbol} ${h.name} ${h.sector}`.toLowerCase().includes(state.query.toLowerCase()));
  const shown=state.expanded||state.query?matches:matches.slice(0,7);
  shown.forEach(h=>{const row=document.createElement('tr'),asset=document.createElement('td'),cell=document.createElement('div');cell.className='asset-cell';addText(cell,h.symbol.startsWith('SIM')?h.symbol.slice(-2):h.symbol.slice(0,2),'ticker-logo');const info=document.createElement('div');addText(info,h.symbol,'ticker-name');addText(info,h.name,'company-name');cell.append(info);asset.append(cell);row.append(asset);
    const sector=document.createElement('td');sector.textContent=h.sector;row.append(sector);
    const weight=document.createElement('td');weight.className='number weight-cell';const track=document.createElement('span');track.className='weight-track';const bar=document.createElement('i');bar.style.width=`${h.weight/state.report.model.max_position_weight*100}%`;track.append(bar);weight.append(track,document.createTextNode(pct(h.weight,2)));row.append(weight);
    const amount=document.createElement('td');amount.className='number';amount.textContent=capital===null?'—':money(h.weight*capital);row.append(amount);body.append(row);
  });
  if(!shown.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=4;cell.textContent='No holdings match your search.';row.append(cell);body.append(row);}
  $('showAllButton').hidden=matches.length<=7||!!state.query;$('showAllButton').textContent=state.expanded?'Show fewer ↑':`Show all ${matches.length} holdings ↓`;
}

function exportCSV(){
  if(!state.selected)return;
  // Prefix formula-like text to prevent spreadsheet formula injection.
  const escape=v=>{let s=String(v);if(/^[=+@\-\t\r]/.test(s)&&typeof v!=='number')s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
  const r=state.report,c=validCapital();const rows=[['symbol','name','sector','weight','allocation_usd','data_kind','weights_as_of'],...state.selected.holdings.map(h=>[h.symbol,h.name,h.sector,h.weight,c===null?'':(h.weight*c).toFixed(2),r.dataset.kind,r.model.weights_as_of])];
  const blob=new Blob(['\uFEFF'+rows.map(row=>row.map(escape).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8;'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`indexlens-${r.dataset.kind}-${state.selected.budget}-stocks.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

$('holdingRange').addEventListener('input',e=>{if(state.report)selectBudget(state.report.portfolios[Number(e.target.value)].budget);});
$('autoButton').addEventListener('click',()=>selectBudget(state.report.recommended_budget));
$('searchHoldings').addEventListener('input',e=>{state.query=e.target.value;drawTable();});
$('capital').addEventListener('input',drawTable);
$('showAllButton').addEventListener('click',()=>{state.expanded=!state.expanded;drawTable();});
$('exportButton').addEventListener('click',exportCSV);
document.querySelectorAll('[data-method]').forEach(b=>b.addEventListener('click',()=>$('methodDialog').showModal()));
$('closeMethod').addEventListener('click',()=>$('methodDialog').close());
$('methodDialog').addEventListener('click',e=>{if(e.target===$('methodDialog')){const rect=e.target.getBoundingClientRect();if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)e.target.close();}});
init();
