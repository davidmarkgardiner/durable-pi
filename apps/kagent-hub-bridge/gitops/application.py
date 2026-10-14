"""Synthetic checkout, with the same request failing only in image v2."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.environ.get('APP_VERSION', 'v1')


def checkout(customer):
    if VERSION == 'v2':
        # The regression assumes every guest has a loyalty account.
        discount = customer['loyalty']['discount']
    else:
        discount = customer.get('loyalty', {}).get('discount', 0)
    return {'order': 'synthetic-order', 'total': 20 - discount, 'version': VERSION}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        status, body = 200, {'healthy': True, 'version': VERSION}
        if self.path == '/checkout':
            try:
                body = checkout({'name': 'Guest'})
            except KeyError as error:
                status, body = 500, {'error': 'KeyError', 'message': str(error), 'version': VERSION,
                    'route': '/checkout', 'customer': 'synthetic guest'}
        print(json.dumps({'severity': 'ERROR' if status == 500 else 'INFO', 'service': 'lumen-checkout',
            'method': 'GET', 'route': self.path, 'status': status, **body}), flush=True)
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
