# 🔧 Troubleshooting Guide

> Giải quyết các vấn đề thường gặp trong Day 12 Lab

---

## 🐳 Docker Issues

### Issue: "Cannot connect to Docker daemon"

**Symptoms:**
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

**Solutions:**

1. **Docker Desktop chưa chạy:**
   ```bash
   # macOS: Mở Docker Desktop app
   # Linux: Start Docker service
   sudo systemctl start docker
   ```

2. **Permission denied (Linux):**
   ```bash
   # Add user to docker group
   sudo usermod -aG docker $USER
   
   # Logout and login again, or:
   newgrp docker
   ```

3. **Check Docker status:**
   ```bash
   docker info
   docker version
   ```

---

### Issue: "Port is already allocated"

**Symptoms:**
```
Error starting userland proxy: listen tcp4 0.0.0.0:8000: bind: address already in use
```

**Solutions:**

1. **Find process using port:**
   ```bash
   # macOS/Linux
   lsof -i :8000
   
   # Windows
   netstat -ano | findstr :8000
   ```

2. **Kill process:**
   ```bash
   # macOS/Linux
   kill -9 $(lsof -t -i:8000)
   
   # Windows
   taskkill /PID <PID> /F
   ```

3. **Use different port:**
   ```bash
   docker run -p 8001:8000 myapp
   ```

4. **Stop conflicting container:**
   ```bash
   docker ps
   docker stop <container-id>
   ```

---

### Issue: "No space left on device"

**Symptoms:**
```
Error: No space left on device
```

**Solutions:**

1. **Clean up Docker:**
   ```bash
   # Remove stopped containers
   docker container prune
   
   # Remove unused images
   docker image prune -a
   
   # Remove everything (careful!)
   docker system prune -a --volumes
   ```

2. **Check disk usage:**
   ```bash
   docker system df
   ```

3. **Increase Docker disk size:**
   - Docker Desktop → Settings → Resources → Disk image size

---

### Issue: "Build fails with 'requirements.txt not found'"

**Symptoms:**
```
COPY requirements.txt .
COPY failed: file not found in build context
```

**Solutions:**

1. **Check file exists:**
   ```bash
   ls -la requirements.txt
   ```

2. **Check Dockerfile location:**
   ```bash
   # Dockerfile phải cùng folder với requirements.txt
   # Hoặc adjust COPY path
   COPY ./path/to/requirements.txt .
   ```

3. **Check .dockerignore:**
   ```bash
   # Make sure requirements.txt không bị ignore
   cat .dockerignore
   ```

4. **Build with context:**
   ```bash
   docker build -t myapp -f Dockerfile .
   #                                  ^ context path
   ```

---

### Issue: "Container exits immediately"

**Symptoms:**
```
docker ps  # Container không có trong list
docker ps -a  # Container có status "Exited (1)"
```

**Solutions:**

1. **Check logs:**
   ```bash
   docker logs <container-id>
   ```

2. **Common causes:**
   - **Missing environment variables:**
     ```bash
     docker run -e REQUIRED_VAR=value myapp
     ```
   
   - **Wrong CMD/ENTRYPOINT:**
     ```dockerfile
     # ❌ Wrong
     CMD python app.py
     
     # ✅ Correct
     CMD ["python", "app.py"]
     ```
   
   - **Application crashes on startup:**
     ```bash
     # Run interactively to debug
     docker run -it myapp /bin/sh
     python app.py  # Run manually to see error
     ```

3. **Keep container running for debugging:**
   ```bash
   docker run -it --entrypoint /bin/sh myapp
   ```

---

## 🎼 Docker Compose Issues

### Issue: "Service 'X' failed to build"

**Solutions:**

1. **Check docker-compose.yml syntax:**
   ```bash
   docker compose config
   ```

2. **Build with verbose output:**
   ```bash
   docker compose build --no-cache --progress=plain
   ```

