import http.server
import logging
import os
import time
import urllib.parse
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
import requests

EXPORTER_HOST = os.getenv('EXPORTER_HOST', '0.0.0.0')
EXPORTER_PORT = int(os.getenv('EXPORTER_PORT', '9138'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
DEFAULT_TIMEOUT = int(os.getenv('DEFAULT_TIMEOUT', '10'))
MAX_TIMEOUT = int(os.getenv('MAX_TIMEOUT', '300'))
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '8192'))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProbeHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info("%s - %s" % (self.address_string(), format % args))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if parsed.path == '/probe':
            self._handle_probe(params)
        elif parsed.path == '/':
            self._handle_index()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_index(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h1>Download Speed Exporter</h1><p><a href="/probe?target=https://fsn1-speed.hetzner.com/100MB.bin&timeout=30">Example</a></p>')

    def _handle_probe(self, params):
        target = params.get('target', [None])[0]
        timeout = float(params.get('timeout', [str(DEFAULT_TIMEOUT)])[0])
        
        if not target:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing 'target' parameter")
            return

        if timeout > MAX_TIMEOUT:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Timeout exceeds maximum allowed ({MAX_TIMEOUT}s)".encode())
            return

        registry = CollectorRegistry()
        success = Gauge('probe_success', 'Probe success', registry=registry)
        duration = Gauge('probe_duration_seconds', 'Probe duration', registry=registry)
        speed = Gauge('download_speed_bytes_per_second', 'Download speed', registry=registry)
        size = Gauge('download_content_length_bytes', 'Content length', registry=registry)
        http_status = Gauge('probe_http_status_code', 'HTTP status code', registry=registry)
        
        start = time.time()
        bytes_downloaded = 0
        content_length = 0
        probe_success = False
        status_code = 0
        
        try:
            with requests.get(target, stream=True, timeout=timeout) as r:
                status_code = r.status_code
                r.raise_for_status()
                content_length = int(r.headers.get('Content-Length', 0))
                
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if time.time() - start > timeout:
                        raise requests.Timeout("Download timeout")
                    if chunk:
                        bytes_downloaded += len(chunk)
            probe_success = True
            elapsed = time.time() - start
            speed_mbps = (bytes_downloaded / elapsed * 8 / 1000000) if elapsed > 0 else 0
            logger.info(f"Probe success: {target} - {bytes_downloaded} bytes in {elapsed:.2f}s ({speed_mbps:.2f} Mbps)")
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
            logger.error(f"Probe failed: {target} - {e}")
        except Exception as e:
            logger.error(f"Probe failed: {target} - {e}")
        
        elapsed = time.time() - start
        download_speed = bytes_downloaded / elapsed if elapsed > 0 else 0
        
        success.set(1 if probe_success else 0)
        duration.set(elapsed)
        speed.set(download_speed)
        size.set(content_length)
        http_status.set(status_code)

        self.send_response(200)
        self.send_header('Content-Type', CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(generate_latest(registry))


if __name__ == '__main__':
    server = http.server.HTTPServer((EXPORTER_HOST, EXPORTER_PORT), ProbeHandler)
    logger.info(f"Starting exporter on {EXPORTER_HOST}:{EXPORTER_PORT}")
    logger.info(f"Configuration: DEFAULT_TIMEOUT={DEFAULT_TIMEOUT}s, MAX_TIMEOUT={MAX_TIMEOUT}s, CHUNK_SIZE={CHUNK_SIZE}, LOG_LEVEL={LOG_LEVEL}")
    server.serve_forever()
