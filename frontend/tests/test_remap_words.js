// Extraction de remapWords depuis studio.html pour test des critères LOT 0
function remapWords(newLinesW, anchors){
  const norm=w=>w.toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
  const N=[]; newLinesW.forEach((ws,li)=>ws.forEach(w=>N.push({w,li})));
  const n=N.length, m=anchors.length;
  if(!n||!m) return null;
  const dp=Array.from({length:n+1},()=>new Int16Array(m+1));
  for(let i=n-1;i>=0;i--){
    const ni=norm(N[i].w);
    for(let j=m-1;j>=0;j--){
      dp[i][j] = (ni && ni===norm(anchors[j].text))
        ? dp[i+1][j+1]+1
        : Math.max(dp[i+1][j], dp[i][j+1]);
    }
  }
  const match=new Array(n).fill(-1);
  let i=0,j=0;
  while(i<n&&j<m){
    const ni=norm(N[i].w);
    if(ni && ni===norm(anchors[j].text) && dp[i][j]===dp[i+1][j+1]+1){ match[i]=j; i++; j++; }
    else if(dp[i+1][j]>=dp[i][j+1]) i++;
    else j++;
  }
  const units=N.map((x,k)=>({
    text:x.w, lineIdx:x.li,
    t0: match[k]>=0? anchors[match[k]].t0 : null,
    t1: match[k]>=0? anchors[match[k]].t1 : null,
  }));
  const startT=anchors[0].t0, endT=anchors[m-1].t1;
  let k=0;
  while(k<n){
    if(units[k].t0!=null){k++;continue;}
    const s=k;
    while(k<n && units[k].t0==null) k++;
    const prevT = s>0 ? units[s-1].t1 : startT;
    const nextT = k<n ? units[k].t0 : endT;
    const cnt=k-s;
    const span=nextT-prevT;
    if(span>0.02){
      const dur=span/cnt;
      for(let q=0;q<cnt;q++){
        units[s+q].t0=prevT+q*dur;
        units[s+q].t1=prevT+(q+1)*dur;
      }
    }else if(s>0){
      const p=units[s-1];
      const per=(p.t1-p.t0)/(cnt+1);
      p.t1=p.t0+per;
      for(let q=0;q<cnt;q++){
        units[s+q].t0=p.t0+per*(q+1);
        units[s+q].t1=p.t0+per*(q+2);
      }
    }else{
      const per=0.22;
      for(let q=0;q<cnt;q++){
        units[s+q].t0=Math.max(0, startT-(cnt-q)*per);
        units[s+q].t1=Math.max(0.05, startT-(cnt-q-1)*per);
      }
    }
  }
  for(let q=0;q<n;q++){
    if(q>0 && units[q].t0<units[q-1].t0) units[q].t0=units[q-1].t0+0.01;
    if(units[q].t1<=units[q].t0) units[q].t1=units[q].t0+0.15;
    if(q<n-1 && units[q].t1>units[q+1].t0 && units[q+1].t0>units[q].t0)
      units[q].t1=units[q+1].t0;
  }
  return units;
}

// ============ TESTS CRITÈRES D'ACCEPTATION LOT 0 ============
let pass=0, fail=0;
function check(name, cond, detail=''){
  if(cond){ pass++; console.log(`  ✓ ${name}`); }
  else { fail++; console.log(`  ✗ ${name} ${detail}`); }
}

// Génère 50 mots avec timings réalistes
const words50 = Array.from({length:50},(_,i)=>({
  text:`mot${i}`, t0: 1+i*0.35, t1: 1+i*0.35+0.3, lineIdx: Math.floor(i/6)
}));

// TEST 1 : corriger l'orthographe d'1 mot sur 50 → les 49 autres timestamps STRICTEMENT identiques
console.log("TEST 1 — Correction d'1 mot sur 50 :");
{
  const newText = words50.map(w=>w.text);
  newText[25] = "corrigé";  // remplace mot25
  const lines=[]; for(let i=0;i<50;i+=6) lines.push(newText.slice(i,i+6));
  const out = remapWords(lines, words50);
  let identical = 0, changed=[];
  out.forEach((u,i)=>{
    if(i===25) return;
    if(u.t0===words50[i].t0 && u.t1===words50[i].t1) identical++;
    else changed.push(i);
  });
  check("49 timestamps strictement identiques", identical===49, `(identiques: ${identical}, changés: ${changed})`);
  check("le mot corrigé garde une plage plausible", out[25].t0>=words50[24].t1-0.01 && out[25].t1<=words50[26].t0+0.01,
    `(t0=${out[25].t0}, t1=${out[25].t1}, attendu entre ${words50[24].t1} et ${words50[26].t0})`);
}

