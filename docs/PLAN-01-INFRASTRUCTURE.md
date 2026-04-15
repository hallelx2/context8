# Plan 01 — Infrastructure Setup

## Objective

Get Actian VectorAI DB running in Docker and verify the Python client can connect, create collections, and perform basic operations. This is the foundation everything else builds on.

## Steps

### Step 1: Docker Compose Configuration

Create `docker-compose.yml` at the project root:

```yaml
version: "3.8"
services:
  vectoraidb:
    image: williamimoh/actian-vectorai-db:latest
    container_name: context8_db
    ports:
      - "50051:50051"
    volumes:
      - ./data:/data
    restart: unless-stopped
    stop_grace_period: 2m
```

**Key decisions:**
- Container name `context8_db` (not generic `vectoraidb`)
- Volume mount `./data:/data` for persistence across restarts
- Port 50051 (gRPC, primary transport)

### Step 2: Python Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows

# Install Actian client from the beta wheel
pip install actian-vectorai

# Install embedding dependencies
pip install sentence-transformers torch
pip install transformers  # for CodeBERT

# Install MCP SDK
pip install mcp

# Install dev dependencies
pip install pytest pytest-asyncio
```

**Requirements file (`requirements.txt`):**

```
actian-vectorai>=0.1.0b2
sentence-transformers>=2.2.0
transformers>=4.30.0
torch>=2.0.0
mcp>=1.0.0
pydantic>=2.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
```

### Step 3: Verify Connection

Create `scripts/verify_connection.py`:

```python
"""Verify Actian VectorAI DB is running and accessible."""
from actian_vectorai import VectorAIClient

def main():
    try:
        with VectorAIClient("localhost:50051") as client:
            info = client.health_check()
            print(f"Connected: {info['title']} v{info['version']}")
            print(f"Status: HEALTHY")
            
            # List existing collections
            collections = client.collections.list()
            print(f"Collections: {len(collections)}")
            for col in collections:
                print(f"  - {col}")
                
    except Exception as e:
        print(f"Connection FAILED: {e}")
        print("Is Docker running? Try: docker compose up -d")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
```

### Step 4: Startup Script

Create `scripts/start.sh` (Linux/Mac) and `scripts/start.ps1` (Windows):

**`scripts/start.sh`:**
```bash
#!/bin/bash
set -e

echo "Starting Context8 infrastructure..."

# Start Docker container
docker compose up -d

# Wait for DB to be ready
echo "Waiting for Actian VectorAI DB..."
for i in {1..30}; do
    if python scripts/verify_connection.py 2>/dev/null; then
        echo "Database is ready!"
        exit 0
    fi
    sleep 1
done

echo "ERROR: Database did not start within 30 seconds"
exit 1
```

**`scripts/start.ps1`:**
```powershell
Write-Host "Starting Context8 infrastructure..."

docker compose up -d

Write-Host "Waiting for Actian VectorAI DB..."
$maxAttempts = 30
for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        python scripts/verify_connection.py 2>$null
        Write-Host "Database is ready!"
        exit 0
    } catch {
        Start-Sleep -Seconds 1
    }
}

Write-Host "ERROR: Database did not start within 30 seconds"
exit 1
```

## Testing Criteria

- [ ] `docker compose up -d` starts the container without errors
- [ ] `python scripts/verify_connection.py` prints "Connected" and "HEALTHY"
- [ ] Container survives `docker compose restart`
- [ ] Data persists in `./data/` across restarts
- [ ] Container auto-restarts after Docker daemon restart (restart policy)

## Files Created

```
actian-hackathon/
├── docker-compose.yml
├── requirements.txt
├── scripts/
│   ├── verify_connection.py
│   ├── start.sh
│   └── start.ps1
└── data/                    (created by Docker, gitignored)
```

## Estimated Time: 30 minutes

## Dependencies: None (this is the first step)

## Next: Plan 02 (Embedding Pipeline)
