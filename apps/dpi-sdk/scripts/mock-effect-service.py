#!/usr/bin/env python3
"""Loopback synthetic effect fixture with transactional idempotency and a response barrier."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--port', type=int, default=4785)
    parser.add_argument('--hold-key', required=True)
    args = parser.parse_args()
    args.home.mkdir(parents=True, exist_ok=True, mode=0o700)

    def connect():
        db = sqlite3.connect(args.home / 'effects.sqlite', timeout=10, isolation_level=None)
        db.execute('PRAGMA synchronous=FULL')
        return db

    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS effects (key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, receipt TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, key TEXT NOT NULL, outcome TEXT NOT NULL, at REAL NOT NULL)')

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, value):
            body = json.dumps(value).encode()
            try:
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if self.path != '/health':
                return self.reply(404, {'error': 'not found'})
            self.reply(200, {'status': 'ready', 'synthetic': True})

        def do_POST(self):
            if self.path != '/effects':
                return self.reply(404, {'error': 'not found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 65536:
                    raise ValueError('Invalid content length')
                body = json.loads(self.rfile.read(length))
                key = body['idempotencyKey']
                payload = body['payload']
                if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', key) or not isinstance(payload, dict):
                    raise ValueError('Invalid effect request')
                canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            except (ValueError, KeyError, TypeError):
                return self.reply(400, {'error': 'Invalid effect request'})
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT payload_hash, receipt FROM effects WHERE key=?', (key,)).fetchone()
                if row and row[0] != digest:
                    outcome, status, receipt = 'CONFLICT', 409, {'error': 'Idempotency key belongs to different content'}
                elif row:
                    outcome, status, receipt = 'REPLAY', 200, json.loads(row[1])
                else:
                    outcome, status = 'CREATED', 200
                    receipt = {'effectId': str(uuid.uuid4()), 'idempotencyKey': key, 'payloadHash': digest, 'payload': payload, 'synthetic': True}
                    db.execute('INSERT INTO effects VALUES (?,?,?)', (key, digest, json.dumps(receipt)))
                attempt = db.execute('INSERT INTO attempts(key,outcome,at) VALUES (?,?,?)', (key, outcome, time.time())).lastrowid
                db.execute('COMMIT')
            if outcome == 'CREATED' and key == args.hold_key:
                marker = {'attemptId': attempt, 'receipt': receipt, 'phase': 'effect_committed_response_not_sent'}
                temporary = args.home / 'COMMITTED.tmp'
                temporary.write_text(json.dumps(marker, indent=2))
                temporary.replace(args.home / 'COMMITTED.json')
                deadline = time.monotonic() + 180
                while not (args.home / 'RELEASE').exists() and time.monotonic() < deadline:
                    time.sleep(.1)
                if not (args.home / 'RELEASE').exists():
                    return self.reply(504, {'error': 'Response barrier timed out; retry with the identical key'})
            self.reply(status, {'receipt': receipt, 'outcome': outcome, 'attemptId': attempt})

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True
    print('Synthetic effect fixture ready on loopback', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