// TEST 2 : insertion d'1 mot au milieu → seuls le mot inséré et son voisin immédiat modifiés
console.log("TEST 2 — Insertion d'1 mot au milieu :");
{
  const newText = words50.map(w=>w.text);
  newText.splice(25, 0, "inséré");
  const lines=[newText];
  const out = remapWords(lines, words50);
  // out a 51 mots. Mots 0..24 → anchors 0..24 ; out[25]=inséré ; out[26..50] → anchors 25..49
  let untouched=0, touched=[];
  for(let i=0;i<25;i++){ if(out[i].t0===words50[i].t0&&out[i].t1===words50[i].t1) untouched++; else touched.push(i); }
  for(let i=26;i<51;i++){ if(out[i].t0===words50[i-1].t0&&out[i].t1===words50[i-1].t1) untouched++; else touched.push(i); }
  // tolérance : le voisin immédiat (out[24] ou out[26]) peut être grignoté s'il n'y a pas de silence
  const strictOk = untouched>=48;
  check("mots hors zone d'insertion inchangés (>=48/50)", strictOk, `(inchangés: ${untouched}, touchés: ${JSON.stringify(touched)})`);
  check("le mot inséré a des timings valides", out[25].t0!=null && out[25].t1>out[25].t0);
}

// TEST 3 : suppression d'1 mot → les autres gardent leurs timings
console.log("TEST 3 — Suppression d'1 mot :");
{
  const newText = words50.map(w=>w.text);
  newText.splice(25, 1);
  const lines=[newText];
  const out = remapWords(lines, words50);
  let identical=0;
  out.forEach((u,i)=>{
    const src = i<25 ? words50[i] : words50[i+1];
    if(u.t0===src.t0 && u.t1===src.t1) identical++;
  });
  check("49 mots restants gardent leurs timings exacts", identical===49, `(identiques: ${identical}/49)`);
}

// TEST 4 : mode "colle tes paroles" — 30% de mots différents
console.log("TEST 4 — Colle tes paroles (30% de mots différents) :");
{
  const newText = words50.map((w,i)=> i%3===0 ? `verlan${i}` : w.text); // ~33% différents
  const lines=[newText];
  const out = remapWords(lines, words50);
  // les mots identiques (66%) doivent garder leurs timings
  let anchored=0, interp=0;
  out.forEach((u,i)=>{
    if(i%3!==0){ if(u.t0===words50[i].t0) anchored++; }
    else { if(u.t0!=null && u.t1>u.t0) interp++; }
  });
  const nbSame = words50.filter((_,i)=>i%3!==0).length;
  const nbDiff = 50-nbSame;
  check(`les ${nbSame} mots identiques gardent leurs timings`, anchored===nbSame, `(ancrés: ${anchored}/${nbSame})`);
  check(`les ${nbDiff} mots remplacés sont interpolés localement`, interp===nbDiff, `(interpolés: ${interp}/${nbDiff})`);
  // monotonie globale
  let mono=true;
  for(let i=1;i<out.length;i++) if(out[i].t0<out[i-1].t0) mono=false;
  check("timings monotones croissants", mono);
}

// TEST 5 : ponctuation/casse ignorées dans le matching
console.log("TEST 5 — Ponctuation et casse :");
{
  const anchors=[{text:"hello",t0:1,t1:1.3},{text:"world",t0:1.4,t1:1.7},{text:"yo",t0:1.8,t1:2.1}];
  const out = remapWords([["Hello,","WORLD!","yo?"]], anchors);
  check("Hello, == hello", out[0].t0===1);
  check("WORLD! == world", out[1].t0===1.4);
  check("yo? == yo", out[2].t0===1.8);
}

console.log(`\n===== RÉSULTAT : ${pass} PASS / ${fail} FAIL =====`);
process.exit(fail?1:0);
