# Deployment Scripts

This directory contains scripts for deploying and running the application in various environments.

## Scripts

- `start.sh`: Script to start the application in development mode
- `entrypoint.prod.sh`: Production entrypoint script for Docker containers

## Usage

### Start Application (Development)

```bash
./backend/scripts/deployment/start.sh
```

### Production Entrypoint

This script is used as the entrypoint in the Docker container for production deployment:

```dockerfile
ENTRYPOINT ["/app/scripts/deployment/entrypoint.prod.sh"]
```

## Notes

- The `start.sh` script is for development purposes
- The `entrypoint.prod.sh` script is used in production Docker containers
- Make sure the scripts have executable permissions before using them:
  ```bash
  chmod +x backend/scripts/deployment/*.sh
  ``` 