"""
Health monitoring system for AI providers with continuous checks and status tracking.
"""
import asyncio
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from utils.logging_config import get_logger

logger = get_logger(__name__)


class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result"""
    name: str
    status: ProviderStatus
    response_time: float
    error_message: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    """Complete health status for a provider"""
    provider_name: str
    status: ProviderStatus
    last_check: float
    consecutive_failures: int
    consecutive_successes: int
    total_checks: int
    successful_checks: int
    average_response_time: float
    last_error: Optional[str] = None
    checks: List[HealthCheck] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthMonitor:
    """
    Continuous health monitoring for AI providers with configurable checks.
    """
    
    def __init__(
        self,
        check_interval: float = 30.0,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
        max_check_history: int = 100
    ):
        """
        Initialize health monitor.
        
        Args:
            check_interval: Seconds between health checks
            failure_threshold: Consecutive failures before marking unhealthy
            recovery_threshold: Consecutive successes before marking healthy
            max_check_history: Maximum number of checks to keep in history
        """
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.max_check_history = max_check_history
        
        self.providers: Dict[str, ProviderHealth] = {}
        self.health_checks: Dict[str, List[Callable[[], HealthCheck]]] = {}
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        logger.info(f"Health monitor initialized: check_interval={check_interval}s, "
                   f"failure_threshold={failure_threshold}, recovery_threshold={recovery_threshold}")
    
    def register_provider(
        self,
        provider_name: str,
        health_checks: List[Callable[[], HealthCheck]],
        initial_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register a provider for health monitoring.
        
        Args:
            provider_name: Name of the provider
            health_checks: List of health check functions
            initial_metadata: Initial metadata for the provider
        """
        self.health_checks[provider_name] = health_checks
        self.providers[provider_name] = ProviderHealth(
            provider_name=provider_name,
            status=ProviderStatus.UNKNOWN,
            last_check=0,
            consecutive_failures=0,
            consecutive_successes=0,
            total_checks=0,
            successful_checks=0,
            average_response_time=0.0,
            metadata=initial_metadata or {}
        )
        
        logger.info(f"Registered provider '{provider_name}' with {len(health_checks)} health checks")
    
    def unregister_provider(self, provider_name: str):
        """Unregister a provider from health monitoring."""
        if provider_name in self.providers:
            del self.providers[provider_name]
        if provider_name in self.health_checks:
            del self.health_checks[provider_name]
        logger.info(f"Unregistered provider '{provider_name}'")
    
    async def start_monitoring(self):
        """Start continuous health monitoring."""
        if self._monitoring:
            logger.warning("Health monitoring is already running")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop continuous health monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                await self._check_all_providers()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(5)  # Brief pause on error
    
    async def _check_all_providers(self):
        """Check health of all registered providers."""
        async with self._lock:
            tasks = []
            for provider_name in list(self.providers.keys()):
                if provider_name in self.health_checks:
                    tasks.append(self._check_provider(provider_name))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_provider(self, provider_name: str):
        """Check health of a specific provider."""
        if provider_name not in self.health_checks:
            return
        
        provider_health = self.providers[provider_name]
        checks = self.health_checks[provider_name]
        
        # Run all health checks for this provider
        check_results = []
        for check_func in checks:
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, check_func
                )
                check_results.append(result)
            except Exception as e:
                logger.error(f"Health check failed for {provider_name}: {e}")
                check_results.append(HealthCheck(
                    name=check_func.__name__,
                    status=ProviderStatus.UNHEALTHY,
                    response_time=0.0,
                    error_message=str(e)
                ))
        
        # Determine overall provider status
        await self._update_provider_health(provider_name, check_results)
    
    async def _update_provider_health(self, provider_name: str, check_results: List[HealthCheck]):
        """Update provider health based on check results."""
        provider_health = self.providers[provider_name]
        
        # Calculate overall status
        healthy_count = sum(1 for check in check_results if check.status == ProviderStatus.HEALTHY)
        degraded_count = sum(1 for check in check_results if check.status == ProviderStatus.DEGRADED)
        unhealthy_count = sum(1 for check in check_results if check.status == ProviderStatus.UNHEALTHY)
        
        total_checks = len(check_results)
        if total_checks == 0:
            overall_status = ProviderStatus.UNKNOWN
        elif unhealthy_count > 0:
            overall_status = ProviderStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = ProviderStatus.DEGRADED
        else:
            overall_status = ProviderStatus.HEALTHY
        
        # Calculate average response time
        response_times = [check.response_time for check in check_results if check.response_time > 0]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        
        # Update counters
        was_healthy = provider_health.status == ProviderStatus.HEALTHY
        is_healthy = overall_status == ProviderStatus.HEALTHY
        
        if is_healthy:
            provider_health.consecutive_successes += 1
            provider_health.consecutive_failures = 0
        else:
            provider_health.consecutive_failures += 1
            provider_health.consecutive_successes = 0
        
        provider_health.total_checks += 1
        if is_healthy:
            provider_health.successful_checks += 1
        
        # Update status with thresholds
        if overall_status == ProviderStatus.HEALTHY:
            if provider_health.consecutive_successes >= self.recovery_threshold:
                provider_health.status = ProviderStatus.HEALTHY
            elif was_healthy:
                provider_health.status = ProviderStatus.DEGRADED
            else:
                provider_health.status = overall_status
        else:
            if provider_health.consecutive_failures >= self.failure_threshold:
                provider_health.status = ProviderStatus.UNHEALTHY
            else:
                provider_health.status = ProviderStatus.DEGRADED
        
        # Update other fields
        provider_health.last_check = time.time()
        provider_health.average_response_time = avg_response_time
        
        # Store recent checks (trim if necessary)
        provider_health.checks.extend(check_results)
        if len(provider_health.checks) > self.max_check_history:
            provider_health.checks = provider_health.checks[-self.max_check_history:]
        
        # Store last error if any
        unhealthy_checks = [check for check in check_results if check.status == ProviderStatus.UNHEALTHY]
        if unhealthy_checks:
            provider_health.last_error = unhealthy_checks[0].error_message
        
        # Log status changes
        if provider_health.status != overall_status:
            logger.info(f"Provider '{provider_name}' status: {overall_status.value} -> {provider_health.status.value}")
    
    def get_provider_health(self, provider_name: str) -> Optional[ProviderHealth]:
        """Get health status for a specific provider."""
        return self.providers.get(provider_name)
    
    def get_all_health(self) -> Dict[str, ProviderHealth]:
        """Get health status for all providers."""
        return self.providers.copy()
    
    def is_healthy(self, provider_name: str) -> bool:
        """Check if a provider is healthy."""
        health = self.providers.get(provider_name)
        return health is not None and health.status == ProviderStatus.HEALTHY
    
    def is_available(self, provider_name: str) -> bool:
        """Check if a provider is available (healthy or degraded)."""
        health = self.providers.get(provider_name)
        if health is None:
            return False
        return health.status in [ProviderStatus.HEALTHY, ProviderStatus.DEGRADED]
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of all provider health statuses."""
        summary = {
            "total_providers": len(self.providers),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "disabled": 0,
            "unknown": 0,
            "monitoring_active": self._monitoring,
            "providers": {}
        }
        
        for name, health in self.providers.items():
            status = health.status.value
            summary[status] += 1
            summary["providers"][name] = {
                "status": status,
                "consecutive_failures": health.consecutive_failures,
                "consecutive_successes": health.consecutive_successes,
                "success_rate": health.successful_checks / health.total_checks if health.total_checks > 0 else 0,
                "average_response_time": health.average_response_time,
                "last_check": health.last_check,
                "last_error": health.last_error
            }
        
        return summary
    
    async def force_check(self, provider_name: str) -> Optional[ProviderHealth]:
        """Force an immediate health check for a specific provider."""
        if provider_name not in self.health_checks:
            logger.warning(f"Provider '{provider_name}' not registered for health monitoring")
            return None
        
        await self._check_provider(provider_name)
        return self.providers.get(provider_name)
    
    async def force_check_all(self) -> Dict[str, ProviderHealth]:
        """Force immediate health checks for all providers."""
        await self._check_all_providers()
        return self.get_all_health()


# Global health monitor instance
health_monitor = HealthMonitor()