3. **Build individual service:**
   ```bash
   docker compose build <service-name>
   ```

---

### Issue: "Cannot connect to service from another service"

**Symptoms:**
```python
# From agent container
requests.get("http://redis:6379")  # Connection refused
```

**Solutions:**

1. **Use service name as hostname:**
   ```python
   # ✅ Correct
   redis_url = "redis://redis:6379"
   
   # ❌ Wrong
   redis_url = "redis://localhost:6379"
   ```

2. **Check services are on same network:**
   ```yaml
   services:
     agent:
       networks:
         - mynetwork
     redis:
       networks:
         - mynetwork
   
   networks:
     mynetwork:
   ```

3. **Check service is ready:**
   ```bash
   docker compose ps
   docker compose logs redis
   ```

4. **Test connectivity:**
   ```bash
   docker compose exec agent ping redis
   docker compose exec agent curl http://redis:6379
   ```

---

### Issue: "Changes not reflected in container"

**Solutions:**

1. **Rebuild images:**
   ```bash
   docker compose up --build
   ```

2. **Use volumes for development:**
   ```yaml
   services:
     agent:
       volumes:
         - ./app:/app  # Mount local code
   ```

3. **Clear cache:**
   ```bash
   docker compose build --no-cache
   ```

---

## 🚂 Railway Issues

### Issue: "railway: command not found"

**Solutions:**

1. **Install Railway CLI:**
   ```bash
   npm i -g @railway/cli
   
   # Or with Homebrew (macOS)
   brew install railway
   ```

2. **Check installation:**
   ```bash
   railway --version
   ```

3. **Add to PATH (if needed):**
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export PATH="$PATH:$(npm config get prefix)/bin"
   ```

---

### Issue: "Build failed on Railway"

**Solutions:**

1. **Check build logs:**
   - Railway Dashboard → Deployments → Click failed deployment → View logs

2. **Common causes:**
   - **Missing requirements.txt:**
     ```bash
     # Make sure file is committed
     git add requirements.txt
     git commit -m "Add requirements"
     git push
     ```
   
   - **Wrong Python version:**
     ```toml
     # railway.toml
     [build]
     builder = "NIXPACKS"
     
     [build.nixpacksPlan.phases.setup]
     nixPkgs = ["python311"]
     ```
   
   - **Build timeout:**
     ```toml
     [build]
     buildCommand = "pip install --no-cache-dir -r requirements.txt"
     ```

3. **Test build locally:**
   ```bash
   railway run python app.py
   ```

---

### Issue: "Application crashes on Railway"

**Solutions:**

1. **Check logs:**
   ```bash
   railway logs
   ```

2. **Common causes:**
   - **Missing environment variables:**
     ```bash
     railway variables set KEY=value
     ```
   
   - **Wrong PORT:**
     ```python
     # ✅ Use Railway's PORT
     port = int(os.getenv("PORT", 8000))
     
     # ❌ Hardcoded port
     port = 8000
     ```
   
   - **Memory limit exceeded:**
     - Railway Dashboard → Settings → Increase memory

3. **Run locally with Railway env:**
   ```bash
   railway run python app.py
   ```

---

## 🎨 Render Issues

### Issue: "Build failed on Render"

**Solutions:**

1. **Check build command:**
   ```yaml
   # render.yaml
   services:
     - type: web
       buildCommand: pip install -r requirements.txt
   ```

2. **Check Python version:**
   ```yaml
   services:
     - type: web
       runtime: python
       envVars:
         - key: PYTHON_VERSION
           value: 3.11.0
   ```

3. **View build logs:**
   - Render Dashboard → Service → Events → Click build

---

### Issue: "Health check failing"

**Symptoms:**
```
Health check failed: GET /health returned 404
```

**Solutions:**

1. **Implement health endpoint:**
   ```python
   @app.get("/health")
   def health():
       return {"status": "ok"}
   ```

2. **Configure in render.yaml:**
   ```yaml
   services:
     - type: web
       healthCheckPath: /health
   ```

3. **Check start command:**
   ```yaml
   services:
     - type: web
       startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

