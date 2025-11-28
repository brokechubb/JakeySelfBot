#!/usr/bin/env python3
"""
Rate Limiting Monitor - Real-time monitoring dashboard for rate limiting system
"""

import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tools.rate_limiter import user_rate_limiter
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    print("❌ Rate limiting system not available")
    RATE_LIMITING_AVAILABLE = False

class RateLimitMonitor:
    """Real-time monitoring for rate limiting system."""
    
    def __init__(self):
        self.running = False
        self.start_time = time.time()
        
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        if not RATE_LIMITING_AVAILABLE:
            return {"error": "Rate limiting not available"}
        
        system_stats = user_rate_limiter.get_system_stats()
        
        # Get top violators
        top_violators = self.get_top_violators()
        
        # Get active users
        active_users = self.get_active_users()
        
        # Get operation breakdown
        operation_stats = self.get_operation_stats()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime": system_stats['uptime_seconds'],
            "system": {
                "total_requests": system_stats['total_requests'],
                "total_violations": system_stats['total_violations'],
                "requests_per_second": system_stats['requests_per_second'],
                "active_users": system_stats['active_users_count'],
                "total_users": system_stats['total_users_count'],
                "recent_violations": system_stats['recent_violations_count'],
                "violation_rate": (system_stats['total_violations'] / system_stats['total_requests'] * 100) if system_stats['total_requests'] > 0 else 0
            },
            "penalties": {
                "users_with_penalties": system_stats['users_with_penalties'],
                "average_penalty": system_stats['average_penalty_multiplier']
            },
            "top_violators": top_violators,
            "active_users": active_users,
            "operations": operation_stats
        }
    
    def get_top_violators(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get users with the most violations."""
        if not RATE_LIMITING_AVAILABLE:
            return []
        
        violators = []
        current_time = time.time()
        
        for user_id, violations in user_rate_limiter.violations.items():
            # Count recent violations (last hour)
            recent_violations = [v for v in violations if current_time - v.timestamp < 3600]
            
            if recent_violations:
                penalty = user_rate_limiter.get_user_penalty_multiplier(user_id)
                
                violators.append({
                    "user_id": user_id,
                    "total_violations": len(violations),
                    "recent_violations": len(recent_violations),
                    "penalty_multiplier": penalty,
                    "last_violation": max(v.timestamp for v in violations)
                })
        
        # Sort by recent violations
        violators.sort(key=lambda x: x['recent_violations'], reverse=True)
        return violators[:limit]
    
    def get_active_users(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most active users."""
        if not RATE_LIMITING_AVAILABLE:
            return []
        
        active_users = []
        current_time = time.time()
        
        for user_id, operations in user_rate_limiter.user_requests.items():
            total_requests = 0
            recent_requests = 0
            
            for operation, requests in operations.items():
                total_requests += len(requests)
                recent_requests += len([r for r in requests if current_time - r < 3600])
            
            if recent_requests > 0:
                penalty = user_rate_limiter.get_user_penalty_multiplier(user_id)
                
                active_users.append({
                    "user_id": user_id,
                    "total_requests": total_requests,
                    "recent_requests": recent_requests,
                    "penalty_multiplier": penalty
                })
        
        # Sort by recent requests
        active_users.sort(key=lambda x: x['recent_requests'], reverse=True)
        return active_users[:limit]
    
    def get_operation_stats(self) -> Dict[str, Any]:
        """Get operation-specific statistics."""
        if not RATE_LIMITING_AVAILABLE:
            return {}
        
        operation_counts = {}
        operation_violations = {}
        
        # Count requests per operation
        for user_operations in user_rate_limiter.user_requests.values():
            for operation, requests in user_operations.items():
                operation_counts[operation] = operation_counts.get(operation, 0) + len(requests)
        
        # Count violations per operation
        for violations in user_rate_limiter.violations.values():
            for violation in violations:
                operation = violation.operation
                operation_violations[operation] = operation_violations.get(operation, 0) + 1
        
        # Calculate violation rates
        operation_stats = {}
        for operation in operation_counts:
            requests = operation_counts[operation]
            violations = operation_violations.get(operation, 0)
            violation_rate = (violations / requests * 100) if requests > 0 else 0
            
            operation_stats[operation] = {
                "requests": requests,
                "violations": violations,
                "violation_rate": violation_rate
            }
        
        return operation_stats
    
    def print_dashboard(self):
        """Print a formatted dashboard to console."""
        data = self.get_dashboard_data()
        
        if "error" in data:
            print(f"❌ {data['error']}")
            return
        
        print("\n" + "="*80)
        print(f"🚀 RATE LIMITING DASHBOARD - {data['timestamp']}")
        print("="*80)
        
        # System Overview
        system = data['system']
        print(f"\n📊 SYSTEM OVERVIEW:")
        print(f"   Total Requests: {system['total_requests']:,}")
        print(f"   Total Violations: {system['total_violations']:,}")
        print(f"   Requests/Second: {system['requests_per_second']:.2f}")
        print(f"   Active Users: {system['active_users']}")
        print(f"   Total Users: {system['total_users']}")
        print(f"   Violation Rate: {system['violation_rate']:.2f}%")
        
        # Penalties
        penalties = data['penalties']
        print(f"\n🔥 PENALTIES:")
        print(f"   Users with Penalties: {penalties['users_with_penalties']}")
        print(f"   Average Penalty Multiplier: {penalties['average_penalty']:.2f}x")
        
        # Top Violators
        if data['top_violators']:
            print(f"\n⚠️ TOP VIOLATORS:")
            for i, violator in enumerate(data['top_violators'][:5], 1):
                last_violation = datetime.fromtimestamp(violator['last_violation']).strftime('%H:%M:%S')
                print(f"   {i}. User {violator['user_id']}: {violator['recent_violations']} recent violations "
                      f"(penalty: {violator['penalty_multiplier']}x, last: {last_violation})")
        
        # Active Users
        if data['active_users']:
            print(f"\n👥 MOST ACTIVE USERS:")
            for i, user in enumerate(data['active_users'][:5], 1):
                print(f"   {i}. User {user['user_id']}: {user['recent_requests']} recent requests "
                      f"(penalty: {user['penalty_multiplier']}x)")
        
        # Operations
        if data['operations']:
            print(f"\n🔧 OPERATIONS:")
            # Sort by violation rate
            sorted_ops = sorted(data['operations'].items(), 
                              key=lambda x: x[1]['violation_rate'], reverse=True)
            
            for operation, stats in sorted_ops[:10]:
                emoji = "🟢" if stats['violation_rate'] < 5 else "🟡" if stats['violation_rate'] < 15 else "🔴"
                print(f"   {emoji} {operation}: {stats['requests']} requests, "
                      f"{stats['violations']} violations ({stats['violation_rate']:.1f}%)")
        
        print("\n" + "="*80)
    
    def start_monitoring(self, interval: int = 30):
        """Start real-time monitoring."""
        if not RATE_LIMITING_AVAILABLE:
            print("❌ Cannot start monitoring: Rate limiting system not available")
            return
        
        self.running = True
        print(f"🚀 Starting rate limit monitoring (updates every {interval} seconds)")
        print("   Press Ctrl+C to stop monitoring")
        
        try:
            while self.running:
                self.print_dashboard()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
            self.running = False
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.running = False
    
    def export_report(self, filename: str = None) -> str:
        """Export detailed report to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rate_limit_report_{timestamp}.json"
        
        data = self.get_dashboard_data()
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            print(f"📄 Report exported to {filename}")
            return filename
        except Exception as e:
            print(f"❌ Failed to export report: {e}")
            return None
    
    def check_health(self) -> Dict[str, Any]:
        """Check system health and return status."""
        if not RATE_LIMITING_AVAILABLE:
            return {"status": "error", "message": "Rate limiting not available"}
        
        system_stats = user_rate_limiter.get_system_stats()
        
        # Health checks
        health = {
            "status": "healthy",
            "checks": []
        }
        
        # Check 1: Violation rate
        violation_rate = (system_stats['total_violations'] / system_stats['total_requests'] * 100) if system_stats['total_requests'] > 0 else 0
        if violation_rate > 20:
            health["status"] = "warning"
            health["checks"].append({
                "name": "violation_rate",
                "status": "warning",
                "message": f"High violation rate: {violation_rate:.1f}%"
            })
        else:
            health["checks"].append({
                "name": "violation_rate",
                "status": "ok",
                "message": f"Violation rate: {violation_rate:.1f}%"
            })
        
        # Check 2: Penalty users
        if system_stats['users_with_penalties'] > system_stats['active_users_count'] * 0.5:
            health["status"] = "warning"
            health["checks"].append({
                "name": "penalty_users",
                "status": "warning",
                "message": f"Many users with penalties: {system_stats['users_with_penalties']}"
            })
        else:
            health["checks"].append({
                "name": "penalty_users",
                "status": "ok",
                "message": f"Users with penalties: {system_stats['users_with_penalties']}"
            })
        
        # Check 3: Request rate
        if system_stats['requests_per_second'] > 100:
            health["status"] = "warning"
            health["checks"].append({
                "name": "request_rate",
                "status": "warning",
                "message": f"High request rate: {system_stats['requests_per_second']:.1f}/s"
            })
        else:
            health["checks"].append({
                "name": "request_rate",
                "status": "ok",
                "message": f"Request rate: {system_stats['requests_per_second']:.1f}/s"
            })
        
        return health


def main():
    """Main function for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Rate Limiting Monitor")
    parser.add_argument("--monitor", action="store_true", help="Start real-time monitoring")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in seconds")
    parser.add_argument("--report", action="store_true", help="Export report to JSON")
    parser.add_argument("--health", action="store_true", help="Check system health")
    parser.add_argument("--dashboard", action="store_true", help="Show one-time dashboard")
    
    args = parser.parse_args()
    
    monitor = RateLimitMonitor()
    
    if args.monitor:
        monitor.start_monitoring(args.interval)
    elif args.report:
        monitor.export_report()
    elif args.health:
        health = monitor.check_health()
        print(f"Health Status: {health['status'].upper()}")
        for check in health['checks']:
            status_emoji = "✅" if check['status'] == 'ok' else "⚠️"
            print(f"   {status_emoji} {check['name']}: {check['message']}")
    elif args.dashboard:
        monitor.print_dashboard()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()