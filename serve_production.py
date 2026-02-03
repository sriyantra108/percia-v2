import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(SCRIPT_DIR, 'src', 'web-interface')

if not os.path.isdir(APP_DIR):
    print('ERROR: App directory not found: ' + APP_DIR)
    sys.exit(1)

sys.path.insert(0, APP_DIR)

try:
    from app import app
except ImportError as e:
    print('ERROR: Could not import Flask app: ' + str(e))
    sys.exit(1)
except RuntimeError as e:
    print('CONFIGURATION ERROR: ' + str(e))
    sys.exit(1)

try:
    from waitress import serve
except ImportError:
    print('ERROR: Waitress not installed. Run: pip install waitress')
    sys.exit(1)

host = (os.environ.get('PERCIA_FLASK_HOST', '127.0.0.1') or '127.0.0.1').strip()
port_raw = (os.environ.get('PERCIA_FLASK_PORT', '5000') or '5000').strip()
try:
    port = int(port_raw)
except ValueError:
    print('ERROR: PERCIA_FLASK_PORT invalid: ' + repr(port_raw))
    sys.exit(1)
if not (1 <= port <= 65535):
    print('ERROR: PERCIA_FLASK_PORT out of range: ' + str(port))
    sys.exit(1)

THREADS = int(os.environ.get('PERCIA_WAITRESS_THREADS', '1'))

if __name__ == '__main__':
    sep = '=' * 60
    print(sep)
    print('  PERCIA v2.0 - Production Server (Waitress WSGI)')
    print(sep)
    print('  Host:    ' + host)
    print('  Port:    ' + str(port))
    print('  Threads: ' + str(THREADS))
    print('  Debug:   OFF (production mode)')
    print('  URL:     http://' + host + ':' + str(port))
    print(sep)
    print()
    print('Press Ctrl+C to stop the server.')
    print()
    try:
        serve(
            app,
            host=host,
            port=port,
            threads=THREADS,
            url_scheme='http',
            ident='PERCIA v2.0',
            connection_limit=100,
            channel_timeout=120,
            recv_bytes=65536,
            expose_tracebacks=False,
        )
    except KeyboardInterrupt:
        print('Server stopped by user.')
    except Exception as e:
        print('FATAL: Server crashed: ' + str(e))
        sys.exit(1)