---

## 🔐 Authentication Issues

### Issue: "401 Unauthorized" even with correct API key

**Solutions:**

1. **Check header name:**
   ```bash
   # ✅ Correct
   curl -H "X-API-Key: secret" http://localhost:8000/ask
   
   # ❌ Wrong
   curl -H "API-Key: secret" http://localhost:8000/ask
   ```

2. **Check environment variable:**
   ```python
   # Print to debug
   print(f"Expected key: {settings.agent_api_key}")
   print(f"Received key: {x_api_key}")
   ```

3. **Check for whitespace:**
   ```bash
   # Trim whitespace
   export AGENT_API_KEY=$(echo "secret" | xargs)
   ```

---

### Issue: "JWT token expired"

**Solutions:**

1. **Get new token:**
   ```bash
   curl -X POST http://localhost:8000/token \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "secret"}'
   ```

2. **Increase expiration time:**
   ```python
   expire = datetime.utcnow() + timedelta(hours=24)  # 24 hours
   ```

3. **Check token format:**
   ```bash
   # ✅ Correct
   curl -H "Authorization: Bearer <token>"
   
   # ❌ Wrong
   curl -H "Authorization: <token>"
   ```

---

## ⏱️ Rate Limiting Issues

### Issue: "429 Too Many Requests" immediately

**Solutions:**

1. **Check Redis connection:**
   ```python
   try:
       r.ping()
       print("Redis connected")
   except:
       print("Redis not connected")
   ```

2. **Clear rate limit data:**
   ```bash
   # Connect to Redis
   docker exec -it <redis-container> redis-cli
   
   # Delete rate limit keys
   KEYS rate:*
   DEL rate:user123
   ```

3. **Increase limit:**
   ```python
   RATE_LIMIT = 100  # requests per minute
   ```

4. **Check time window:**
   ```python
   # Make sure window is in seconds
   window = 60  # 60 seconds
   ```

---

## 💰 Cost Guard Issues

### Issue: "402 Payment Required" but budget not exceeded

**Solutions:**

1. **Check Redis data:**
   ```bash
   docker exec -it <redis-container> redis-cli
   GET budget:user123:2026-04
   ```

2. **Reset budget:**
   ```bash
   DEL budget:user123:2026-04
   ```

3. **Check calculation:**
   ```python
   print(f"Current: {current}")
   print(f"Estimated: {estimated_cost}")
   print(f"Limit: {monthly_limit}")
   print(f"Total: {current + estimated_cost}")
   ```

---

## 🔄 Redis Issues

### Issue: "Connection refused to Redis"

**Solutions:**

1. **Check Redis is running:**
   ```bash
   docker ps | grep redis
   ```

2. **Check connection string:**
   ```python
   # ✅ Correct
   redis_url = "redis://redis:6379"  # In Docker Compose
   redis_url = "redis://localhost:6379"  # Local
   
   # ❌ Wrong
   redis_url = "redis://redis:6379/0"  # Extra /0 might cause issues
   ```

3. **Test connection:**
   ```bash
   # From host
   redis-cli -h localhost -p 6379 ping
   
   # From container
   docker exec -it <redis-container> redis-cli ping
   ```

4. **Check firewall:**
   ```bash
   # Allow port 6379
   sudo ufw allow 6379
   ```

---

### Issue: "Redis data lost after restart"

**Solutions:**

1. **Use volume:**
   ```yaml
   services:
     redis:
       volumes:
         - redis-data:/data
   
   volumes:
     redis-data:
   ```

2. **Enable persistence:**
   ```yaml
   services:
     redis:
       command: redis-server --appendonly yes
   ```

---

## 🏥 Health Check Issues

### Issue: "Health check always fails"

**Solutions:**

