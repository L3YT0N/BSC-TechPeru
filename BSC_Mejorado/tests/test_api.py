"""Pruebas de integración reales contra HTTP y una base SQLite temporal."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import zipfile
import xml.etree.ElementTree as ET
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer

spec=importlib.util.spec_from_file_location('bsc_server',Path(__file__).resolve().parents[1]/'backend/server.py')
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)

class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();app.DB=Path(cls.tmp.name)/'test.sqlite3'
        os.environ['BSC_INITIAL_PASSWORD']='Prueba-BSC-2025!';app.init_db()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);cls.server.attempts={}
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()

    def setUp(self):
        self.client=build_opener(HTTPCookieProcessor(CookieJar()));self.csrf='';self.revision=''
        code,data=self.request('login','POST',{'email':'admin@techperu.local','password':'Prueba-BSC-2025!'})
        self.assertEqual(code,200);self.csrf=data['csrf'];self.refresh()

    def request(self,path,method='GET',body=None,headers=None):
        h={'Content-Type':'application/json','X-CSRF-Token':self.csrf,'If-Match':self.revision};h.update(headers or {})
        if body is not None and not isinstance(body,bytes):body=json.dumps(body).encode()
        req=Request(self.url+'/api/'+path,data=body,method=method,headers=h)
        try:
            with self.client.open(req) as r:return r.status,json.loads(r.read())
        except HTTPError as e:return e.code,json.loads(e.read())

    def refresh(self):
        code,self.data=self.request('state');self.assertEqual(code,200);self.revision=str(self.data['revision'])

    def test_seed_and_formulas(self):
        self.assertEqual(len(self.data['kpis']),36);self.assertEqual(len(self.data['objectives']),12)
        self.assertTrue(all(len(k['measurements'])>=1 for k in self.data['kpis']))
        k=next(k for k in self.data['kpis'] if k['id']=='KPI-01')
        self.assertAlmostEqual(app.achievement(k,16.5),91.6666667,places=5)
        self.assertEqual(app.achievement(k,0),0);self.assertIsNone(app.achievement(k,None))
        inverse={'direction':'menor','target':2}
        self.assertEqual(app.achievement(inverse,0),100);self.assertAlmostEqual(app.achievement(inverse,2.8),71.4285714,places=5)

    def test_unauthenticated_and_passwords(self):
        empty=build_opener()
        with self.assertRaises(HTTPError) as r:empty.open(self.url+'/api/state')
        self.assertEqual(r.exception.code,401)
        with app.connect() as c:
            stored=c.execute("SELECT password FROM users WHERE id='u1'").fetchone()[0]
        self.assertNotIn('Prueba-BSC',stored);self.assertTrue(app.password_ok('Prueba-BSC-2025!',stored))
        self.assertNotIn('password',json.dumps(self.data))

    def test_csrf(self):
        code,_=self.request('objectives','POST',{},headers={'X-CSRF-Token':''});self.assertEqual(code,403)

    def test_concurrency(self):
        code,_=self.request('objectives','POST',{},headers={'If-Match':'-1'});self.assertEqual(code,409)

    def test_measurement_persistence_duplicate_and_year(self):
        payload=dict(kpiId='KPI-01',period='2026-01',date='2026-02-01',value=18,notes='Prueba')
        code,r=self.request('measurements','POST',payload);self.assertEqual(code,200,r);uid=r['id']
        self.refresh();k=next(k for k in self.data['kpis'] if k['id']=='KPI-01');self.assertEqual(k['current'],18)
        self.assertEqual(self.request('measurements','POST',payload)[0],409)
        self.refresh();payload['value']=0;self.assertEqual(self.request('measurements/'+uid,'PUT',payload)[0],200)
        self.refresh();k=next(k for k in self.data['kpis'] if k['id']=='KPI-01');self.assertEqual(k['current'],0)
        self.assertEqual(self.request('measurements/'+uid,'DELETE',{})[0],200)
        self.refresh();self.assertGreater(len(self.data['audit']),1)

    def test_invalid_and_referential_integrity(self):
        self.assertEqual(self.request('objectives/OBJ-F1','DELETE',{})[0],409)
        k=next(k for k in self.data['kpis'] if k['id']=='KPI-01');k['target']=0
        self.assertEqual(self.request('kpis/KPI-01','PUT',k)[0],400)
        bad=dict(kpiId='KPI-01',period='2025-99',date='2025-12-31',value=1)
        self.assertEqual(self.request('measurements','POST',bad)[0],400)

    def test_role_enforced_by_server(self):
        code,r=self.request('login','POST',{'email':'responsable@techperu.local','password':'Prueba-BSC-2025!'})
        self.csrf=r['csrf'];self.refresh()
        self.assertEqual(self.data['users'],[]);self.assertEqual(self.data['audit'],[])
        self.assertEqual(self.request('objectives','POST',{})[0],403)
        payload=dict(kpiId='KPI-01',period='2026-02',date='2026-02-01',value=5)
        self.assertEqual(self.request('measurements','POST',payload)[0],403)
        payload['kpiId']='KPI-19';code,r=self.request('measurements','POST',payload);self.assertEqual(code,200,r)

    def test_user_creation_and_real_login(self):
        u=dict(name='Usuario prueba',email='prueba@techperu.local',role='Gerente',area='Comercial',password='Clave-prueba-123!')
        self.assertEqual(self.request('users','POST',u)[0],200)
        self.assertEqual(self.request('login','POST',{'email':u['email'],'password':u['password']})[0],200)

    def test_import_excel_and_rollback(self):
        path=Path(__file__).resolve().parents[1]/'docs/BSC_TechPeru_Mejorado_2025.xlsx'
        if not path.exists():self.skipTest('Excel aún no empaquetado')
        raw=path.read_bytes();records=app.read_xlsx(raw);self.assertEqual(len(records),36)
        code,r=self.request('import-xlsx','POST',raw,{'Content-Type':'application/octet-stream'});self.assertEqual(code,200,r)
        self.refresh();before=self.data['revision']
        code,_=self.request('import-xlsx','POST',b'archivo invalido');self.assertEqual(code,400)
        self.refresh();self.assertEqual(before,self.data['revision'])
        # Una fila válida seguida de otra inválida debe revertir también la primera.
        data_before=json.dumps(self.data['kpis'],sort_keys=True)
        output=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as original,zipfile.ZipFile(output,'w') as changed:
            for item in original.infolist():
                content=original.read(item.filename)
                if item.filename.startswith('xl/worksheets/') and item.filename.endswith('.xml'):
                    root=ET.fromstring(content);ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    cells={c.get('r'):c for c in root.findall('.//s:sheetData/s:row/s:c',ns)}
                    if 'J4' in cells and 'K4' in cells and 'F5' in cells and cells['F4'].find('s:v',ns) is not None and cells['F5'].find('s:v',ns) is not None:
                        cells['F4'].find('s:v',ns).text='999'
                        cells['F5'].find('s:v',ns).text='-1'
                        content=ET.tostring(root)
                changed.writestr(item,content)
        code,result=self.request('import-xlsx','POST',output.getvalue());self.assertEqual(code,400,result)
        self.refresh();self.assertEqual(self.data['revision'],before)
        self.assertEqual(json.dumps(self.data['kpis'],sort_keys=True),data_before)

    def test_logout(self):
        self.assertEqual(self.request('logout','POST',{})[0],200)
        self.assertEqual(self.request('state')[0],401)

if __name__=='__main__':unittest.main(verbosity=2)
