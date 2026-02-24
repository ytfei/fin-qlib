# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability, please send an email to [security contact].

## Supported Versions

Currently supported versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |

## Security Best Practices

### 1. Credential Management

**NEVER commit sensitive information to the repository:**
- Passwords
- API keys
- Tokens
- Private keys
- Certificates

**Use environment variables instead:**

```yaml
# config/online_config.yaml
mongo:
  task_url: "mongodb://${MONGO_USER}:${MONGO_PASS}@host:27017/db"
```

```bash
# .env file (DO NOT commit)
MONGO_USER=your_username
MONGO_PASS=your_password
```

### 2. Database Security

- Change default MongoDB credentials in production
- Use strong passwords (minimum 12 characters, mixed case, numbers, symbols)
- Enable authentication
- Use SSL/TLS for connections
- Restrict network access (firewall, IP whitelisting)

### 3. MLflow Configuration

- Set `mlflow_tracking_uri` to a secure location
- Use authentication for MLflow UI
- Restrict access to MLflow tracking server

### 4. File Permissions

Ensure sensitive files have restricted permissions:
```bash
chmod 600 .env
chmod 600 config/online_config.yaml
```

### 5. Git Best Practices

```bash
# Review before committing
git diff --cached

# Check for secrets
git diff --cached | grep -i "password\|secret\|key\|token"

# Use .gitignore properly
echo ".env" >> .gitignore
echo "*.key" >> .gitignore
echo "*.pem" >> .gitignore
```

### 6. Docker Security

When running in Docker:
- Don't bake credentials into images
- use Docker secrets or environment variables
- Run containers as non-root user
- Keep images updated

```yaml
# docker-compose.yml
services:
  app:
    environment:
      - MONGO_USER=${MONGO_USER}
      - MONGO_PASS=${MONGO_PASS}
```

## Security Checklist

Before deploying to production:

- [ ] All credentials removed from code
- [ ] Environment variables configured
- [ ] Strong passwords set
- [ ] SSL/TLS enabled
- [ ] Firewall configured
- [ ] Access logs enabled
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Dependencies updated
- [ ] .gitignore reviewed

## Dependency Scanning

Regularly scan dependencies for vulnerabilities:

```bash
# Using pip-audit
pip install pip-audit
pip-audit

# Using safety
pip install safety
safety check
```

## Contact

For security questions or concerns, please contact [security contact].