1. **Test endpoint manually:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check response format:**
   ```python
   # ✅ Return 200 status
   @app.get("/health")
   def health():
       return {"status": "ok"}
   
   # ❌ Return error status
   @app.get("/health")
   def health():
       return JSONResponse(status_code=500, content={"status": "error"})
   ```

3. **Check dependencies in readiness:**
   ```python
   @app.get("/ready")
   def ready():
       try:
           r.ping()  # Check Redis
           return {"status": "ready"}
       except Exception as e:
           return JSONResponse(
               status_code=503,
               content={"status": "not ready", "error": str(e)}
           )
   ```

---

## 🔄 Graceful Shutdown Issues

### Issue: "Container killed immediately"

**Solutions:**

1. **Handle SIGTERM:**
   ```python
   import signal
   
   def shutdown_handler(signum, frame):
       print("Shutting down gracefully...")
       # Cleanup code here
       sys.exit(0)
   
   signal.signal(signal.SIGTERM, shutdown_handler)
   ```

2. **Increase stop timeout:**
   ```yaml
   services:
     agent:
       stop_grace_period: 30s
   ```

3. **Test locally:**
   ```bash
   python app.py &
   PID=$!
   kill -TERM $PID
   # Should see "Shutting down gracefully..."
   ```

---

## 📊 Logging Issues

### Issue: "No logs visible"

**Solutions:**

1. **Check log level:**
   ```python
   logging.basicConfig(level=logging.INFO)  # Not DEBUG
   ```

2. **Flush stdout:**
   ```python
   print("Log message", flush=True)
   ```

3. **Use proper logger:**
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info("Message")  # Not print()
   ```

4. **Check Docker logs:**
   ```bash
   docker logs <container-id>
   docker logs -f <container-id>  # Follow
   ```

---

## 🌐 Network Issues

### Issue: "Cannot access deployed app"

**Solutions:**

1. **Check URL:**
   ```bash
   # Railway
   railway domain
   
   # Render
   # Check dashboard for URL
   ```

2. **Check deployment status:**
   - Dashboard → Deployments → Should be "Active"

3. **Check logs for errors:**
   ```bash
   railway logs
   # or Render dashboard → Logs
   ```

4. **Test with curl:**
   ```bash
   curl -v https://your-app.railway.app/health
   ```

---

## 🐛 General Debugging Tips

### Enable verbose logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Add debug endpoints

```python
@app.get("/debug/env")
def debug_env():
    return {
        "port": os.getenv("PORT"),
        "redis_url": os.getenv("REDIS_URL"),
        "log_level": os.getenv("LOG_LEVEL"),
    }

@app.get("/debug/redis")
def debug_redis():
    try:
        r.ping()
        return {"redis": "connected"}
    except Exception as e:
        return {"redis": "error", "message": str(e)}
```

### Use pdb for debugging

```python
import pdb

@app.post("/ask")
def ask(question: str):
    pdb.set_trace()  # Debugger will pause here
    # ...
```

### Check Python path

```python
import sys
print(sys.path)
```

---

## 📞 Getting Help

### Before asking for help:

1. **Read error message carefully**
2. **Check logs:**
   ```bash
   docker logs <container>
   railway logs
   ```
3. **Search error message on Google/Stack Overflow**
4. **Try minimal reproducible example**

### When asking for help, provide:

- **Error message** (full traceback)
- **What you tried**
- **Relevant code snippets**
- **Environment info:**
  ```bash
  python --version
  docker --version
  docker compose version
  ```
- **Logs**

---

## 🔗 Useful Resources

- [Docker Documentation](https://docs.docker.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Railway Documentation](https://docs.railway.app/)
- [Render Documentation](https://render.com/docs)
- [Redis Documentation](https://redis.io/docs/)
- [Stack Overflow](https://stackoverflow.com/)

---

**Still stuck? Check the Q&A section in CODE_LAB.md or ask your instructor! 💬**
