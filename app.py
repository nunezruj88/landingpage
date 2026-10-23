"""Small project launcher for an authenticated Nginx reverse proxy."""
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit
from wsgiref.simple_server import WSGIServer, make_server

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('LANDING_DB', ROOT / 'data' / 'landing.sqlite3'))
ICONS = {'basketball', 'globe', 'code', 'home', 'chart', 'folder', 'server', 'grid'}
COLORS = {'amber', 'blue', 'green', 'rose', 'violet'}


class RequestError(Exception):
    def __init__(self, message, status='400 Bad Request'):
        super().__init__(message)
        self.status = status


@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with con:
            con.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, url TEXT NOT NULL, category TEXT NOT NULL, icon TEXT NOT NULL, color TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, deleted INTEGER NOT NULL DEFAULT 0)')
            con.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            if con.execute("INSERT OR IGNORE INTO settings VALUES ('seeded', '1')").rowcount:
                con.execute('INSERT INTO projects (id,name,description,url,category,icon,color) VALUES (?,?,?,?,?,?,?)',
                            ('mvp-cervello', 'MVP Cervelló', 'Partidos, estadísticas de jugadores y clasificaciones. Todo el equipo, en números.', ':8083', 'Deportes', 'basketball', 'amber'))
        yield con
    finally:
        con.close()


def project_fields(payload):
    limits = {'name': 64, 'description': 220, 'url': 1000, 'category': 32, 'icon': 20, 'color': 20}
    values = {}
    for key, limit in limits.items():
        value = payload.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit:
            raise RequestError('Revisa la longitud de los campos del proyecto.')
        values[key] = value.strip()
    if not values['name'] or not values['url']:
        raise RequestError('El nombre y la dirección son obligatorios.')
    values['category'] = values['category'] or 'General'
    if values['icon'] not in ICONS or values['color'] not in COLORS:
        raise RequestError('Selecciona un icono y un color disponibles.')
    url = values['url']
    if any(ord(c) < 32 or ord(c) == 127 for c in url) or '\\' in url:
        raise RequestError('La dirección contiene caracteres no permitidos.')
    if re.fullmatch(r':\d{1,5}', url):
        if not 1 <= int(url[1:]) <= 65535:
            raise RequestError('El puerto debe estar entre 1 y 65535.')
    elif url.startswith('/') and not url.startswith('//'):
        pass
    else:
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                raise ValueError()
            parsed.port
        except ValueError:
            raise RequestError('Usa una dirección http:// o https://, una ruta /proyecto o un puerto :8083.')
    return values


def application(env, start_response):
    method, path = env.get('REQUEST_METHOD', 'GET'), env.get('PATH_INFO', '/')
    headers = [('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
               ('Referrer-Policy', 'no-referrer'),
               ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")]

    def reply(value, status='200 OK', mime='application/json; charset=utf-8'):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        start_response(status, headers + [('Content-Type', mime), ('Content-Length', str(len(raw)))])
        return [raw]

    try:
        if path == '/health' and method == 'GET':
            return reply({'status': 'ok'})
        if method == 'GET' and path in ('/', '/app.js', '/style.css', '/favicon.svg'):
            name, mime = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                          '/style.css': ('style.css', 'text/css; charset=utf-8'), '/favicon.svg': ('favicon.svg', 'image/svg+xml')}[path]
            return reply((ROOT / 'static' / name).read_bytes(), mime=mime)
        if path == '/api/projects' and method == 'GET':
            with connect() as con:
                projects = [dict(row) for row in con.execute('SELECT * FROM projects WHERE deleted=0 ORDER BY name COLLATE NOCASE, id')]
            return reply({'projects': projects})
        if method in ('POST', 'PATCH', 'DELETE'):
            origin = env.get('HTTP_ORIGIN')
            if origin and (urlsplit(origin).netloc != env.get('HTTP_HOST') or urlsplit(origin).scheme not in ('http', 'https')):
                raise RequestError('Origen de la petición no permitido.', '403 Forbidden')
            if env.get('HTTP_X_LANDING_REQUEST') != '1':
                raise RequestError('Petición no permitida.', '403 Forbidden')
            length = int(env.get('CONTENT_LENGTH') or 0)
            if not 0 < length <= 16 * 1024:
                raise RequestError('Petición vacía o demasiado grande.', '413 Payload Too Large')
            try:
                payload = json.loads(env['wsgi.input'].read(length))
            except (ValueError, UnicodeError):
                raise RequestError('Petición inválida.')
            if not isinstance(payload, dict):
                raise RequestError('Petición inválida.')
            match = re.fullmatch(r'/api/projects/([a-z0-9-]{1,40})(/restore)?', path)
            if path == '/api/projects' and method == 'POST':
                fields = project_fields(payload)
                with connect() as con, con:
                    con.execute('BEGIN IMMEDIATE')
                    if con.execute('SELECT COUNT(*) FROM projects WHERE deleted=0').fetchone()[0] >= 100:
                        raise RequestError('El panel admite hasta 100 proyectos.')
                    project_id = uuid.uuid4().hex
                    con.execute('INSERT INTO projects (id,name,description,url,category,icon,color) VALUES (?,?,?,?,?,?,?)',
                                (project_id, *(fields[key] for key in ('name', 'description', 'url', 'category', 'icon', 'color'))))
                    project = dict(con.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
                return reply({'project': project}, '201 Created')
            if match:
                project_id, restore = match.groups()
                with connect() as con, con:
                    con.execute('BEGIN IMMEDIATE')
                    row = con.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
                    if not row or bool(row['deleted']) != bool(restore):
                        raise RequestError('No se encuentra este acceso.', '404 Not Found')
                    if restore and method == 'POST':
                        if con.execute('SELECT COUNT(*) FROM projects WHERE deleted=0').fetchone()[0] >= 100:
                            raise RequestError('El panel admite hasta 100 proyectos.')
                        con.execute('UPDATE projects SET deleted=0, version=version+1 WHERE id=?', (project_id,))
                    elif not restore and method in ('PATCH', 'DELETE'):
                        if payload.get('version') != row['version']:
                            raise RequestError('Este acceso ha cambiado en otro dispositivo. Cierra el formulario y vuelve a abrirlo.', '409 Conflict')
                        if method == 'DELETE':
                            con.execute('UPDATE projects SET deleted=1, version=version+1 WHERE id=?', (project_id,))
                        else:
                            fields = project_fields(payload)
                            con.execute('UPDATE projects SET name=?,description=?,url=?,category=?,icon=?,color=?,version=version+1 WHERE id=?',
                                        (*(fields[key] for key in ('name', 'description', 'url', 'category', 'icon', 'color')), project_id))
                    else:
                        raise RequestError('Operación no permitida.', '405 Method Not Allowed')
                    project = dict(con.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
                return reply({'project': project})
        return reply({'error': 'Página no encontrada.'}, '404 Not Found')
    except RequestError as exc:
        return reply({'error': str(exc)}, exc.status)
    except (ValueError, TypeError):
        return reply({'error': 'Petición inválida.'}, '400 Bad Request')
    except Exception:
        import traceback
        traceback.print_exc()
        return reply({'error': 'No se ha podido completar la operación. Inténtalo de nuevo.'}, '500 Internal Server Error')


class ThreadingServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


if __name__ == '__main__':
    port = int(os.environ.get('LANDING_PORT', '8093'))
    with connect():
        pass
    print(f'Landing page: http://127.0.0.1:{port}', flush=True)
    with make_server('127.0.0.1', port, application, server_class=ThreadingServer) as server:
        server.serve_forever()
