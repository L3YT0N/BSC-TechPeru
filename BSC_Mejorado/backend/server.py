"""BSC académico: API REST y archivos estáticos, Python 3.10+, sin dependencias."""
import argparse
import csv
import hashlib
import hmac
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get('BSC_DB', str(ROOT / 'data/bsc.sqlite3')))
FRONT = ROOT / 'frontend'
PERSPECTIVES = ('financiera', 'clientes', 'procesos', 'aprendizaje')
ROLES = ('Administrador', 'Gerente', 'Responsable de indicadores')
MAX_BODY = 2_000_000

def connect():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()

def password_ok(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS objectives (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS kpis (id TEXT PRIMARY KEY, objective_id TEXT NOT NULL REFERENCES objectives(id) ON DELETE RESTRICT, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS measurements (id TEXT PRIMARY KEY, kpi_id TEXT NOT NULL REFERENCES kpis(id) ON DELETE CASCADE, period TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(kpi_id,period));
        CREATE TABLE IF NOT EXISTS initiatives (id TEXT PRIMARY KEY, objective_id TEXT NOT NULL REFERENCES objectives(id) ON DELETE RESTRICT, kpi_id TEXT REFERENCES kpis(id) ON DELETE SET NULL, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, csrf TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, user TEXT NOT NULL, action TEXT NOT NULL, entity TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
            return
        password = os.environ.get('BSC_INITIAL_PASSWORD') or secrets.token_urlsafe(12)
        for uid, name, email, role, area in [
            ('u1', 'Administrador TechPeru', 'admin@techperu.local', ROLES[0], 'Gerencia'),
            ('u2', 'Carlos Ruiz', 'gerente@techperu.local', ROLES[1], 'Comercial'),
            ('u3', 'María Torres', 'responsable@techperu.local', ROLES[2], 'Operaciones')]:
            u = dict(id=uid, name=name, email=email, role=role, area=area)
            c.execute('INSERT INTO users VALUES (?,?,?,?)', (uid, email, password_hash(password), json.dumps(u)))
        seed = json.loads((ROOT / 'data/seed.json').read_text(encoding='utf-8'))
        for o in seed['objectives']:
            c.execute('INSERT INTO objectives VALUES (?,?)', (o['id'], json.dumps(o)))
        for k in seed['kpis']:
            k = dict(k); measurements = k.pop('measurements'); k.pop('current', None)
            c.execute('INSERT INTO kpis VALUES (?,?,?)', (k['id'], k['objectiveId'], json.dumps(k)))
            for m in measurements:
                c.execute('INSERT INTO measurements VALUES (?,?,?,?)', (m['id'], k['id'], m['period'], json.dumps(m)))
        for i in seed['initiatives']:
            c.execute('INSERT INTO initiatives VALUES (?,?,?,?)', (i['id'], i['objectiveId'], i['kpiId'], json.dumps(i)))
        c.execute('INSERT INTO meta VALUES (?,?)', ('revision', '1'))
        c.execute('INSERT INTO audit(user,action,entity,detail) VALUES (?,?,?,?)', ('Sistema','Inicialización','BSC','36 resultados académicos importados; no hay historial mensual inventado.'))
        print('\nPrimera ejecución. Contraseña inicial de los tres usuarios:', password, flush=True)
        print('Usuarios: admin@techperu.local / gerente@techperu.local / responsable@techperu.local\n', flush=True)

def number(v, label, low=None, high=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(label + ': ingresa un número válido.')
    if low is not None and v < low or high is not None and v > high:
        raise ValueError(label + ': fuera del intervalo permitido.')
    return v

def text(data, key, limit=500, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > limit or required and not value.strip():
        raise ValueError('Revisa el campo ' + key + '.')
    return value.strip()

def achievement(k, value):
    if value is None:
        return None
    target = k['target']
    if k['direction'] == 'menor':
        return 100.0 if value <= target else max(0, target / value * 100)
    return min(150, max(0, value / target * 100))

def avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None

def snapshot(c):
    objectives = [json.loads(r['data']) for r in c.execute('SELECT data FROM objectives ORDER BY id')]
    kpis = []
    for r in c.execute('SELECT * FROM kpis ORDER BY id'):
        k = json.loads(r['data'])
        k['perspective'] = next(o['perspective'] for o in objectives if o['id']==k['objectiveId'])
        k['measurements'] = [json.loads(m['data']) for m in c.execute('SELECT data FROM measurements WHERE kpi_id=? ORDER BY period', (r['id'],))]
        k['current'] = k['measurements'][-1]['value'] if k['measurements'] else None
        kpis.append(k)
    return dict(company='TechPeru SAC', year='2025', objectives=objectives, kpis=kpis,
        initiatives=[dict(json.loads(r['data']), kpiId=r['kpi_id'] or '') for r in c.execute('SELECT * FROM initiatives ORDER BY id')],
        users=[json.loads(r['data']) for r in c.execute('SELECT data FROM users ORDER BY id')],
        audit=[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')],
        revision=int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]))

def validate(c, entity, d, uid, user):
    if entity == 'measurements':
        kid = text(d, 'kpiId', 80); row = c.execute('SELECT data FROM kpis WHERE id=?', (kid,)).fetchone()
        if not row: raise ValueError('Indicador no encontrado.')
        k = json.loads(row['data'])
        if user['role'] == ROLES[2] and k['area'] != user['area']:
            raise PermissionError('Solo puedes registrar resultados de tu área.')
        period = text(d, 'period', 7); day = text(d, 'date', 10)
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', period): raise ValueError('Período inválido.')
        date.fromisoformat(day)
        # La fecha puede ser posterior al cierre; el período identifica el resultado.
        return dict(id=uid, kpiId=kid, period=period, date=day, value=number(d.get('value'), 'Resultado', -100 if k['unit']=='pts' else 0), responsible=user['name'], notes=text(d,'notes',2000,False))
    if entity == 'users':
        email = text(d,'email',200).lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ValueError('Correo inválido.')
        role = text(d,'role',80)
        if role not in ROLES: raise ValueError('Rol inválido.')
        return dict(id=uid,name=text(d,'name',150),email=email,role=role,area=text(d,'area',120))
    name=text(d,'name',250)
    if entity == 'objectives':
        p=text(d,'perspective',30)
        if p not in PERSPECTIVES: raise ValueError('Perspectiva inválida.')
        priority=text(d,'priority',20); status=text(d,'status',30)
        if priority not in ('Alta','Media','Baja') or status not in ('Activo','En revisión','Inactivo'): raise ValueError('Estado o prioridad inválidos.')
        return dict(id=uid,name=name,perspective=p,description=text(d,'description',2000,False),owner=text(d,'owner',150),priority=priority,status=status)
    obj=text(d,'objectiveId',80); row=c.execute('SELECT data FROM objectives WHERE id=?',(obj,)).fetchone()
    if not row: raise ValueError('Selecciona un objetivo existente.')
    o=json.loads(row['data'])
    if entity == 'kpis':
        direction=text(d,'direction',10)
        if direction not in ('mayor','menor'): raise ValueError('Sentido inválido.')
        target=number(d.get('target'),'Meta',0)
        if direction=='mayor' and target==0: raise ValueError('Para mayor es mejor, la meta debe ser mayor que cero.')
        return dict(id=uid,name=name,objectiveId=obj,perspective=o['perspective'],unit=text(d,'unit',40),target=target,direction=direction,owner=text(d,'owner',150),area=text(d,'area',120),frequency=text(d,'frequency',50),description=text(d,'description',2000,False),formula='Meta / resultado × 100' if direction=='menor' else 'Resultado / meta × 100')
    kid=text(d,'kpiId',80,False)
    if kid and not c.execute('SELECT id FROM kpis WHERE id=? AND objective_id=?',(kid,obj)).fetchone(): raise ValueError('El indicador debe pertenecer al objetivo seleccionado.')
    start=text(d,'start',10); end=text(d,'end',10); date.fromisoformat(start); date.fromisoformat(end)
    if end < start: raise ValueError('La fecha final debe ser posterior a la inicial.')
    status=text(d,'status',30)
    if status not in ('Planificada','En ejecución','En riesgo','Finalizada','Cancelada'): raise ValueError('Estado inválido.')
    progress=number(d.get('progress'),'Avance',0,100)
    if status=='Finalizada' and progress!=100: raise ValueError('Una iniciativa finalizada debe tener 100% de avance.')
    return dict(id=uid,name=name,objectiveId=obj,kpiId=kid,owner=text(d,'owner',150),area=text(d,'area',120),start=start,end=end,budget=number(d.get('budget'),'Presupuesto',0),progress=progress,status='Finalizada' if progress==100 else status,description=text(d,'description',2000,False))

def read_xlsx(raw):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist())>20_000_000: raise ValueError('Excel demasiado grande.')
        strings=[''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)] if 'xl/sharedStrings.xml' in z.namelist() else []
        sheets=ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets',ns)
        target=next((s for s in sheets if 'BSC Completo' in s.attrib['name']),None)
        if target is None: raise ValueError('Falta la hoja BSC Completo.')
        rid=target.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        relationships=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        path=next(r.attrib['Target'] for r in relationships if r.attrib['Id']==rid)
        path=path.lstrip('/') if path.startswith('/') else 'xl/'+path
        records=[]
        for row in ET.fromstring(z.read(path)).findall('s:sheetData/s:row',ns):
            vals={}
            for cell in row:
                v=cell.find('s:v',ns); value=v.text if v is not None else ''
                if cell.attrib.get('t')=='s': value=strings[int(value)]
                elif cell.attrib.get('t')=='inlineStr': value=''.join(cell.find('s:is',ns).itertext())
                vals[re.sub(r'\d','',cell.attrib['r'])]=value
            if vals.get('J','').startswith('KPI-'):
                records.append((vals['J'],vals.get('F',''),vals.get('G',''),vals.get('K','')))
        if not records: raise ValueError('Utiliza el Excel mejorado: necesita códigos en la columna J.')
        return records

class Handler(BaseHTTPRequestHandler):
    server_version='BSC/1.0'
    def log_message(self, fmt, *args):
        # No registrar credenciales, cookies o cuerpos de petición.
        pass

    def send(self, status, data=None, headers=None, raw=None, mime='application/json; charset=utf-8'):
        body=raw if raw is not None else json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-store'); self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)

    def body(self, binary=False):
        size=int(self.headers.get('Content-Length','0'))
        if size>MAX_BODY: raise ValueError('Archivo demasiado grande (máximo 2 MB).')
        raw=self.rfile.read(size)
        if binary: return raw
        data=json.loads(raw or b'{}')
        if not isinstance(data,dict): raise ValueError('Se esperaba un objeto JSON.')
        return data

    def auth(self,c,mutate=False):
        cookie=SimpleCookie(); cookie.load(self.headers.get('Cookie',''))
        token=cookie['bsc_session'].value if 'bsc_session' in cookie else ''
        r=c.execute('SELECT s.csrf,u.data FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not r: raise PermissionError('Inicia sesión.')
        if mutate and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),r['csrf']): raise PermissionError('Sesión de formulario inválida. Recarga la página.')
        return json.loads(r['data']),r['csrf']

    def do_GET(self):
        try:
            path=urlsplit(self.path).path
            if path.startswith('/api/'):
                with connect() as c:
                    u,csrf=self.auth(c)
                    if path=='/api/me': return self.send(200,dict(user=u,csrf=csrf))
                    if path=='/api/state':
                        data=snapshot(c)
                        if u['role']!=ROLES[0]: data['audit']=[]; data['users']=[]
                        return self.send(200,data,{'ETag':str(data['revision'])})
                    return self.send(404,{'error':'Ruta no encontrada.'})
            if path=='/': path='/index.html'
            f=(FRONT/path.lstrip('/')).resolve()
            if not f.is_relative_to(FRONT.resolve()) or not f.is_file(): return self.send(404,{'error':'Archivo no encontrado.'})
            mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8'}.get(f.suffix,'application/octet-stream')
            self.send(200,raw=f.read_bytes(),mime=mime)
        except PermissionError as e: self.send(401,{'error':str(e)})
        except Exception: self.send(500,{'error':'No se pudo cargar el recurso.'})

    def do_POST(self): self.mutate('POST')
    def do_PUT(self): self.mutate('PUT')
    def do_DELETE(self): self.mutate('DELETE')

    def mutate(self,method):
        try:
            path=urlsplit(self.path).path
            origin=self.headers.get('Origin')
            if origin and origin not in ('http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')): raise PermissionError('Origen de petición inválido.')
            with connect() as c:
                if path=='/api/login' and method=='POST':
                    d=self.body(); email=text(d,'email',200).lower(); password=text(d,'password',200)
                    # Límite por origen para intentos fallidos, sin registrar la contraseña.
                    ip=self.client_address[0]; attempts=self.server.attempts.get(ip,[]); attempts=[t for t in attempts if t>time.time()-300]
                    if len(attempts)>=15: return self.send(429,{'error':'Demasiados intentos. Espera cinco minutos.'})
                    r=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                    if not r or not password_ok(password,r['password']):
                        self.server.attempts[ip]=attempts+[time.time()]; return self.send(401,{'error':'Usuario o contraseña incorrectos.'})
                    self.server.attempts.pop(ip,None)
                    token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                    c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
                    c.execute('INSERT INTO sessions VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),r['id'],csrf,time.time()+8*3600))
                    return self.send(200,dict(user=json.loads(r['data']),csrf=csrf),{'Set-Cookie':f'bsc_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
                u,csrf=self.auth(c,True)
                if path=='/api/logout':
                    cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));token=cookie['bsc_session'].value
                    c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
                    return self.send(200,{'ok':True},{'Set-Cookie':'bsc_session=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/'})
                if path=='/api/password' and method=='POST':
                    d=self.body(); old=text(d,'oldPassword',200); new=text(d,'newPassword',200)
                    r=c.execute('SELECT password FROM users WHERE id=?',(u['id'],)).fetchone()
                    if not password_ok(old,r['password']): raise ValueError('La contraseña actual es incorrecta.')
                    if len(new)<10: raise ValueError('Usa al menos 10 caracteres.')
                    c.execute('UPDATE users SET password=? WHERE id=?',(password_hash(new),u['id']))
                    c.execute('DELETE FROM sessions WHERE user_id=? AND csrf<>?',(u['id'],csrf))
                    return self.send(200,{'ok':True})
                if path=='/api/import-xlsx' and method=='POST':
                    if u['role']!=ROLES[0]: raise PermissionError('Solo el administrador puede importar el Excel.')
                    records=read_xlsx(self.body(True))
                    c.execute('BEGIN IMMEDIATE')
                    revision=str(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
                    if self.headers.get('If-Match')!=revision: return self.send(409,{'error':'Otra sesión cambió los datos. Actualiza la pantalla antes de importar.'})
                    # Una transacción: cualquier error revierte toda la importación.
                    seen=set()
                    for kid,target,current,direction in records:
                        if kid in seen: raise ValueError('Código duplicado en Excel: '+kid)
                        seen.add(kid); row=c.execute('SELECT data FROM kpis WHERE id=?',(kid,)).fetchone()
                        if not row: raise ValueError('Código no encontrado: '+kid)
                        k=json.loads(row['data']); k['target']=float(target); k['direction']={'Mayor':'mayor','Menor':'menor'}.get(direction,direction)
                        k=validate(c,'kpis',k,kid,u)
                        c.execute('UPDATE kpis SET data=? WHERE id=?',(json.dumps(k),kid))
                        if current=='':
                            c.execute('DELETE FROM measurements WHERE kpi_id=? AND period=?',(kid,'2025-12'))
                        else:
                            m=validate(c,'measurements',dict(kpiId=kid,period='2025-12',date='2025-12-31',value=float(current),notes='Importado desde el Excel mejorado.'),'M-'+kid+'-2025-12',u)
                            c.execute('INSERT INTO measurements VALUES (?,?,?,?) ON CONFLICT(kpi_id,period) DO UPDATE SET data=excluded.data',(m['id'],kid,m['period'],json.dumps(m)))
                    self.audit(c,u,'Importación','Excel',str(len(records))+' indicadores actualizados, período 2025-12')
                    return self.send(200,{'count':len(records)})
                parts=path.strip('/').split('/')
                if len(parts) not in (2,3) or parts[0]!='api' or parts[1] not in ('objectives','kpis','measurements','initiatives','users'): return self.send(404,{'error':'Ruta no encontrada.'})
                entity=parts[1]; uid=parts[2] if len(parts)==3 else None
                if entity=='users' and u['role']!=ROLES[0] or entity!='measurements' and u['role']==ROLES[2]: raise PermissionError('Tu rol no permite esta acción.')
                c.execute('BEGIN IMMEDIATE')
                revision=str(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
                if self.headers.get('If-Match')!=revision: return self.send(409,{'error':'Otra sesión cambió los datos. Actualiza la pantalla antes de guardar.'})
                if method in ('PUT','DELETE'):
                    if not uid or not c.execute(f'SELECT id FROM {entity} WHERE id=?',(uid,)).fetchone(): return self.send(404,{'error':'Registro no encontrado.'})
                if method=='DELETE':
                    if entity=='users' and uid in ('u1',u['id']): raise ValueError('No puedes eliminar al administrador principal o tu propia cuenta.')
                    if entity=='measurements' and u['role']==ROLES[2]: raise PermissionError('Solo un gerente o administrador puede eliminar mediciones.')
                    c.execute(f'DELETE FROM {entity} WHERE id=?',(uid,))
                else:
                    d=self.body();uid=uid or {'objectives':'OBJ','kpis':'KPI','measurements':'M','initiatives':'INI','users':'U'}[entity]+'-'+secrets.token_hex(6)
                    clean=validate(c,entity,d,uid,u)
                    if entity=='users':
                        previous=c.execute('SELECT data FROM users WHERE id=?',(uid,)).fetchone()
                        if uid=='u1' and clean['role']!=ROLES[0]: raise ValueError('El administrador principal debe conservar su rol.')
                        if method=='POST':
                            password=text(d,'password',200)
                            if len(password)<10: raise ValueError('Usa una contraseña de al menos 10 caracteres.')
                            c.execute('INSERT INTO users VALUES (?,?,?,?)',(uid,clean['email'],password_hash(password),json.dumps(clean)))
                        else: c.execute('UPDATE users SET email=?,data=? WHERE id=?',(clean['email'],json.dumps(clean),uid))
                    else:
                        cols=['id']; values=[uid]
                        if entity in ('kpis','initiatives'): cols+=['objective_id'];values+=[clean['objectiveId']]
                        if entity in ('measurements','initiatives'): cols+=['kpi_id'];values+=[clean['kpiId'] or None]
                        if entity=='measurements': cols+=['period'];values+=[clean['period']]
                        cols+=['data'];values+=[json.dumps(clean)]
                        if method=='POST': c.execute(f'INSERT INTO {entity} ({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})',values)
                        else: c.execute(f'UPDATE {entity} SET '+','.join(col+'=?' for col in cols[1:])+' WHERE id=?',values[1:]+[uid])
                self.audit(c,u,method,entity,uid)
                self.send(200,dict(ok=True,id=uid))
        except PermissionError as e: self.send(403,{'error':str(e)})
        except sqlite3.IntegrityError as e:
            message='No se puede eliminar: existen registros asociados.' if 'FOREIGN KEY' in str(e) else 'Ya existe ese correo o una medición para el mismo indicador y período.'
            self.send(409,{'error':message})
        except (ValueError,KeyError,TypeError,zipfile.BadZipFile,ET.ParseError) as e: self.send(400,{'error':str(e) or 'Datos inválidos.'})
        except Exception: self.send(500,{'error':'No se pudo guardar. No se realizaron cambios.'})

    def audit(self,c,user,action,entity,detail):
        c.execute('INSERT INTO audit(user,action,entity,detail) VALUES (?,?,?,?)',(user['name'],action,entity,detail))
        c.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);parser.add_argument('--host',default='127.0.0.1');args=parser.parse_args()
    init_db();server=ThreadingHTTPServer((args.host,args.port),Handler);server.attempts={}
    print(f'BSC disponible en http://{args.host}:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nServidor detenido.')

if __name__=='__main__': main()
