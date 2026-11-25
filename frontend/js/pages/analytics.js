/* Gráficos e estatísticas do Cognix: código de apresentação sem dados externos. */
const num=x=>Number(x);
const good=x=>x!==null&&x!==undefined&&Number.isFinite(num(x));
const n1=x=>good(x)?num(x).toLocaleString('pt-BR',{maximumFractionDigits:1,minimumFractionDigits:1}):'—';
const clean=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function stats(values){const v=values.filter(good).map(num).sort((a,b)=>a-b);const n=v.length;if(!n)return null;const m=v.reduce((a,b)=>a+b,0)/n;
 const q=p=>{const i=(n-1)*p,l=Math.floor(i),h=Math.ceil(i);return v[l]+(v[h]-v[l])*(i-l)};
 const variance=n>1?v.reduce((s,x)=>s+(x-m)**2,0)/(n-1):null;
 return {n,mean:m,median:q(.5),q1:q(.25),q3:q(.75),min:v[0],max:v[n-1],sd:variance===null?null:Math.sqrt(variance),variance};}
export function histogram(values){const valid=values.filter(good).map(num);if(!valid.length)return '<p class="muted">Sem notas.</p>';
 const bins=Array.from({length:10},()=>0);valid.forEach(v=>bins[Math.min(9,Math.max(0,Math.floor(v)))]++);const max=Math.max(1,...bins);
 const width=660,height=244,left=42,right=15,top=22,bottom=39,w=(width-left-right)/10;
 const y=n=>top+(height-top-bottom)*(1-n/max);let svg='';
 for(let i=0;i<=max;i+=Math.max(1,Math.ceil(max/5)))svg+=`<line x1="${left}" x2="${width-right}" y1="${y(i)}" y2="${y(i)}" stroke="var(--line)"/><text x="${left-8}" y="${y(i)+4}" text-anchor="end">${i}</text>`;
 bins.forEach((n,i)=>{const color=i<4?'var(--rose)':i<6?'var(--amber)':'var(--teal)';const x=left+i*w+4;svg+=`<rect x="${x}" y="${y(n)}" width="${w-8}" height="${Math.max(0,y(0)-y(n))}" rx="5" fill="${color}" opacity=".85"><title>Nota ${i}–${i+1}: ${n} aluno(s)</title></rect><text x="${x+(w-8)/2}" y="${height-bottom+20}" text-anchor="middle">${i}</text>`});
 return `<svg class="data-svg" role="img" aria-label="Histograma da distribuição de notas" viewBox="0 0 ${width} ${height}">${svg}<text x="${width-right}" y="${height-bottom+20}" text-anchor="end">10</text></svg>`;}
export function evolution(series){const points=series.filter(x=>good(x.stats?.mean));if(!points.length)return '<p class="muted">Sem avaliações com notas.</p>';
 const W=680,H=232,L=38,R=23,T=25,B=51;const x=i=>L+(W-L-R)*i/Math.max(1,points.length-1),y=v=>T+(H-T-B)*(1-v/10);let svg='';
 for(let t=0;t<=10;t+=2)svg+=`<line x1="${L}" x2="${W-R}" y1="${y(t)}" y2="${y(t)}" stroke="var(--line)"/><text x="${L-7}" y="${y(t)+4}" text-anchor="end">${t}</text>`;
 svg+=`<line x1="${L}" x2="${W-R}" y1="${y(6)}" y2="${y(6)}" stroke="var(--rose)" stroke-dasharray="5 4"/>`;
 svg+=`<polyline points="${points.map((p,i)=>`${x(i)},${y(p.stats.mean)}`).join(' ')}" fill="none" stroke="var(--accent)" stroke-width="3" stroke-linejoin="round"/>`;
 points.forEach((p,i)=>{const xi=x(i),yi=y(p.stats.mean);svg+=`<circle cx="${xi}" cy="${yi}" r="4" fill="var(--paper)" stroke="var(--accent)" stroke-width="2"><title>${clean(p.assessment)} · média ${n1(p.stats.mean)}</title></circle><text x="${xi}" y="${yi-12}" text-anchor="middle" class="value">${n1(p.stats.mean)}</text><text x="${xi}" y="${H-B+21}" text-anchor="${i===0?'start':i===points.length-1?'end':'middle'}">${clean(p.assessment.slice(0,18))}</text>`});
 return `<svg class="data-svg" role="img" aria-label="Evolução da média da turma nas avaliações" viewBox="0 0 ${W} ${H}">${svg}</svg>`;}
export function boxplots(series){const pts=series.filter(x=>good(x.stats?.median));if(!pts.length)return '<p class="muted">Sem notas suficientes.</p>';const H=30+pts.length*46,W=680,L=175,R=25,x=v=>L+(W-L-R)*v/10;let svg='';
 pts.forEach((p,i)=>{const s=p.stats,y=24+i*46;const a=good(s.q1)?s.q1:s.median,b=good(s.q3)?s.q3:s.median;svg+=`<text x="${L-9}" y="${y+4}" text-anchor="end">${clean(p.assessment.slice(0,22))}</text><line x1="${x(s.min)}" x2="${x(s.max)}" y1="${y}" y2="${y}" stroke="var(--accent)"/><rect x="${x(a)}" y="${y-10}" width="${Math.max(2,x(b)-x(a))}" height="20" fill="var(--accent)" opacity=".2" stroke="var(--accent)"/><line x1="${x(s.median)}" x2="${x(s.median)}" y1="${y-10}" y2="${y+10}" stroke="var(--accent)" stroke-width="2"/><circle cx="${x(s.mean)}" cy="${y}" r="3" fill="var(--navy)"/><title>${clean(p.assessment)} · mediana ${n1(s.median)}</title>`});
 return `<svg class="data-svg" role="img" aria-label="Boxplots por avaliação" viewBox="0 0 ${W} ${H}">${svg}</svg>`;}
export function heatColor(v){if(!good(v))return '';const x=num(v);const color=x<4?'var(--rose)':x<6?'var(--amber)':x>=8?'var(--teal)':'var(--accent)';const pct=x<6?19:14;return `background:color-mix(in srgb,${color} ${pct}%,var(--paper))`;}
