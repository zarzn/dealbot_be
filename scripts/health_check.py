#!/usr/bin/env python
"""Health check script for AI Agentic Deals System.

This script checks the health of the application by calling the health check endpoints.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import requests

# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[37m"

def colored_print(message: str, color: str = Colors.RESET) -> None:
    """Print colored message to terminal.
    
    Args:
        message: Message to print
        color: ANSI color code
    """
    print(f"{color}{message}{Colors.RESET}")

def make_request(url: str, timeout: int = 10) -> Tuple[bool, Dict[str, Any]]:
    """Make HTTP request to health check endpoint.
    
    Args:
        url: URL to request
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (success, response_data)
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}

def check_endpoint(base_url: str, endpoint: str, description: str, verbose: bool = False) -> bool:
    """Check health of endpoint.
    
    Args:
        base_url: Base URL of application
        endpoint: Endpoint to check
        description: Description of check
        verbose: Whether to print verbose output
        
    Returns:
        True if healthy, False otherwise
    """
    url = f"{base_url}{endpoint}"
    
    if verbose:
        colored_print(f"Checking {description} at {url}...", Colors.CYAN)
    else:
        colored_print(f"Checking {description}...", Colors.CYAN)
    
    success, data = make_request(url)
    
    if verbose and success:
        colored_print(f"Response: {json.dumps(data, indent=2)}", Colors.GRAY)
    
    if not success:
        colored_print(f"✗ Failed to check {description}: {data.get('error')}", Colors.RED)
        return False
    
    status = data.get("status", "unknown")
    
    if status == "healthy":
        colored_print(f"✓ {description} is healthy", Colors.GREEN)
        return True
    elif status == "initializing":
        colored_print(f"⚠ {description} is initializing", Colors.YELLOW)
        return True
    else:
        message = data.get("message", "Unknown error")
        colored_print(f"✗ {description} is unhealthy: {message}", Colors.RED)
        return False

def main() -> int:
    """Main function.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(description="Health check for AI Agentic Deals System")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of application")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--check-database", action="store_true", help="Check database health")
    parser.add_argument("--check-redis", action="store_true", help="Check Redis health")
    parser.add_argument("--check-all", action="store_true", help="Check all services")
    parser.add_argument("--retry", type=int, default=0, help="Number of retries for failed checks")
    parser.add_argument("--retry-delay", type=int, default=5, help="Delay between retries in seconds")
    
    args = parser.parse_args()
    
    colored_print("=== AI Agentic Deals System Health Check ===", Colors.MAGENTA)
    colored_print(f"Base URL: {args.base_url}", Colors.MAGENTA)
    colored_print(f"Time: {datetime.now().isoformat()}", Colors.MAGENTA)
    colored_print("=======================================", Colors.MAGENTA)
    
    all_checks = []
    
    # Check root health endpoint
    root_health = check_endpoint(args.base_url, "/health", "Basic health check", args.verbose)
    all_checks.append(root_health)
    
    # Check detailed health endpoint
    detailed_health = check_endpoint(args.base_url, "/api/v1/health", "Detailed health check", args.verbose)
    all_checks.append(detailed_health)
    
    # Check database health if requested
    if args.check_database or args.check_all:
        db_health = check_endpoint(args.base_url, "/api/v1/health/database", "Database health", args.verbose)
        all_checks.append(db_health)
    
    # Check Redis health if requested
    if args.check_redis or args.check_all:
        redis_health = check_endpoint(args.base_url, "/api/v1/health/redis", "Redis health", args.verbose)
        all_checks.append(redis_health)
    
    # Retry failed checks if requested
    if args.retry > 0 and False in all_checks:
        colored_print(f"\nSome checks failed. Retrying up to {args.retry} times...", Colors.YELLOW)
        
        for retry in range(args.retry):
            colored_print(f"\nRetry {retry + 1}/{args.retry}...", Colors.YELLOW)
            colored_print(f"Waiting {args.retry_delay} seconds...", Colors.YELLOW)
            time.sleep(args.retry_delay)
            
            # Retry all checks
            all_checks = []
            
            # Check root health endpoint
            root_health = check_endpoint(args.base_url, "/health", "Basic health check", args.verbose)
            all_checks.append(root_health)
            
            # Check detailed health endpoint
            detailed_health = check_endpoint(args.base_url, "/api/v1/health", "Detailed health check", args.verbose)
            all_checks.append(detailed_health)
            
            # Check database health if requested
            if args.check_database or args.check_all:
                db_health = check_endpoint(args.base_url, "/api/v1/health/database", "Database health", args.verbose)
                all_checks.append(db_health)
            
            # Check Redis health if requested
            if args.check_redis or args.check_all:
                redis_health = check_endpoint(args.base_url, "/api/v1/health/redis", "Redis health", args.verbose)
                all_checks.append(redis_health)
            
            # If all checks pass, break out of retry loop
            if False not in all_checks:
                colored_print("\nAll checks passed after retry!", Colors.GREEN)
                break
    
    # Summary
    colored_print("\n=======================================", Colors.MAGENTA)
    
    if False in all_checks:
        colored_print("❌ Health check failed! Some services are unhealthy.", Colors.RED)
        return 1
    else:
        colored_print("✅ All health checks passed!", Colors.GREEN)
        return 0

if __name__ == "__main__":
    sys.exit(main()) 