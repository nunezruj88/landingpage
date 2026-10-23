import io
import json
import tempfile
import unittest
from pathlib import Path
import app


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = app.DB
        app.DB = Path(self.temp.name) / 'test.sqlite3'

    def tearDown(self):
        app.DB = self.previous
        self.temp.cleanup()

    def call(self, path='/api/projects', method='GET', payload=None, origin='http://localhost:8093', marker='1'):
        raw = json.dumps(payload or {}).encode()
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'HTTP_HOST': 'localhost:8093',
               'HTTP_ORIGIN': origin, 'HTTP_X_LANDING_REQUEST': marker, 'CONTENT_LENGTH': str(len(raw)), 'wsgi.input': io.BytesIO(raw)}
        result = {}
        def start(status, headers): result.update(status=status, headers=dict(headers))
        body = b''.join(app.application(env, start))
        result['body'] = json.loads(body) if result['headers']['Content-Type'].startswith('application/json') else body
        return result

    def payload(self, **extra):
        return dict(name='Casa', description='Mi panel de domótica', url='http://casa.local:8123', category='Domótica', icon='home', color='green') | extra

    def test_seeded_once_and_data_persists(self):
        project = self.call()['body']['projects'][0]
        self.assertEqual(project['name'], 'MVP Cervelló')
        self.assertEqual(project['url'], ':8083')
        self.assertEqual(self.call()['body']['projects'], [project])
        result = self.call(method='POST', payload=self.payload())
        self.assertEqual(result['status'], '201 Created')
        self.assertEqual(len(self.call()['body']['projects']), 2)

    def test_edit_revision_check_and_soft_delete_restore(self):
        project = self.call(method='POST', payload=self.payload())['body']['project']
        url = '/api/projects/' + project['id']
        changed = self.call(url, 'PATCH', self.payload(name='Mi casa', version=1))
        self.assertEqual(changed['body']['project']['version'], 2)
        self.assertEqual(self.call(url, 'PATCH', self.payload(version=1))['status'], '409 Conflict')
        self.assertEqual(self.call(url, 'DELETE', {'version': 2})['status'], '200 OK')
        self.assertEqual(len(self.call()['body']['projects']), 1)
        self.assertEqual(self.call(url+'/restore', 'POST')['status'], '200 OK')
        self.assertEqual(len(self.call()['body']['projects']), 2)
        self.assertEqual(self.call(url+'/restore', 'POST')['status'], '404 Not Found')

    def test_deleting_all_does_not_reseed(self):
        project = self.call()['body']['projects'][0]
        self.call('/api/projects/'+project['id'], 'DELETE', {'version': project['version']})
        self.assertEqual(self.call()['body']['projects'], [])

    def test_dangerous_urls_rejected_without_writes(self):
        self.call()
        for url in ['javascript:alert(1)', 'data:text/html,test', '//evil.example', 'file:///etc/passwd', 'http://user:secret@example.com', ':0', ':65536', 'http://host:bad', '/\\evil', 'https://example.com\n/path']:
            with self.subTest(url=url):
                self.assertEqual(self.call(method='POST', payload=self.payload(url=url))['status'], '400 Bad Request')
        self.assertEqual(len(self.call()['body']['projects']), 1)

    def test_relative_urls_and_local_ports(self):
        for url in ['/domotica', ':8123', 'https://example.com/a?b=c', 'http://192.168.1.20:8080']:
            with self.subTest(url=url):
                self.assertEqual(self.call(method='POST', payload=self.payload(url=url))['status'], '201 Created')

    def test_origin_and_request_marker_required(self):
        self.assertEqual(self.call(method='POST', payload=self.payload(), origin='https://outside.example')['status'], '403 Forbidden')
        self.assertEqual(self.call(method='POST', payload=self.payload(), marker='')['status'], '403 Forbidden')
        self.assertEqual(self.call()['body']['projects'][0]['name'], 'MVP Cervelló')

    def test_invalid_fields_and_unknown_resources(self):
        for extra in [dict(name=''), dict(name='x'*65), dict(icon='script'), dict(color='red'), dict(category=42)]:
            self.assertEqual(self.call(method='POST', payload=self.payload(**extra))['status'], '400 Bad Request')
        self.assertEqual(self.call('/api/projects/unknown', 'DELETE', {'version':1})['status'], '404 Not Found')
        self.assertEqual(self.call('/../../etc/passwd')['status'], '404 Not Found')

    def test_security_headers_and_static_files(self):
        for path in ['/', '/style.css', '/app.js', '/favicon.svg', '/health']:
            result = self.call(path)
            self.assertEqual(result['status'], '200 OK')
            self.assertEqual(result['headers']['X-Content-Type-Options'], 'nosniff')
            self.assertIn("frame-ancestors 'none'", result['headers']['Content-Security-Policy'])


if __name__ == '__main__':
    unittest.main()
