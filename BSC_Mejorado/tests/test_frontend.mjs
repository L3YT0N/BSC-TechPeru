import fs from 'node:fs/promises';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const base=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source=await fs.readFile(base+'/frontend/app.js','utf8');
const seed=JSON.parse(await fs.readFile(base+'/data/seed.json','utf8'));
const elements=new Map();
const document={querySelector(s){if(!elements.has(s))elements.set(s,{addEventListener(){},classList:{remove(){},toggle(){}},showModal(){},innerHTML:'',textContent:'',hidden:false});return elements.get(s);},addEventListener(){},querySelectorAll(){return []}};
const context=vm.createContext({document,console,Date,Intl,URL,Blob,FormData,Set,setTimeout,history:{replaceState(){}}});
vm.runInContext(source.slice(0,source.lastIndexOf('(async()=>')),context);
context.fixture={...seed,users:[],audit:[],revision:1};
vm.runInContext("state=fixture;user={id:'u1',name:'Administrador',role:'Administrador',area:'Gerencia'};year='2025';",context);
const check=(expr,label)=>{if(!vm.runInContext(expr,context))throw Error(label);};
check('Math.abs(globalPct()-84.22715272347814)<0.00001','El resumen no coincide');
check("score(compliance(state.kpis[0],0)).label==='Crítico'",'Cero tratado como vacío');
for(const page of ['dashboard','mapa','objetivos','kpis','mediciones','iniciativas','reportes','administracion','ayuda']){
 context.testPage=page;check('views[testPage]().includes("<h1>")','Vista sin contenido: '+page);
}
vm.runInContext("filters.search='NPS'",context);check('filteredKpis().length===1','Filtro de búsqueda');
vm.runInContext("year='2026'",context);check('globalPct()===null && current(state.kpis[0])===null','Filtro de año');
vm.runInContext("year='2025';filters.search='';openForm('kpis','KPI-01')",context);
check("document.querySelector('#fields').innerHTML.includes('name=\"target\"')",'Formulario KPI');
vm.runInContext("openForm('measurements',null,'KPI-01')",context);
check("document.querySelector('#fields').innerHTML.includes('name=\"period\"')",'Formulario de resultados');
console.log('Lógica frontend: 9 vistas, equivalencia con Excel, cero, año sin datos, filtros y formularios: OK.');
