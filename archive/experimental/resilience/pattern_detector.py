"""
Pattern detection system for identifying failure patterns and anomalies.
"""
import time
import statistics
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import math

from utils.logging_config import get_logger

logger = get_logger(__name__)


class PatternType(Enum):
    """Types of patterns that can be detected"""
    SPIKE = "spike"
    DRIFT = "drift"
    OSCILLATION = "oscillation"
    CORRELATION = "correlation"
    SEASONAL = "seasonal"
    ANOMALY = "anomaly"
    TREND = "trend"
    BURST = "burst"


class PatternSeverity(Enum):
    """Pattern severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Pattern:
    """Detected pattern information"""
    pattern_id: str
    pattern_type: PatternType
    severity: PatternSeverity
    confidence: float
    description: str
    metric_name: str
    detected_at: float
    time_window: int
    parameters: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    historical_occurrences: int = 0
    last_occurrence: Optional[float] = None


@dataclass
class MetricThreshold:
    """Metric threshold configuration"""
    metric_name: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    std_dev_threshold: float = 2.0
    trend_threshold: float = 0.1
    anomaly_threshold: float = 0.05


class PatternDetector:
    """
    Advanced pattern detection system for identifying system issues.
    """
    
    def __init__(
        self,
        history_size: int = 1000,
        min_pattern_samples: int = 10,
        confidence_threshold: float = 0.7,
        learning_enabled: bool = True
    ):
        """
        Initialize pattern detector.
        
        Args:
            history_size: Size of metric history to keep
            min_pattern_samples: Minimum samples required for pattern detection
            confidence_threshold: Minimum confidence for pattern detection
            learning_enabled: Enable adaptive learning from patterns
        """
        self.history_size = history_size
        self.min_pattern_samples = min_pattern_samples
        self.confidence_threshold = confidence_threshold
        self.learning_enabled = learning_enabled
        
        # Data storage
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self.detected_patterns: Dict[str, Pattern] = {}
        self.pattern_history: List[Pattern] = []
        
        # Thresholds and parameters
        self.thresholds: Dict[str, MetricThreshold] = {}
        self.adaptive_parameters: Dict[str, Dict[str, float]] = {}
        
        # Pattern detection functions
        self.pattern_detectors: Dict[PatternType, Callable] = {
            PatternType.SPIKE: self._detect_spike_pattern,
            PatternType.DRIFT: self._detect_drift_pattern,
            PatternType.OSCILLATION: self._detect_oscillation_pattern,
            PatternType.CORRELATION: self._detect_correlation_pattern,
            PatternType.SEASONAL: self._detect_seasonal_pattern,
            PatternType.ANOMALY: self._detect_anomaly_pattern,
            PatternType.TREND: self._detect_trend_pattern,
            PatternType.BURST: self._detect_burst_pattern
        }
        
        # Statistics
        self.stats = {
            "patterns_detected": 0,
            "patterns_by_type": defaultdict(int),
            "total_metrics_processed": 0,
            "detection_accuracy": 0.0
        }
        
        logger.info(f"Pattern detector initialized: history_size={history_size}, "
                   f"min_samples={min_pattern_samples}, confidence_threshold={confidence_threshold}")
    
    def add_metric(self, metric_name: str, value: float, timestamp: Optional[float] = None):
        """
        Add a metric value to the history.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            timestamp: Optional timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.metrics_history[metric_name].append((timestamp, value))
        self.stats["total_metrics_processed"] += 1
        
        # Trigger pattern detection for this metric
        if len(self.metrics_history[metric_name]) >= self.min_pattern_samples:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._detect_patterns_for_metric(metric_name))
            except RuntimeError:
                # No event loop running, skip pattern detection for now
                pass
    
    async def _detect_patterns_for_metric(self, metric_name: str):
        """Detect all patterns for a specific metric."""
        if metric_name not in self.metrics_history:
            return
        
        metric_data = list(self.metrics_history[metric_name])
        if len(metric_data) < self.min_pattern_samples:
            return
        
        values = [value for _, value in metric_data]
        timestamps = [timestamp for timestamp, _ in metric_data]
        
        # Run all pattern detectors
        for pattern_type, detector_func in self.pattern_detectors.items():
            try:
                patterns = await detector_func(metric_name, values, timestamps)
                for pattern in patterns:
                    await self._handle_detected_pattern(pattern)
            except Exception as e:
                logger.error(f"Pattern detection failed for {pattern_type.value} on {metric_name}: {e}")
    
    async def _detect_spike_pattern(self, metric_name: str, values: List[float], timestamps: List[float]) -> List[Pattern]:
        """Detect spike patterns (sudden large changes)."""
        patterns = []
        
        if len(values) < 5:
            return patterns
        
        # Calculate rolling statistics
        window_size = min(10, len(values) // 2)
        if window_size < 3:
            return patterns
        
        for i in range(window_size, len(values)):
            window_values = values[i-window_size:i]
            current_value = values[i]
            
            # Calculate statistics for the window
            window_mean = statistics.mean(window_values)
            window_std = statistics.stdev(window_values) if len(window_values) > 1 else 0
            
            if window_std == 0:
                continue
            
            # Check for spike (value significantly outside normal range)
            z_score = abs(current_value - window_mean) / window_std
            threshold = self.thresholds.get(metric_name, MetricThreshold(metric_name)).std_dev_threshold
            
            if z_score >= threshold:
                confidence = min(z_score / (threshold * 2), 1.0)
                severity = self._calculate_spike_severity(z_score)
                
                pattern = Pattern(
                    pattern_id=self._generate_pattern_id(),
                    pattern_type=PatternType.SPIKE,
                    severity=severity,
                    confidence=confidence,
                    description=f"Spike detected in {metric_name}: {current_value:.2f} (z-score: {z_score:.2f})",
                    metric_name=metric_name,
                    detected_at=timestamps[i],
                    time_window=window_size,
                    parameters={
                        "z_score": z_score,
                        "threshold": threshold,
                        "current_value": current_value,
                        "window_mean": window_mean,
                        "window_std": window_std
                    }
                )
                
                patterns.append(pattern)
        
        return patterns
    
    async def _detect_drift_pattern(self, metric_name: str, values: List[float], timestamps: List[float]) -> List[Pattern]:
        """Detect drift patterns (gradual changes over time)."""
        patterns = []
        
        if len(values) < 20:
            return patterns
        
        # Calculate trend over different windows
        window_sizes = [10, 20, min(50, len(values) // 2)]
        
        for window_size in window_sizes:
            if window_size >= len(values):
                continue
            
            recent_values = values[-window_size:]
            older_values = values[-(window_size*2):-window_size] if len(values) >= window_size*2 else values[:-window_size]
            
            if len(recent_values) < 5 or len(older_values) < 5:
                continue
            
            # Calculate means for both periods
            recent_mean = statistics.mean(recent_values)
            older_mean = statistics.mean(older_values)
            
            # Calculate percent change
            if older_mean != 0:
                percent_change = abs(recent_mean - older_mean) / abs(older_mean)
            else:
                percent_change = abs(recent_mean - older_mean)
            
            threshold = self.thresholds.get(metric_name, MetricThreshold(metric_name)).trend_threshold
            
            if percent_change >= threshold:
                # Calculate trend direction
                trend_direction = "increasing" if recent_mean > older_mean else "decreasing"
                
                # Calculate confidence based on consistency of trend
                trend_consistency = self._calculate_trend_consistency(recent_values)
                confidence = min(trend_consistency * percent_change / threshold, 1.0)
                
                severity = self._calculate_drift_severity(percent_change)
                
                pattern = Pattern(
                    pattern_id=self._generate_pattern_id(),
                    pattern_type=PatternType.DRIFT,
                    severity=severity,
                    confidence=confidence,
                    description=f"Drift detected in {metric_name}: {trend_direction} by {percent_change:.2%}",
                    metric_name=metric_name,
                    detected_at=timestamps[-1],
                    time_window=window_size,
                    parameters={
                        "percent_change": percent_change,
                        "threshold": threshold,
                        "trend_direction": trend_direction,
                        "recent_mean": recent_mean,
                        "older_mean": older_mean,
                        "trend_consistency": trend_consistency
                    }
                )
                
                patterns.append(pattern)
        
        return patterns
    
    async def _detect_oscillation_pattern(self, metric_name: str, values: List[float], timestamps: List[float]) -> List[Pattern]:
        """Detect oscillation patterns (regular fluctuations)."""
        patterns = []
        
        if len(values) < 20:
            return patterns
        
        # Look for periodic behavior using autocorrelation
        max_lag = min(len(values) // 4, 50)
        if max_lag < 5:
            return patterns
        
        # Calculate autocorrelation for different lags
        autocorrelations = []
        for lag in range(1, max_lag):
            if len(values) <= lag:
                continue
            
            # Calculate autocorrelation
            n = len(values) - lag
            if n < 10:
                continue
            
            x = values[:-lag]
            y = values[lag:]
            
            # Calculate correlation coefficient
            if len(set(x)) > 1 and len(set(y)) > 1:
                correlation = self._calculate_correlation(x, y)
                autocorrelations.append((lag, abs(correlation)))
        
        if not autocorrelations:
            return patterns
        
        # Find significant peaks in autocorrelation
        autocorrelations.sort(key=lambda x: x[1], reverse=True)
        
        for lag, correlation in autocorrelations[:3]:  # Check top 3
            if correlation >= 0.7:  # Strong correlation threshold
                # Verify periodicity
                if self._verify_periodicity(values, lag, tolerance=0.3):
                    confidence = correlation
                    severity = self._calculate_oscillation_severity(correlation, lag)
                    
                    pattern = Pattern(
                        pattern_id=self._generate_pattern_id(),
                        pattern_type=PatternType.OSCILLATION,
                        severity=severity,
                        confidence=confidence,
                        description=f"Oscillation detected in {metric_name}: period {lag}, correlation {correlation:.3f}",
                        metric_name=metric_name,
                        detected_at=timestamps[-1],
                        time_window=lag * 3,  # Show 3 periods
                        parameters={
                            "period": lag,
                            "correlation": correlation,
                            "frequency": 1.0 / lag if lag > 0 else 0
                        }
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    async def _detect_correlation_pattern(self, metric_name: str, values: List[float], timestamps: List[float]) -> List[Pattern]:
        """Detect correlation patterns between metrics."""
        patterns = []
        
        if len(values) < 10:
            return patterns
        
        # Check correlation with other metrics
        for other_metric_name, other_data in self.metrics_history.items():
            if other_metric_name == metric_name:
                continue
            
            other_values = [value for _, value in other_data]
            if len(other_values) != len(values):
                # Align the data
                min_length = min(len(values), len(other_values))
                if min_length < 10:
                    continue
                values_aligned = values[-min_length:]
                other_values_aligned = other_values[-min_length:]
            else:
                values_aligned = values
                other_values_aligned = other_values
            
            # Calculate correlation
            if len(set(values_aligned)) > 1 and len(set(other_values_aligned)) > 1:
                correlation = self._calculate_correlation(values_aligned, other_values_aligned)
                
                if abs(correlation) >= 0.8:  # Strong correlation threshold
                    confidence = abs(correlation)
                    severity = self._calculate_correlation_severity(abs(correlation))
                    
                    correlation_type = "positive" if correlation > 0 else "negative"
                    
                    pattern = Pattern(
                        pattern_id=self._generate_pattern_id(),
                        pattern_type=PatternType.CORRELATION,
                        severity=severity,
                        confidence=confidence,
                        description=f"Strong {correlation_type} correlation between {metric_name} and {other_metric_name}: {correlation:.3f}",
                        metric_name=metric_name,
                        detected_at=timestamps[-1],
                        time_window=len(values_aligned),
                        parameters={
                            "correlated_metric": other_metric_name,
                            "correlation": correlation,
                            "correlation_type": correlation_type,
                            "sample_size": len(values_aligned)
                        },
                        context={"other_metric_values": other_values_aligned[-10:]}
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    async def _detect_seasonal_pattern(self, metric_name: str, values: List[float], timestamps: List[float]) -> List[Pattern]:
        """Detect seasonal patterns (time-based regularity)."""
        patterns = []
        
        if len(values) < 50:  # Need more data for seasonal patterns
            return patterns
        
        # Convert timestamps to time-based features
        time_features = []
        for timestamp in timestamps:
            dt = time.localtime(timestamp)
            time_features.append({
                "hour": dt.tm_hour,
                "day_of_week": dt.tm_wday,
                "day_of_month": dt.tm_mday,
                "month": dt.tm_mon
            })
        
        # Check for hourly patterns
        hourly_patterns = self._detect_time_based_pattern(values, [f["hour"] for f in time_features], 24)
        if hourly_patterns:
            patterns.extend(hourly_patterns)
        
        # Check for daily patterns
        daily_patterns = self._detect_time_based_pattern(values, [f["day_of_week"] for f in time_features], 7)
        if daily_patterns:
            patterns.extend(daily_patterns)
        
        return patterns
    
    async def _detect_anomaly_pattern(self, metric_name: str, values: List[float], timestamps: List[float]) -> List[Pattern]:
        """Detect anomaly patterns (statistical outliers)."""
        patterns = []
        
        if len(values) < 20:
            return patterns
        
        # Use multiple anomaly detection methods
        
        # 1. Z-score based anomaly detection
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0
        
        if std > 0:
            z_scores = [(value - mean) / std for value in values]
            threshold = self.thresholds.get(metric_name, MetricThreshold(metric_name)).std_dev_threshold
            
            anomalies = []
            for i, z_score in enumerate(z_scores):
                if abs(z_score) >= threshold:
                    anomalies.append((i, z_score, values[i]))
            
            # Group consecutive anomalies
            if anomalies:
                anomaly_groups = self._group_consecutive_anomalies(anomalies)
                
                for group in anomaly_groups:
                    if len(group) >= 2:  # Only consider groups of 2 or more
                        confidence = min(max(abs(z_score) for _, z_score, _ in group) / (threshold * 2), 1.0)
                        severity = self._calculate_anomaly_severity(len(group), max(abs(z_score) for _, z_score, _ in group))
                        
                        pattern = Pattern(
                            pattern_id=self._generate_pattern_id(),
                            pattern_type=PatternType.ANOMALY,
                            severity=severity,
                            confidence=confidence,
                            description=f"Anomaly group detected in {metric_name}: {len(group)} outliers",
                            metric_name=metric_name,
                            detected_at=timestamps[group[-1][0]],
                            time_window=group[-1][0] - group[0][0] + 1,
                            parameters={
                                "anomaly_count": len(group),
                                "z_scores": [z_score for _, z_score, _ in group],
                                "values": [value for _, _, value in group],
                                "threshold": threshold
                            }
                        )
                        
                        patterns.append(pattern)
        
        # 2. Isolation forest-like approach (simplified)
        isolation_anomalies = self._detect_isolation_anomalies(values)
        if isolation_anomalies:
            # Convert isolation anomalies to patterns
            for anomaly_indices in isolation_anomalies:
                if len(anomaly_indices) >= 3:  # Group of 3 or more
                    confidence = 0.8  # High confidence for isolation-based detection
                    severity = PatternSeverity.MEDIUM
                    
                    pattern = Pattern(
                        pattern_id=self._generate_pattern_id(),
                        pattern_type=PatternType.ANOMALY,
                        severity=severity,
                        confidence=confidence,
                        description=f"Isolation anomaly detected in {metric_name}: {len(anomaly_indices)} points",
                        metric_name=metric_name,
                        detected_at=timestamps[anomaly_indices[-1]],
                        time_window=anomaly_indices[-1] - anomaly_indices[0] + 1,
                        parameters={
                            "anomaly_count": len(anomaly_indices),
                            "indices": anomaly_indices,
                            "method": "isolation"
                        }
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    async def _detect_trend_pattern(self, metric_name: str, values: List[float], timestamps: List[float]) -> List[Pattern]:
        """Detect trend patterns (consistent directional movement)."""
        patterns = []
        
        if len(values) < 15:
            return patterns
        
        # Calculate trend over different windows
        window_sizes = [10, 20, min(30, len(values) // 3)]
        
        for window_size in window_sizes:
            if window_size >= len(values):
                continue
            
            recent_values = values[-window_size:]
            
            # Calculate linear regression
            trend_slope = self._calculate_linear_trend(recent_values)
            
            # Determine if trend is significant
            threshold = self.thresholds.get(metric_name, MetricThreshold(metric_name)).trend_threshold
            
            if abs(trend_slope) >= threshold:
                trend_direction = "increasing" if trend_slope > 0 else "decreasing"
                
                # Calculate trend strength (R-squared)
                r_squared = self._calculate_trend_strength(recent_values)
                confidence = r_squared
                
                severity = self._calculate_trend_severity(abs(trend_slope), r_squared)
                
                pattern = Pattern(
                    pattern_id=self._generate_pattern_id(),
                    pattern_type=PatternType.TREND,
                    severity=severity,
                    confidence=confidence,
                    description=f"Strong {trend_direction} trend in {metric_name}: slope {trend_slope:.4f}",
                    metric_name=metric_name,
                    detected_at=timestamps[-1],
                    time_window=window_size,
                    parameters={
                        "trend_slope": trend_slope,
                        "trend_direction": trend_direction,
                        "r_squared": r_squared,
                        "threshold": threshold
                    }
                )
                
                patterns.append(pattern)
        
        return patterns
    
    async def _detect_burst_pattern(self, metric_name: str, values: List[float], timestamps: List[float]) -> List[Pattern]:
        """Detect burst patterns (sudden high activity periods)."""
        patterns = []
        
        if len(values) < 10:
            return patterns
        
        # Calculate moving average and standard deviation
        window_size = min(10, len(values) // 3)
        if window_size < 3:
            return patterns
        
        moving_averages = []
        moving_stds = []
        
        for i in range(window_size, len(values) + 1):
            window = values[i-window_size:i]
            moving_averages.append(statistics.mean(window))
            moving_stds.append(statistics.stdev(window) if len(window) > 1 else 0)
        
        # Detect bursts (values significantly above moving average)
        burst_threshold = 2.0  # 2 standard deviations above moving average
        burst_groups = []
        current_burst = []
        
        for i in range(window_size, len(values)):
            if i - window_size < len(moving_averages):
                ma = moving_averages[i - window_size]
                std = moving_stds[i - window_size]
                
                if std > 0:
                    z_score = (values[i] - ma) / std
                    if z_score >= burst_threshold:
                        current_burst.append(i)
                    else:
                        if len(current_burst) >= 3:  # Minimum burst length
                            burst_groups.append(current_burst)
                        current_burst = []
        
        # Add final burst group if active
        if len(current_burst) >= 3:
            burst_groups.append(current_burst)
        
        # Create patterns for detected bursts
        for burst_group in burst_groups:
            burst_values = [values[i] for i in burst_group]
            burst_intensity = statistics.mean(burst_values)
            max_intensity = max(burst_values)
            
            confidence = min(len(burst_group) / 10.0, 1.0)
            severity = self._calculate_burst_severity(len(burst_group), max_intensity)
            
            pattern = Pattern(
                pattern_id=self._generate_pattern_id(),
                pattern_type=PatternType.BURST,
                severity=severity,
                confidence=confidence,
                description=f"Burst detected in {metric_name}: {len(burst_group)} high-value points",
                metric_name=metric_name,
                detected_at=timestamps[burst_group[-1]],
                time_window=burst_group[-1] - burst_group[0] + 1,
                parameters={
                    "burst_length": len(burst_group),
                    "burst_intensity": burst_intensity,
                    "max_intensity": max_intensity,
                    "indices": burst_group
                }
            )
            
            patterns.append(pattern)
        
        return patterns
    
    def _detect_time_based_pattern(self, values: List[float], time_values: List[int], period: int) -> List[Pattern]:
        """Detect patterns based on time cycles (hourly, daily, etc.)."""
        patterns = []
        
        if len(values) < period * 2:  # Need at least 2 full periods
            return patterns
        
        # Group values by time period
        period_groups = defaultdict(list)
        for i, time_val in enumerate(time_values):
            if i < len(values):
                period_groups[time_val].append(values[i])
        
        # Calculate statistics for each period
        period_stats = {}
        for period_val, group_values in period_groups.items():
            if len(group_values) >= 3:  # Need enough samples
                period_stats[period_val] = {
                    "mean": statistics.mean(group_values),
                    "std": statistics.stdev(group_values) if len(group_values) > 1 else 0,
                    "count": len(group_values)
                }
        
        if len(period_stats) < period // 2:  # Need data for at least half the periods
            return patterns
        
        # Check for consistent patterns across periods
        means = [stats["mean"] for stats in period_stats.values()]
        if len(means) > 1:
            mean_std = statistics.stdev(means)
            mean_mean = statistics.mean(means)
            
            # Calculate coefficient of variation
            cv = mean_std / mean_mean if mean_mean != 0 else 0
            
            # Low CV indicates consistent pattern
            if cv <= 0.3:  # 30% or less variation
                confidence = max(0, 1 - (cv / 0.3))
                severity = PatternSeverity.LOW if cv <= 0.1 else PatternSeverity.MEDIUM
                
                pattern = Pattern(
                    pattern_id=self._generate_pattern_id(),
                    pattern_type=PatternType.SEASONAL,
                    severity=severity,
                    confidence=confidence,
                    description=f"Seasonal pattern detected with period {period}: CV {cv:.3f}",
                    metric_name="",  # Will be set by caller
                    detected_at=time.time(),
                    time_window=period,
                    parameters={
                        "period": period,
                        "coefficient_of_variation": cv,
                        "period_count": len(period_stats),
                        "period_means": period_stats
                    }
                )
                
                patterns.append(pattern)
        
        return patterns
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)
        sum_y2 = sum(yi * yi for yi in y)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y))
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def _calculate_linear_trend(self, values: List[float]) -> float:
        """Calculate linear trend (slope) using least squares."""
        n = len(values)
        if n < 2:
            return 0.0
        
        x = list(range(n))
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(xi * yi for xi, yi in zip(x, values))
        sum_x2 = sum(xi * xi for xi in x)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = n * sum_x2 - sum_x * sum_x
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def _calculate_trend_strength(self, values: List[float]) -> float:
        """Calculate R-squared for trend strength."""
        n = len(values)
        if n < 3:
            return 0.0
        
        # Calculate trend line
        slope = self._calculate_linear_trend(values)
        intercept = statistics.mean(values) - slope * (n - 1) / 2
        
        # Calculate total sum of squares
        y_mean = statistics.mean(values)
        ss_total = sum((y - y_mean) ** 2 for y in values)
        
        if ss_total == 0:
            return 0.0
        
        # Calculate residual sum of squares
        ss_residual = sum((values[i] - (slope * i + intercept)) ** 2 for i in range(n))
        
        # Calculate R-squared
        r_squared = 1 - (ss_residual / ss_total)
        return max(0, r_squared)
    
    def _calculate_trend_consistency(self, values: List[float]) -> float:
        """Calculate how consistent a trend is."""
        if len(values) < 5:
            return 0.0
        
        # Calculate trend for sliding windows
        window_size = len(values) // 3
        if window_size < 3:
            return 0.0
        
        trends = []
        for i in range(len(values) - window_size + 1):
            window = values[i:i + window_size]
            trend = self._calculate_linear_trend(window)
            trends.append(trend)
        
        if not trends:
            return 0.0
        
        # Check if all trends have the same sign
        positive_trends = sum(1 for t in trends if t > 0)
        negative_trends = sum(1 for t in trends if t < 0)
        
        consistency = max(positive_trends, negative_trends) / len(trends)
        return consistency
    
    def _verify_periodicity(self, values: List[float], period: int, tolerance: float = 0.3) -> bool:
        """Verify if a pattern is truly periodic."""
        if len(values) < period * 2:
            return False
        
        # Check correlation between values separated by the period
        correlations = []
        for i in range(len(values) - period):
            x = values[i:i + period]
            y = values[i + period:i + 2 * period]
            
            if len(x) == len(y) and len(x) > 1:
                correlation = self._calculate_correlation(x, y)
                correlations.append(abs(correlation))
        
        if not correlations:
            return False
        
        # Check if average correlation is above tolerance
        avg_correlation = statistics.mean(correlations)
        return avg_correlation >= (1 - tolerance)
    
    def _group_consecutive_anomalies(self, anomalies: List[Tuple[int, float, float]]) -> List[List[Tuple[int, float, float]]]:
        """Group consecutive anomalies into clusters."""
        if not anomalies:
            return []
        
        groups = []
        current_group = [anomalies[0]]
        
        for i in range(1, len(anomalies)):
            if anomalies[i][0] - anomalies[i-1][0] <= 3:  # Within 3 indices
                current_group.append(anomalies[i])
            else:
                groups.append(current_group)
                current_group = [anomalies[i]]
        
        groups.append(current_group)
        return groups
    
    def _detect_isolation_anomalies(self, values: List[float]) -> List[List[int]]:
        """Simplified isolation forest-like anomaly detection."""
        if len(values) < 10:
            return []
        
        # Use a simple approach: find points that are far from their neighbors
        anomaly_indices = []
        
        for i in range(1, len(values) - 1):
            prev_val = values[i-1]
            curr_val = values[i]
            next_val = values[i+1]
            
            # Calculate average distance to neighbors
            avg_neighbor = (prev_val + next_val) / 2
            distance = abs(curr_val - avg_neighbor)
            
            # Calculate local standard deviation
            local_window = values[max(0, i-2):min(len(values), i+3)]
            local_std = statistics.stdev(local_window) if len(local_window) > 1 else 0
            
            if local_std > 0:
                z_score = distance / local_std
                if z_score >= 2.5:  # High threshold for isolation
                    anomaly_indices.append(i)
        
        # Group consecutive anomalies
        if anomaly_indices:
            return self._group_consecutive_indices(anomaly_indices)
        
        return []
    
    def _group_consecutive_indices(self, indices: List[int]) -> List[List[int]]:
        """Group consecutive indices."""
        if not indices:
            return []
        
        groups = []
        current_group = [indices[0]]
        
        for i in range(1, len(indices)):
            if indices[i] - indices[i-1] <= 2:  # Within 2 indices
                current_group.append(indices[i])
            else:
                groups.append(current_group)
                current_group = [indices[i]]
        
        groups.append(current_group)
        return groups
    
    def _calculate_spike_severity(self, z_score: float) -> PatternSeverity:
        """Calculate severity for spike patterns."""
        if z_score >= 4.0:
            return PatternSeverity.CRITICAL
        elif z_score >= 3.0:
            return PatternSeverity.HIGH
        elif z_score >= 2.5:
            return PatternSeverity.MEDIUM
        else:
            return PatternSeverity.LOW
    
    def _calculate_drift_severity(self, percent_change: float) -> PatternSeverity:
        """Calculate severity for drift patterns."""
        if percent_change >= 0.5:  # 50% change
            return PatternSeverity.CRITICAL
        elif percent_change >= 0.3:  # 30% change
            return PatternSeverity.HIGH
        elif percent_change >= 0.15:  # 15% change
            return PatternSeverity.MEDIUM
        else:
            return PatternSeverity.LOW
    
    def _calculate_oscillation_severity(self, correlation: float, period: int) -> PatternSeverity:
        """Calculate severity for oscillation patterns."""
        if correlation >= 0.9 and period <= 10:
            return PatternSeverity.HIGH
        elif correlation >= 0.8:
            return PatternSeverity.MEDIUM
        else:
            return PatternSeverity.LOW
    
    def _calculate_correlation_severity(self, correlation: float) -> PatternSeverity:
        """Calculate severity for correlation patterns."""
        if correlation >= 0.95:
            return PatternSeverity.HIGH
        elif correlation >= 0.85:
            return PatternSeverity.MEDIUM
        else:
            return PatternSeverity.LOW
    
    def _calculate_anomaly_severity(self, anomaly_count: int, max_z_score: float) -> PatternSeverity:
        """Calculate severity for anomaly patterns."""
        if anomaly_count >= 5 or max_z_score >= 4.0:
            return PatternSeverity.CRITICAL
        elif anomaly_count >= 3 or max_z_score >= 3.0:
            return PatternSeverity.HIGH
        elif anomaly_count >= 2 or max_z_score >= 2.5:
            return PatternSeverity.MEDIUM
        else:
            return PatternSeverity.LOW
    
    def _calculate_trend_severity(self, slope: float, r_squared: float) -> PatternSeverity:
        """Calculate severity for trend patterns."""
        if r_squared >= 0.8 and abs(slope) >= 1.0:
            return PatternSeverity.HIGH
        elif r_squared >= 0.6 and abs(slope) >= 0.5:
            return PatternSeverity.MEDIUM
        else:
            return PatternSeverity.LOW
    
    def _calculate_burst_severity(self, burst_length: int, max_intensity: float) -> PatternSeverity:
        """Calculate severity for burst patterns."""
        if burst_length >= 10:
            return PatternSeverity.HIGH
        elif burst_length >= 5:
            return PatternSeverity.MEDIUM
        else:
            return PatternSeverity.LOW
    
    async def _handle_detected_pattern(self, pattern: Pattern):
        """Handle a newly detected pattern."""
        # Check if similar pattern already exists
        existing_pattern = None
        for existing in self.detected_patterns.values():
            if (existing.pattern_type == pattern.pattern_type and
                existing.metric_name == pattern.metric_name and
                abs(existing.detected_at - pattern.detected_at) < 300):  # Within 5 minutes
                existing_pattern = existing
                break
        
        if existing_pattern:
            # Update existing pattern
            existing_pattern.last_occurrence = pattern.detected_at
            existing_pattern.historical_occurrences += 1
            logger.debug(f"Updated existing pattern: {existing_pattern.pattern_id}")
            return
        
        # Register new pattern
        self.detected_patterns[pattern.pattern_id] = pattern
        self.pattern_history.append(pattern)
        self.stats["patterns_detected"] += 1
        self.stats["patterns_by_type"][pattern.pattern_type.value] += 1
        
        logger.warning(f"New pattern detected: {pattern.pattern_type.value} - {pattern.description}")
        
        # Adaptive learning
        if self.learning_enabled:
            await self._learn_from_pattern(pattern)
    
    async def _learn_from_pattern(self, pattern: Pattern):
        """Learn from detected patterns to improve detection."""
        # Update adaptive parameters based on pattern characteristics
        metric_name = pattern.metric_name
        
        if metric_name not in self.adaptive_parameters:
            self.adaptive_parameters[metric_name] = {}
        
        # Adjust thresholds based on pattern feedback
        if pattern.pattern_type == PatternType.SPIKE:
            current_threshold = self.thresholds.get(metric_name, MetricThreshold(metric_name)).std_dev_threshold
            if pattern.confidence > 0.8 and pattern.severity.value in ["high", "critical"]:
                # Pattern is strong, maybe lower threshold for future detection
                new_threshold = max(current_threshold * 0.95, 1.5)
                if metric_name in self.thresholds:
                    self.thresholds[metric_name].std_dev_threshold = new_threshold
                else:
                    self.thresholds[metric_name] = MetricThreshold(metric_name, std_dev_threshold=new_threshold)
        
        elif pattern.pattern_type == PatternType.DRIFT:
            current_threshold = self.thresholds.get(metric_name, MetricThreshold(metric_name)).trend_threshold
            if pattern.confidence > 0.8:
                # Adjust trend threshold
                new_threshold = max(current_threshold * 0.98, 0.05)
                if metric_name in self.thresholds:
                    self.thresholds[metric_name].trend_threshold = new_threshold
                else:
                    self.thresholds[metric_name] = MetricThreshold(metric_name, trend_threshold=new_threshold)
        
        logger.debug(f"Updated adaptive parameters for {metric_name}")
    
    def _generate_pattern_id(self) -> str:
        """Generate unique pattern ID."""
        import hashlib
        import os
        
        timestamp = int(time.time())
        random_hash = hashlib.md5(f"{timestamp}{os.getpid()}".encode()).hexdigest()[:8]
        return f"pattern_{timestamp}_{random_hash}"
    
    # Public API methods
    
    def set_metric_threshold(self, threshold: MetricThreshold):
        """Set threshold configuration for a metric."""
        self.thresholds[threshold.metric_name] = threshold
        logger.info(f"Set threshold for metric: {threshold.metric_name}")
    
    def get_detected_patterns(self, pattern_type: Optional[PatternType] = None, 
                            metric_name: Optional[str] = None) -> List[Pattern]:
        """Get detected patterns with optional filtering."""
        patterns = list(self.detected_patterns.values())
        
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        
        if metric_name:
            patterns = [p for p in patterns if p.metric_name == metric_name]
        
        return patterns
    
    def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get pattern detection statistics."""
        return {
            "total_patterns_detected": self.stats["patterns_detected"],
            "active_patterns": len(self.detected_patterns),
            "patterns_by_type": dict(self.stats["patterns_by_type"]),
            "total_metrics_processed": self.stats["total_metrics_processed"],
            "metrics_tracked": len(self.metrics_history),
            "adaptive_thresholds": len(self.thresholds),
            "pattern_history_size": len(self.pattern_history)
        }
    
    def clear_pattern_history(self, older_than_hours: int = 24):
        """Clear old pattern history."""
        cutoff_time = time.time() - (older_than_hours * 3600)
        
        # Clear detected patterns
        patterns_to_remove = [
            pattern_id for pattern_id, pattern in self.detected_patterns.items()
            if pattern.detected_at < cutoff_time
        ]
        
        for pattern_id in patterns_to_remove:
            del self.detected_patterns[pattern_id]
        
        # Clear pattern history
        self.pattern_history = [
            pattern for pattern in self.pattern_history
            if pattern.detected_at >= cutoff_time
        ]
        
        logger.info(f"Cleared pattern history older than {older_than_hours} hours")
    
    def export_patterns(self, filepath: str):
        """Export detected patterns to JSON file."""
        import json
        
        data = {
            "detected_patterns": {pid: {
                "pattern_type": p.pattern_type.value,
                "severity": p.severity.value,
                "confidence": p.confidence,
                "description": p.description,
                "metric_name": p.metric_name,
                "detected_at": p.detected_at,
                "time_window": p.time_window,
                "parameters": p.parameters,
                "historical_occurrences": p.historical_occurrences,
                "last_occurrence": p.last_occurrence
            } for pid, p in self.detected_patterns.items()},
            "pattern_history": [{
                "pattern_type": p.pattern_type.value,
                "severity": p.severity.value,
                "confidence": p.confidence,
                "description": p.description,
                "metric_name": p.metric_name,
                "detected_at": p.detected_at,
                "parameters": p.parameters
            } for p in self.pattern_history],
            "thresholds": {name: {
                "min_value": t.min_value,
                "max_value": t.max_value,
                "std_dev_threshold": t.std_dev_threshold,
                "trend_threshold": t.trend_threshold,
                "anomaly_threshold": t.anomaly_threshold
            } for name, t in self.thresholds.items()},
            "statistics": self.stats,
            "export_timestamp": time.time()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Exported pattern data to {filepath}")


# Import asyncio for async operations
import asyncio

# Global pattern detector instance
pattern_detector = PatternDetector()