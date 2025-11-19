# Download Speed Exporter

An exporter for monitoring file download speeds. When you request the `/probe` endpoint, the exporter downloads a file from the URL and returns download statistics.

## Metrics

- `probe_success` - download success (1 = success, 0 = error)
- `probe_duration_seconds` - download time
- `probe_http_status_code` - HTTP status code (200, 404, 500...)
- `download_speed_bytes_per_second` - download speed in bytes/sec
- `download_content_length_bytes` - file size (from Content-Length)

## Running

> [!NOTE]
> [WIP] Public Docker image

### Docker Compose (recommended)

Create config file:
```bash
cp .env.example .env
```

Start the exporter:
```bash
docker compose up -d
```

The exporter will be available at http://localhost:9138

### Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python exporter.py
```

### Docker

```bash
docker build -t download-speed-exporter .
docker run -p 9138:9138 download-speed-exporter
```

## Usage

Manual test:
```bash
curl "http://localhost:9138/probe?target=http://speedtest.tele2.net/10MB.zip&timeout=30"
```

Example output:
```
probe_success 1.0
probe_duration_seconds 0.758
probe_http_status_code 200.0
download_speed_bytes_per_second 1.38e+06
download_content_length_bytes 1.048576e+06
```

## Environment Variables

The exporter supports configuration via environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `EXPORTER_HOST` | Host to bind to | `0.0.0.0` |
| `EXPORTER_PORT` | Port | `9138` |
| `LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `DEFAULT_TIMEOUT` | Default timeout (seconds) | `10` |
| `MAX_TIMEOUT` | Maximum timeout (seconds) | `300` |
| `CHUNK_SIZE` | Download chunk size (bytes) | `8192` |

## Prometheus/VictoriaMetrics Configuration

### Example configuration

```yaml
scrape_configs:
  - job_name: 'download-speed'
    scrape_interval: 10m
    scrape_timeout: 50s
    metrics_path: /probe
    params:
      timeout: ['40']
    static_configs:
      - targets:
          - http://speedtest.tele2.net/10MB.zip
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: <exporter_host>:9138
```

## Parameters

- `target` (required) - URL of the file to download
- `timeout` (optional, default `DEFAULT_TIMEOUT`) - download timeout in seconds

> [!NOTE]
> The `timeout` parameter in the request has priority over `DEFAULT_TIMEOUT`. If not specified, the value from the `DEFAULT_TIMEOUT` environment variable is used (default 10 seconds).

> [!IMPORTANT]
> `scrape_timeout` in Prometheus must be **larger** than the exporter's `timeout` parameter, otherwise Prometheus will cancel the request before the exporter returns metrics.

## Pros and Cons


### Recommendations

Incoming traffic is often free, but constantly loading the network is not recommended. Here are traffic usage calculations:

#### 30 MB file
| Interval | Downloads/day | Traffic/day | Traffic/week | Traffic/month |
|----------|--------------|-------------|--------------|---------------|
| 1 minute | 1440 | **43.2 GB** | **302.4 GB** | **1.3 TB** |
| 5 minutes | 288 | **8.64 GB** | **60.48 GB** | **259.2 GB** |
| 10 minutes | 144 | **4.32 GB** | **30.24 GB** | **129.6 GB** |
| 30 minutes | 48 | **1.44 GB** | **10.08 GB** | **43.2 GB** |
| 1 hour | 24 | **0.72 GB** | **5.04 GB** | **21.6 GB** |

## PromQL Query Examples

```promql
# Average download speed over the last hour
avg_over_time(download_speed_bytes_per_second[1h])

# Convert to Mbps
download_speed_bytes_per_second * 8 / 1000000

# Percentage of successful checks
avg_over_time(probe_success[1h]) * 100

# All checks with errors (not 200 OK)
probe_http_status_code{job="download-speed"} != 200

# Number of 404 errors in the last hour
count_over_time((probe_http_status_code == 404)[1h:])
```

## Grafana Dashboard

Ready-to-use dashboard is in `grafana/download-speed.json`.

### Import dashboard

1. Open Grafana → Dashboards → Import
2. Upload `grafana/download-speed.json` file or copy its content
3. **Select Prometheus datasource** in the "Select a Prometheus data source" field
4. Click Import
5. Set the correct `job` in Grafana Variables and save it as default value. Otherwise graphs may capture metrics from blackbox_exporter due to identical metric names (`probe_success`, `probe_duration_seconds`).

## Speed Test Links

- Hetzner (Germany): https://fsn1-speed.hetzner.com/
- Tele2 (EU): http://speedtest.tele2.net/
- OVH (France): https://proof.ovh.net/files/