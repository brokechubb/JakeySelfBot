import time
import threading
import logging
from typing import Dict, Optional, Tuple, Any
from collections import defaultdict, deque
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class RateLimitViolation:
    """Represents a rate limit violation with user context."""
    
    def __init__(self, user_id: str, operation: str, limit_type: str, 
                 current_count: int, limit: int, window_start: float):
        self.user_id = user_id
        self.operation = operation
        self.limit_type = limit_type
        self.current_count = current_count
        self.limit = limit
        self.window_start = window_start
        self.timestamp = time.time()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'operation': self.operation,
            'limit_type': self.limit_type,
            'current_count': self.current_count,
            'limit': self.limit,
            'window_start': self.window_start,
            'timestamp': self.timestamp
        }

class UserRateLimiter:
    """Per-user rate limiting with different limits for different operations."""
    
    def __init__(self):
        # Per-user tracking: {user_id: {operation: deque of timestamps}}
        self.user_requests: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))
        
        # Per-user violation tracking: {user_id: [violations]}
        self.violations: Dict[str, list] = defaultdict(list)
        
        # Per-user penalty multipliers: {user_id: multiplier}
        self.penalty_multipliers: Dict[str, float] = {}
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Default rate limits (requests per window)
        self.default_limits = {
            # Burst limits (short-term, per minute)
            'burst': {
                'window': 60,  # 1 minute
                'limits': {
                    'generate_image': 3,
                    'analyze_image': 3,
                    'web_search': 10,
                    'company_research': 8,
                    'crawling': 5,
                    'get_crypto_price': 20,
                    'get_stock_price': 15,
                    'tip_user': 10,
                    'check_balance': 15,
                    'discord_send_message': 20,
                    'discord_send_dm': 10,
                    'default': 30
                }
            },
            # Sustained limits (long-term, per hour)
            'sustained': {
                'window': 3600,  # 1 hour
                'limits': {
                    'generate_image': 20,
                    'analyze_image': 20,
                    'web_search': 100,
                    'company_research': 50,
                    'crawling': 30,
                    'get_crypto_price': 200,
                    'get_stock_price': 150,
                    'tip_user': 50,
                    'check_balance': 100,
                    'discord_send_message': 200,
                    'discord_send_dm': 50,
                    'default': 150
                }
            },
            # Daily limits (per 24 hours)
            'daily': {
                'window': 86400,  # 24 hours
                'limits': {
                    'generate_image': 50,
                    'analyze_image': 50,
                    'web_search': 500,
                    'company_research': 200,
                    'crawling': 100,
                    'get_crypto_price': 1000,
                    'get_stock_price': 750,
                    'tip_user': 200,
                    'check_balance': 500,
                    'discord_send_message': 1000,
                    'discord_send_dm': 200,
                    'default': 750
                }
            }
        }
        
        # Penalty tiers for repeated violations
        self.penalty_tiers = [
            {'violations': 3, 'multiplier': 1.5, 'duration': 300},    # 3 violations = 1.5x for 5 min
            {'violations': 5, 'multiplier': 2.0, 'duration': 900},    # 5 violations = 2x for 15 min
            {'violations': 10, 'multiplier': 3.0, 'duration': 3600},   # 10 violations = 3x for 1 hour
            {'violations': 15, 'multiplier': 5.0, 'duration': 7200},   # 15 violations = 5x for 2 hours
            {'violations': 20, 'multiplier': 10.0, 'duration': 14400}  # 20 violations = 10x for 4 hours
        ]
        
        # Monitoring
        self.total_requests = 0
        self.total_violations = 0
        self.start_time = time.time()
        
    def get_user_penalty_multiplier(self, user_id: str) -> float:
        """Get current penalty multiplier for a user."""
        with self.lock:
            # Clean expired penalties
            if user_id in self.penalty_multipliers:
                # Check if penalty should expire (simplified - in real implementation, track expiry)
                pass
            return self.penalty_multipliers.get(user_id, 1.0)
    
    def apply_penalty(self, user_id: str, violation_count: int):
        """Apply penalty multiplier based on violation count."""
        with self.lock:
            for tier in reversed(self.penalty_tiers):
                if violation_count >= tier['violations']:
                    self.penalty_multipliers[user_id] = tier['multiplier']
                    logger.warning(f"Applied penalty multiplier {tier['multiplier']}x to user {user_id} for {violation_count} violations")
                    
                    # Schedule penalty removal (simplified - use background task in production)
                    return tier
    
    def clean_old_requests(self, user_id: str, operation: str, window: float):
        """Clean requests older than the window."""
        current_time = time.time()
        cutoff_time = current_time - window
        
        if user_id in self.user_requests and operation in self.user_requests[user_id]:
            requests = self.user_requests[user_id][operation]
            while requests and requests[0] < cutoff_time:
                requests.popleft()
    
    def check_rate_limit(self, user_id: str, operation: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user is within rate limits for an operation.
        
        Returns:
            Tuple of (is_allowed, violation_reason)
        """
        with self.lock:
            current_time = time.time()
            penalty_multiplier = self.get_user_penalty_multiplier(user_id)
            
            # Check each limit type
            for limit_type, config in self.default_limits.items():
                window = config['window']
                base_limit = config['limits'].get(operation, config['limits']['default'])
                
                # Apply penalty multiplier
                effective_limit = int(base_limit / penalty_multiplier)
                effective_limit = max(1, effective_limit)  # Ensure at least 1 request allowed
                
                # Clean old requests
                self.clean_old_requests(user_id, operation, window)
                
                # Count current requests
                request_count = len(self.user_requests[user_id][operation])
                
                if request_count >= effective_limit:
                    # Rate limit violated
                    violation = RateLimitViolation(
                        user_id=user_id,
                        operation=operation,
                        limit_type=limit_type,
                        current_count=request_count,
                        limit=effective_limit,
                        window_start=current_time - window
                    )
                    
                    # Record violation
                    self.violations[user_id].append(violation)
                    self.total_violations += 1
                    
                    # Apply penalty if needed
                    user_violation_count = len([v for v in self.violations[user_id] 
                                               if current_time - v.timestamp < 3600])  # Last hour
                    self.apply_penalty(user_id, user_violation_count)
                    
                    # Log violation
                    logger.warning(f"Rate limit violation: User {user_id} exceeded {limit_type} limit for {operation} "
                                 f"({request_count}/{effective_limit})")
                    
                    reason = f"Rate limit exceeded: {request_count}/{effective_limit} requests per {limit_type}"
                    return False, reason
            
            # Record this request
            self.user_requests[user_id][operation].append(current_time)
            self.total_requests += 1
            
            return True, None
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get rate limiting statistics for a specific user."""
        with self.lock:
            current_time = time.time()
            user_requests = self.user_requests.get(user_id, {})
            user_violations = self.violations.get(user_id, [])
            penalty_multiplier = self.get_user_penalty_multiplier(user_id)
            
            stats = {
                'user_id': user_id,
                'penalty_multiplier': penalty_multiplier,
                'total_violations': len(user_violations),
                'recent_violations': len([v for v in user_violations if current_time - v.timestamp < 3600]),
                'current_usage': {}
            }
            
            # Current usage for each operation
            for operation in user_requests:
                stats['current_usage'][operation] = {}
                for limit_type, config in self.default_limits.items():
                    window = config['window']
                    self.clean_old_requests(user_id, operation, window)
                    count = len(user_requests[operation])
                    base_limit = config['limits'].get(operation, config['limits']['default'])
                    effective_limit = int(base_limit / penalty_multiplier)
                    effective_limit = max(1, effective_limit)
                    
                    stats['current_usage'][operation][limit_type] = {
                        'current': count,
                        'limit': effective_limit,
                        'percentage': (count / effective_limit) * 100
                    }
            
            return stats
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get overall system rate limiting statistics."""
        with self.lock:
            current_time = time.time()
            uptime = current_time - self.start_time
            
            # Active users (users with requests in last hour)
            active_users = set()
            for user_id in self.user_requests:
                for operation in self.user_requests[user_id]:
                    self.clean_old_requests(user_id, operation, 3600)
                    if self.user_requests[user_id][operation]:
                        active_users.add(user_id)
            
            # Recent violations (last hour)
            recent_violations = []
            for user_id, violations in self.violations.items():
                recent_violations.extend([v for v in violations if current_time - v.timestamp < 3600])
            
            return {
                'uptime_seconds': uptime,
                'total_requests': self.total_requests,
                'total_violations': self.total_violations,
                'requests_per_second': self.total_requests / uptime if uptime > 0 else 0,
                'active_users_count': len(active_users),
                'total_users_count': len(self.user_requests),
                'recent_violations_count': len(recent_violations),
                'users_with_penalties': len(self.penalty_multipliers),
                'average_penalty_multiplier': sum(self.penalty_multipliers.values()) / len(self.penalty_multipliers) if self.penalty_multipliers else 1.0
            }
    
    def reset_user_limits(self, user_id: str):
        """Reset rate limits for a specific user (admin function)."""
        with self.lock:
            if user_id in self.user_requests:
                del self.user_requests[user_id]
            if user_id in self.violations:
                del self.violations[user_id]
            if user_id in self.penalty_multipliers:
                del self.penalty_multipliers[user_id]
            logger.info(f"Reset rate limits for user {user_id}")
    
    def cleanup_expired_data(self):
        """Clean up expired data to prevent memory leaks."""
        with self.lock:
            current_time = time.time()
            
            # Clean old violations (older than 24 hours)
            for user_id in list(self.violations.keys()):
                self.violations[user_id] = [v for v in self.violations[user_id] 
                                           if current_time - v.timestamp < 86400]
                if not self.violations[user_id]:
                    del self.violations[user_id]
            
            # Clean old request data (older than 24 hours)
            for user_id in list(self.user_requests.keys()):
                for operation in list(self.user_requests[user_id].keys()):
                    self.clean_old_requests(user_id, operation, 86400)
                    if not self.user_requests[user_id][operation]:
                        del self.user_requests[user_id][operation]
                if not self.user_requests[user_id]:
                    del self.user_requests[user_id]
            
            # Clean expired penalties (simplified - should track expiry time)
            # In production, store expiry timestamps with penalties
            expired_penalties = []
            for user_id, multiplier in self.penalty_multipliers.items():
                # Check if user has recent violations to maintain penalty
                recent_violations = [v for v in self.violations.get(user_id, []) 
                                   if current_time - v.timestamp < 3600]
                if not recent_violations and multiplier > 1.0:
                    expired_penalties.append(user_id)
            
            for user_id in expired_penalties:
                del self.penalty_multipliers[user_id]
                logger.info(f"Removed expired penalty for user {user_id}")

class RateLimitMiddleware:
    """Middleware to apply rate limiting to tool operations."""
    
    def __init__(self, rate_limiter: UserRateLimiter):
        self.rate_limiter = rate_limiter
        self.logger = logging.getLogger(__name__)
    
    def check_request(self, user_id: str, operation: str) -> Tuple[bool, Optional[str]]:
        """Check if a request should be allowed."""
        return self.rate_limiter.check_rate_limit(user_id, operation)
    
    def get_rate_limit_info(self, user_id: str, operation: str) -> Dict[str, Any]:
        """Get detailed rate limit information for user and operation."""
        stats = self.rate_limiter.get_user_stats(user_id)
        current_usage = stats['current_usage'].get(operation, {})
        
        return {
            'user_id': user_id,
            'operation': operation,
            'penalty_multiplier': stats['penalty_multiplier'],
            'total_violations': stats['total_violations'],
            'recent_violations': stats['recent_violations'],
            'current_usage': current_usage
        }

# Global rate limiter instance
user_rate_limiter = UserRateLimiter()
rate_limit_middleware = RateLimitMiddleware(user_rate_limiter)

# Background cleanup task
def cleanup_task():
    """Background task to clean up expired data."""
    while True:
        try:
            user_rate_limiter.cleanup_expired_data()
            time.sleep(300)  # Run every 5 minutes
        except Exception as e:
            logger.error(f"Error in rate limit cleanup task: {e}")
            time.sleep(60)  # Retry after 1 minute on error

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()