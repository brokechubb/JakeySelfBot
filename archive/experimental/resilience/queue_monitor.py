import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import logging
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class QueueMetrics:
    timestamp: float
    pending_count: int
    processing_count: int
    completed_count: int
    failed_count: int
    dead_letter_count: int
    processing_rate: float  # messages per second
    average_processing_time: float
    success_rate: float
    queue_depth: int
    oldest_message_age: float


@dataclass
class AlertThresholds:
    max_queue_depth: int = 1000
    max_failure_rate: float = 0.1  # 10%
    max_processing_time: float = 30.0  # seconds
    max_dead_letter_count: int = 100
    min_success_rate: float = 0.9  # 90%
    max_oldest_message_age: float = 300.0  # 5 minutes


class QueueMonitor:
    """Comprehensive queue monitoring and alerting system"""
    
    def __init__(
        self,
        message_queue,
        alert_thresholds: Optional[AlertThresholds] = None,
        metrics_history_size: int = 1000,
        monitoring_interval: float = 10.0
    ):
        """
        Initialize queue monitor
        
        Args:
            message_queue: Message queue instance to monitor
            alert_thresholds: Thresholds for triggering alerts
            metrics_history_size: Number of metrics to keep in history
            monitoring_interval: Interval between metric collections
        """
        self.message_queue = message_queue
        self.alert_thresholds = alert_thresholds or AlertThresholds()
        self.metrics_history_size = metrics_history_size
        self.monitoring_interval = monitoring_interval
        
        # Metrics storage
        self.metrics_history = deque(maxlen=metrics_history_size)
        self.current_metrics = None
        
        # Alert tracking
        self.active_alerts = {}
        self.alert_history = deque(maxlen=500)
        self.alert_callbacks = []
        
        # Monitoring control
        self._monitoring = False
        self._monitor_task = None
        
        # Performance tracking
        self.processing_times = deque(maxlen=100)
        self.success_failure_counts = deque(maxlen=100)
        
        logger.info("Queue monitor initialized")
    
    async def start_monitoring(self):
        """Start continuous monitoring"""
        if self._monitoring:
            logger.warning("Monitoring already started")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Queue monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Queue monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._monitoring:
            try:
                await self._collect_metrics()
                await self._check_alerts()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _collect_metrics(self):
        """Collect current queue metrics"""
        try:
            # Get queue statistics
            queue_stats = await self.message_queue.get_queue_stats()
            
            # Calculate derived metrics
            total_messages = (
                queue_stats["pending"] + queue_stats["processing"] + 
                queue_stats["completed"] + queue_stats["failed"]
            )
            
            processing_rate = 0.0
            success_rate = 0.0
            avg_processing_time = queue_stats.get("average_age_seconds", 0.0)
            
            if len(self.metrics_history) > 0:
                # Calculate processing rate from recent metrics
                prev_metrics = self.metrics_history[-1]
                time_diff = time.time() - prev_metrics.timestamp
                if time_diff > 0:
                    completed_diff = queue_stats["completed"] - prev_metrics.completed_count
                    processing_rate = completed_diff / time_diff
            
            # Calculate success rate
            total_processed = queue_stats["completed"] + queue_stats["failed"]
            if total_processed > 0:
                success_rate = queue_stats["completed"] / total_processed
            
            # Create metrics object
            metrics = QueueMetrics(
                timestamp=time.time(),
                pending_count=queue_stats["pending"],
                processing_count=queue_stats["processing"],
                completed_count=queue_stats["completed"],
                failed_count=queue_stats["failed"],
                dead_letter_count=queue_stats["dead_letter"],
                processing_rate=processing_rate,
                average_processing_time=avg_processing_time,
                success_rate=success_rate,
                queue_depth=queue_stats["pending"],
                oldest_message_age=queue_stats.get("oldest_message_age_seconds", 0.0)
            )
            
            self.current_metrics = metrics
            self.metrics_history.append(metrics)
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
    
    async def _check_alerts(self):
        """Check for alert conditions"""
        if not self.current_metrics:
            return
        
        alerts = []
        
        # Check queue depth
        if self.current_metrics.queue_depth > self.alert_thresholds.max_queue_depth:
            alerts.append({
                "type": "queue_depth",
                "severity": "warning",
                "message": f"Queue depth {self.current_metrics.queue_depth} exceeds threshold {self.alert_thresholds.max_queue_depth}",
                "value": self.current_metrics.queue_depth,
                "threshold": self.alert_thresholds.max_queue_depth
            })
        
        # Check failure rate
        failure_rate = 1.0 - self.current_metrics.success_rate
        if failure_rate > self.alert_thresholds.max_failure_rate:
            alerts.append({
                "type": "high_failure_rate",
                "severity": "critical",
                "message": f"Failure rate {failure_rate:.2%} exceeds threshold {self.alert_thresholds.max_failure_rate:.2%}",
                "value": failure_rate,
                "threshold": self.alert_thresholds.max_failure_rate
            })
        
        # Check processing time
        if self.current_metrics.average_processing_time > self.alert_thresholds.max_processing_time:
            alerts.append({
                "type": "slow_processing",
                "severity": "warning",
                "message": f"Average processing time {self.current_metrics.average_processing_time:.2f}s exceeds threshold {self.alert_thresholds.max_processing_time}s",
                "value": self.current_metrics.average_processing_time,
                "threshold": self.alert_thresholds.max_processing_time
            })
        
        # Check dead letter count
        if self.current_metrics.dead_letter_count > self.alert_thresholds.max_dead_letter_count:
            alerts.append({
                "type": "dead_letter_overflow",
                "severity": "critical",
                "message": f"Dead letter count {self.current_metrics.dead_letter_count} exceeds threshold {self.alert_thresholds.max_dead_letter_count}",
                "value": self.current_metrics.dead_letter_count,
                "threshold": self.alert_thresholds.max_dead_letter_count
            })
        
        # Check success rate
        if self.current_metrics.success_rate < self.alert_thresholds.min_success_rate:
            alerts.append({
                "type": "low_success_rate",
                "severity": "warning",
                "message": f"Success rate {self.current_metrics.success_rate:.2%} below threshold {self.alert_thresholds.min_success_rate:.2%}",
                "value": self.current_metrics.success_rate,
                "threshold": self.alert_thresholds.min_success_rate
            })
        
        # Check oldest message age
        if self.current_metrics.oldest_message_age > self.alert_thresholds.max_oldest_message_age:
            alerts.append({
                "type": "old_messages",
                "severity": "warning",
                "message": f"Oldest message age {self.current_metrics.oldest_message_age:.2f}s exceeds threshold {self.alert_thresholds.max_oldest_message_age}s",
                "value": self.current_metrics.oldest_message_age,
                "threshold": self.alert_thresholds.max_oldest_message_age
            })
        
        # Process alerts
        for alert in alerts:
            await self._handle_alert(alert)
    
    async def _handle_alert(self, alert: Dict[str, Any]):
        """Handle an alert"""
        alert_key = f"{alert['type']}_{alert['severity']}"
        
        # Check if this is a new alert or ongoing
        if alert_key not in self.active_alerts:
            # New alert
            alert["timestamp"] = time.time()
            alert["first_seen"] = time.time()
            alert["count"] = 1
            self.active_alerts[alert_key] = alert
            
            # Add to history
            self.alert_history.append(alert.copy())
            
            # Trigger callbacks
            await self._trigger_alert_callbacks(alert)
            
            logger.warning(f"ALERT: {alert['message']}")
        else:
            # Update existing alert
            self.active_alerts[alert_key]["count"] += 1
            self.active_alerts[alert_key]["timestamp"] = time.time()
    
    async def _trigger_alert_callbacks(self, alert: Dict[str, Any]):
        """Trigger registered alert callbacks"""
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def add_alert_callback(self, callback):
        """Add a callback function for alerts"""
        self.alert_callbacks.append(callback)
        logger.info(f"Added alert callback: {callback.__name__}")
    
    def remove_alert_callback(self, callback):
        """Remove an alert callback"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
            logger.info(f"Removed alert callback: {callback.__name__}")
    
    async def acknowledge_alert(self, alert_type: str, severity: str) -> bool:
        """Acknowledge and clear an alert"""
        alert_key = f"{alert_type}_{severity}"
        if alert_key in self.active_alerts:
            alert = self.active_alerts.pop(alert_key)
            alert["acknowledged"] = True
            alert["acknowledged_at"] = time.time()
            self.alert_history.append(alert)
            logger.info(f"Acknowledged alert: {alert_type}_{severity}")
            return True
        return False
    
    def get_current_metrics(self) -> Optional[QueueMetrics]:
        """Get current metrics"""
        return self.current_metrics
    
    def get_metrics_history(self, limit: Optional[int] = None) -> List[QueueMetrics]:
        """Get metrics history"""
        history = list(self.metrics_history)
        if limit:
            return history[-limit:]
        return history
    
    def get_active_alerts(self) -> Dict[str, Dict[str, Any]]:
        """Get active alerts"""
        return self.active_alerts.copy()
    
    def get_alert_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get alert history"""
        history = list(self.alert_history)
        if limit:
            return history[-limit:]
        return history
    
    def get_performance_summary(self, time_window: float = 300.0) -> Dict[str, Any]:
        """Get performance summary for a time window"""
        if not self.metrics_history:
            return {}
        
        # Filter metrics within time window
        cutoff_time = time.time() - time_window
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {}
        
        # Calculate aggregates
        avg_processing_rate = sum(m.processing_rate for m in recent_metrics) / len(recent_metrics)
        avg_success_rate = sum(m.success_rate for m in recent_metrics) / len(recent_metrics)
        avg_queue_depth = sum(m.queue_depth for m in recent_metrics) / len(recent_metrics)
        max_queue_depth = max(m.queue_depth for m in recent_metrics)
        min_success_rate = min(m.success_rate for m in recent_metrics)
        
        return {
            "time_window_seconds": time_window,
            "sample_count": len(recent_metrics),
            "average_processing_rate": avg_processing_rate,
            "average_success_rate": avg_success_rate,
            "average_queue_depth": avg_queue_depth,
            "max_queue_depth": max_queue_depth,
            "minimum_success_rate": min_success_rate,
            "trend": self._calculate_trend(recent_metrics)
        }
    
    def _calculate_trend(self, metrics: List[QueueMetrics]) -> str:
        """Calculate trend direction from metrics"""
        if len(metrics) < 2:
            return "stable"
        
        # Compare first and second half
        mid_point = len(metrics) // 2
        first_half = metrics[:mid_point]
        second_half = metrics[mid_point:]
        
        first_avg_queue = sum(m.queue_depth for m in first_half) / len(first_half)
        second_avg_queue = sum(m.queue_depth for m in second_half) / len(second_half)
        
        first_avg_success = sum(m.success_rate for m in first_half) / len(first_half)
        second_avg_success = sum(m.success_rate for m in second_half) / len(second_half)
        
        queue_change = (second_avg_queue - first_avg_queue) / first_avg_queue if first_avg_queue > 0 else 0
        success_change = (second_avg_success - first_avg_success) / first_avg_success if first_avg_success > 0 else 0
        
        if queue_change > 0.1 or success_change < -0.05:
            return "degrading"
        elif queue_change < -0.1 or success_change > 0.05:
            return "improving"
        else:
            return "stable"
    
    def export_metrics(self, filename: str, format: str = "json"):
        """Export metrics to file"""
        try:
            data = {
                "export_timestamp": time.time(),
                "current_metrics": asdict(self.current_metrics) if self.current_metrics else None,
                "metrics_history": [asdict(m) for m in self.metrics_history],
                "active_alerts": self.active_alerts,
                "alert_history": list(self.alert_history),
                "performance_summary": self.get_performance_summary()
            }
            
            if format.lower() == "json":
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            logger.info(f"Metrics exported to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            raise
    
    async def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        if not self.current_metrics:
            return {"status": "unknown", "reason": "No metrics available"}
        
        # Determine overall health
        issues = []
        
        if self.current_metrics.queue_depth > self.alert_thresholds.max_queue_depth * 0.8:
            issues.append("High queue depth")
        
        if self.current_metrics.success_rate < self.alert_thresholds.min_success_rate:
            issues.append("Low success rate")
        
        if self.current_metrics.dead_letter_count > self.alert_thresholds.max_dead_letter_count * 0.8:
            issues.append("High dead letter count")
        
        if len(self.active_alerts) > 5:
            issues.append("Multiple active alerts")
        
        health_status = "healthy" if not issues else "degraded" if len(issues) <= 2 else "unhealthy"
        
        return {
            "status": health_status,
            "issues": issues,
            "metrics": asdict(self.current_metrics),
            "active_alerts_count": len(self.active_alerts),
            "performance_summary": self.get_performance_summary(),
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on current state"""
        recommendations = []
        
        if not self.current_metrics:
            return recommendations
        
        if self.current_metrics.queue_depth > self.alert_thresholds.max_queue_depth * 0.8:
            recommendations.append("Consider increasing processing capacity or reducing message influx")
        
        if self.current_metrics.success_rate < self.alert_thresholds.min_success_rate:
            recommendations.append("Investigate message processing failures and improve error handling")
        
        if self.current_metrics.average_processing_time > self.alert_thresholds.max_processing_time * 0.8:
            recommendations.append("Optimize message processing logic or increase timeouts")
        
        if self.current_metrics.dead_letter_count > 0:
            recommendations.append("Review and handle dead letter messages")
        
        return recommendations


# Predefined alert callback functions
async def log_alert_callback(alert: Dict[str, Any]):
    """Simple logging alert callback"""
    logger.warning(f"Queue Alert [{alert['severity'].upper()}]: {alert['message']}")


async def email_alert_callback(alert: Dict[str, Any]):
    """Example email alert callback (placeholder)"""
    # In a real implementation, this would send an email
    logger.info(f"Would send email alert: {alert['message']}")


def webhook_alert_callback(webhook_url: str):
    """Create a webhook alert callback"""
    async def callback(alert: Dict[str, Any]):
        # In a real implementation, this would send to webhook
        logger.info(f"Would send webhook alert to {webhook_url}: {alert['message']}")
    return callback