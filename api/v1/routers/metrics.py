from typing import Dict, Any
from fastapi import APIRouter, Response, Depends
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import psutil
import os
from datetime import datetime

from ....core.utils.metrics import (
    MetricsCollector,
    MEMORY_USAGE,
    CPU_USAGE,
    DB_CONNECTION_POOL
)
from ....core.utils.logger import get_logger
from ....core.auth import get_current_user, is_admin
from ....core.models.user import User

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = get_logger(__name__)

@router.get("")
async def metrics(
    current_user: User = Depends(get_current_user),
    is_admin_user: bool = Depends(is_admin)
) -> Response:
    """Expose Prometheus metrics"""
    if not is_admin_user:
        raise HTTPException(
            status_code=403,
            detail="Admin access required for metrics"
        )

    # Update system metrics before generating response
    try:
        # Memory metrics
        memory = psutil.virtual_memory()
        MEMORY_USAGE.labels(type="total").set(memory.total)
        MEMORY_USAGE.labels(type="available").set(memory.available)
        MEMORY_USAGE.labels(type="used").set(memory.used)
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        CPU_USAGE.labels(type="total").set(cpu_percent)
        
        # Per-CPU metrics
        cpu_times_percent = psutil.cpu_times_percent(interval=1)
        CPU_USAGE.labels(type="user").set(cpu_times_percent.user)
        CPU_USAGE.labels(type="system").set(cpu_times_percent.system)
        CPU_USAGE.labels(type="idle").set(cpu_times_percent.idle)
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        MEMORY_USAGE.labels(type="disk_total").set(disk.total)
        MEMORY_USAGE.labels(type="disk_used").set(disk.used)
        MEMORY_USAGE.labels(type="disk_free").set(disk.free)
        
        # Process metrics
        process = psutil.Process(os.getpid())
        MEMORY_USAGE.labels(type="process_rss").set(process.memory_info().rss)
        MEMORY_USAGE.labels(type="process_vms").set(process.memory_info().vms)
        CPU_USAGE.labels(type="process").set(process.cpu_percent(interval=1))
        
    except Exception as e:
        logger.error(f"Error updating system metrics: {str(e)}")

    # Generate metrics response
    metrics_data = generate_latest()
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/summary")
async def metrics_summary(
    current_user: User = Depends(get_current_user),
    is_admin_user: bool = Depends(is_admin)
) -> Dict[str, Any]:
    """Get a summary of key metrics"""
    if not is_admin_user:
        raise HTTPException(
            status_code=403,
            detail="Admin access required for metrics summary"
        )

    try:
        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        process = psutil.Process(os.getpid())
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent
                },
                "cpu": {
                    "percent": psutil.cpu_percent(interval=1),
                    "count": psutil.cpu_count()
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "percent": disk.percent
                }
            },
            "process": {
                "memory": {
                    "rss": process.memory_info().rss,
                    "vms": process.memory_info().vms
                },
                "cpu_percent": process.cpu_percent(interval=1),
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections())
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating metrics summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating metrics summary: {str(e)}"
        )

@router.get("/custom/{metric_name}")
async def custom_metric(
    metric_name: str,
    current_user: User = Depends(get_current_user),
    is_admin_user: bool = Depends(is_admin)
) -> Dict[str, Any]:
    """Get specific custom metric"""
    if not is_admin_user:
        raise HTTPException(
            status_code=403,
            detail="Admin access required for custom metrics"
        )

    try:
        if metric_name == "memory":
            memory = psutil.virtual_memory()
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "memory",
                "values": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "free": memory.free,
                    "percent": memory.percent
                }
            }
            
        elif metric_name == "cpu":
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "cpu",
                "values": {
                    "percent": psutil.cpu_percent(interval=1),
                    "count": psutil.cpu_count(),
                    "times_percent": psutil.cpu_times_percent(interval=1)._asdict()
                }
            }
            
        elif metric_name == "disk":
            disk = psutil.disk_usage('/')
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "disk",
                "values": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                }
            }
            
        elif metric_name == "process":
            process = psutil.Process(os.getpid())
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "process",
                "values": {
                    "memory_info": process.memory_info()._asdict(),
                    "cpu_percent": process.cpu_percent(interval=1),
                    "threads": process.num_threads(),
                    "open_files": len(process.open_files()),
                    "connections": len(process.connections())
                }
            }
            
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Metric {metric_name} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting custom metric {metric_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting metric {metric_name}: {str(e)}"
        ) 