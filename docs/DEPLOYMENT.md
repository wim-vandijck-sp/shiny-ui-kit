# Deployment Guide

## Docker

```bash
docker build -t sailpoint-identity-manager .
docker run -p 8000:8000 --env-file .env sailpoint-identity-manager
```

## Production Checklist

- [ ] Set `APP_ENV=production` in environment
- [ ] Generate a strong `SESSION_SECRET` (min 32 chars)
- [ ] Configure HTTPS and update `OAUTH_REDIRECT_URI`
- [ ] Update SailPoint OAuth redirect URIs with production URL
- [ ] Consider Redis for session storage (`REDIS_URL`)
- [ ] Set up log aggregation
- [ ] Configure health check endpoint
