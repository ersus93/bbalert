"""
Telemetry system for bbalert bot.

Provides event tracking, user analytics, and historical data storage
for monitoring bot usage and user engagement.
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from collections import defaultdict
from contextlib import contextmanager
from threading import Lock

from utils.logger import logger
from core.config import EVENTS_LOG_PATH

# --- Constants ---
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CLEANUP_DAYS = 90
LOCK_TIMEOUT_SECONDS = 5

VALID_EVENT_TYPES = {
    'user_joined',
    'command_used',
    'alert_triggered',
    'subscription_started'
}

# --- Thread Safety ---
_file_lock = Lock()


class TelemetryError(Exception):
    """Custom exception for telemetry operations."""
    pass


class EventLogCorruptedError(TelemetryError):
    """Raised when the event log file is corrupted."""
    pass


@contextmanager
def _atomic_write(filepath: str):
    """
    Context manager for atomic file writes.
    Writes to a temporary file and renames it only on success.
    """
    temp_path = f"{filepath}.tmp"
    try:
        yield temp_path
        # Atomic rename only happens if no exception was raised
        os.replace(temp_path, filepath)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


def _ensure_data_dir():
    """Ensure the data directory exists."""
    data_dir = os.path.dirname(EVENTS_LOG_PATH)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"Created data directory: {data_dir}")


def _load_events() -> List[Dict[str, Any]]:
    """
    Load events from the events log file.
    
    Returns:
        List of event dictionaries
        
    Raises:
        EventLogCorruptedError: If the JSON file is corrupted
    """
    if not os.path.exists(EVENTS_LOG_PATH):
        return []
    
    # Check file size before reading
    try:
        file_size = os.path.getsize(EVENTS_LOG_PATH)
        if file_size > MAX_FILE_SIZE_BYTES:
            logger.warning(f"Event log file exceeds {MAX_FILE_SIZE_MB}MB ({file_size} bytes). "
                          "Truncating old events.")
            _rotate_log_file()
    except OSError as e:
        logger.warning(f"Could not check event log file size: {e}")
    
    try:
        with open(EVENTS_LOG_PATH, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return []
            events = json.loads(content)
            if not isinstance(events, list):
                raise EventLogCorruptedError("Event log is not a valid JSON array")
            return events
    except json.JSONDecodeError as e:
        logger.error(f"Event log file is corrupted: {e}")
        raise EventLogCorruptedError(f"Failed to parse event log: {e}")
    except OSError as e:
        logger.error(f"Failed to read event log file: {e}")
        raise TelemetryError(f"Failed to read event log: {e}")


def _save_events(events: List[Dict[str, Any]]) -> None:
    """
    Save events to the events log file atomically.
    
    Args:
        events: List of event dictionaries to save
    """
    _ensure_data_dir()
    
    with _atomic_write(EVENTS_LOG_PATH) as temp_path:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)


def _rotate_log_file() -> None:
    """
    Rotate the log file when it exceeds max size.
    Keeps the most recent events and archives the old ones.
    """
    try:
        events = _load_events()
        cutoff = int((datetime.now() - timedelta(days=30)).timestamp())
        recent_events = [e for e in events if e.get('timestamp', 0) > cutoff]
        
        # If still too large, keep only last 1000 events
        if len(recent_events) > 1000:
            recent_events = recent_events[-1000:]
        
        _save_events(recent_events)
        logger.info(f"Rotated event log. Kept {len(recent_events)} recent events.")
    except Exception as e:
        logger.error(f"Failed to rotate log file: {e}")


def _cleanup_old_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove events older than CLEANUP_DAYS.
    
    Args:
        events: List of all events
        
    Returns:
        Filtered list of recent events
    """
    cutoff_time = int((datetime.now() - timedelta(days=CLEANUP_DAYS)).timestamp())
    cleaned = [e for e in events if e.get('timestamp', 0) > cutoff_time]
    
    removed_count = len(events) - len(cleaned)
    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} events older than {CLEANUP_DAYS} days")
    
    return cleaned


def log_event(event_type: str, user_id: Union[int, str], metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Log an event to the telemetry system.
    
    Args:
        event_type: Type of event (must be in VALID_EVENT_TYPES)
        user_id: Unique identifier for the user
        metadata: Optional dictionary with additional event data
        
    Returns:
        True if event was logged successfully, False otherwise
        
    Raises:
        TelemetryError: If the event type is invalid
    """
    if event_type not in VALID_EVENT_TYPES:
        logger.warning(f"Invalid event type: {event_type}")
        return False
    
    event = {
        'event_type': event_type,
        'user_id': str(user_id),
        'timestamp': int(time.time()),
        'metadata': metadata or {}
    }
    
    # Acquire lock with timeout
    acquired = _file_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS)
    if not acquired:
        logger.error("Failed to acquire telemetry lock within timeout")
        return False
    
    try:
        try:
            events = _load_events()
        except EventLogCorruptedError:
            # Start fresh if file is corrupted
            logger.warning("Starting fresh event log due to corruption")
            events = []
        
        events.append(event)
        events = _cleanup_old_events(events)
        
        _save_events(events)
        
        # Log to main logger at debug level
        logger.debug(f"Telemetry event logged: {event_type} for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to log telemetry event: {e}")
        return False
    finally:
        _file_lock.release()


def get_event_stats(days: int = 30) -> Dict[str, Any]:
    """
    Get aggregated statistics for events within the specified time period.
    
    Args:
        days: Number of days to look back (default: 30)
        
    Returns:
        Dictionary containing:
            - total_events: Total number of events
            - events_by_type: Count per event type
            - unique_users: Number of unique users
            - events_by_day: Daily breakdown
            - most_active_user: User with most events
            - period_days: The period covered
    """
    acquired = _file_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS)
    if not acquired:
        logger.error("Failed to acquire telemetry lock within timeout")
        return _empty_stats(days)
    
    try:
        try:
            events = _load_events()
        except EventLogCorruptedError:
            logger.warning("Event log corrupted, returning empty stats")
            return _empty_stats(days)
        
        cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp())
        recent_events = [e for e in events if e.get('timestamp', 0) > cutoff_time]
        
        if not recent_events:
            return _empty_stats(days)
        
        # Aggregate stats
        events_by_type = defaultdict(int)
        events_by_day = defaultdict(int)
        user_events = defaultdict(int)
        
        for event in recent_events:
            # By type
            events_by_type[event.get('event_type', 'unknown')] += 1
            
            # By day
            ts = event.get('timestamp', 0)
            day_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            events_by_day[day_str] += 1
            
            # By user
            user_events[event.get('user_id', 'unknown')] += 1
        
        # Find most active user
        most_active_user = None
        most_active_count = 0
        for user_id, count in user_events.items():
            if count > most_active_count:
                most_active_count = count
                most_active_user = user_id
        
        return {
            'total_events': len(recent_events),
            'events_by_type': dict(events_by_type),
            'unique_users': len(user_events),
            'events_by_day': dict(sorted(events_by_day.items())),
            'most_active_user': {
                'user_id': most_active_user,
                'event_count': most_active_count
            } if most_active_user else None,
            'period_days': days,
            'period_start': datetime.fromtimestamp(cutoff_time).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get event stats: {e}")
        return _empty_stats(days)
    finally:
        _file_lock.release()


def _empty_stats(days: int) -> Dict[str, Any]:
    """Return empty stats structure."""
    return {
        'total_events': 0,
        'events_by_type': {},
        'unique_users': 0,
        'events_by_day': {},
        'most_active_user': None,
        'period_days': days,
        'period_start': (datetime.now() - timedelta(days=days)).isoformat()
    }


def get_user_journey(user_id: Union[int, str], days: int = 30) -> List[Dict[str, Any]]:
    """
    Get the activity timeline for a specific user.
    
    Args:
        user_id: The user ID to query
        days: Number of days to look back (default: 30)
        
    Returns:
        List of events for the user, sorted by timestamp (newest first)
    """
    acquired = _file_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS)
    if not acquired:
        logger.error("Failed to acquire telemetry lock within timeout")
        return []
    
    try:
        try:
            events = _load_events()
        except EventLogCorruptedError:
            logger.warning("Event log corrupted, returning empty journey")
            return []
        
        cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp())
        user_id_str = str(user_id)
        
        user_events = [
            {
                'event_type': e.get('event_type'),
                'timestamp': e.get('timestamp'),
                'datetime': datetime.fromtimestamp(e.get('timestamp', 0)).isoformat(),
                'metadata': e.get('metadata', {})
            }
            for e in events
            if e.get('user_id') == user_id_str and e.get('timestamp', 0) > cutoff_time
        ]
        
        # Sort by timestamp descending (newest first)
        user_events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        return user_events
        
    except Exception as e:
        logger.error(f"Failed to get user journey for {user_id}: {e}")
        return []
    finally:
        _file_lock.release()


def export_events(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Export events within a date range.
    
    Args:
        start_date: Start date in 'YYYY-MM-DD' format (inclusive)
        end_date: End date in 'YYYY-MM-DD' format (inclusive)
        
    Returns:
        List of matching events
    """
    acquired = _file_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS)
    if not acquired:
        logger.error("Failed to acquire telemetry lock within timeout")
        return []
    
    try:
        try:
            events = _load_events()
        except EventLogCorruptedError:
            logger.warning("Event log corrupted, returning empty export")
            return []
        
        if not start_date and not end_date:
            return events
        
        start_ts = datetime.strptime(start_date, '%Y-%m-%d').timestamp() if start_date else 0
        end_ts = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)).timestamp() if end_date else float('inf')
        
        filtered = [
            e for e in events
            if start_ts <= e.get('timestamp', 0) < end_ts
        ]
        
        return filtered
        
    except Exception as e:
        logger.error(f"Failed to export events: {e}")
        return []
    finally:
        _file_lock.release()


def get_summary() -> Dict[str, Any]:
    """
    Get a quick summary of telemetry data.
    
    Returns:
        Dictionary with key metrics
    """
    acquired = _file_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS)
    if not acquired:
        logger.error("Failed to acquire telemetry lock within timeout")
        return {}
    
    try:
        try:
            events = _load_events()
        except EventLogCorruptedError:
            return {'error': 'Event log corrupted'}
        
        if not events:
            return {
                'total_events_all_time': 0,
                'first_event': None,
                'last_event': None,
                'file_size_mb': 0
            }
        
        timestamps = [e.get('timestamp', 0) for e in events]
        
        try:
            file_size = os.path.getsize(EVENTS_LOG_PATH) / (1024 * 1024)
        except OSError:
            file_size = 0
        
        return {
            'total_events_all_time': len(events),
            'first_event': datetime.fromtimestamp(min(timestamps)).isoformat(),
            'last_event': datetime.fromtimestamp(max(timestamps)).isoformat(),
            'file_size_mb': round(file_size, 2)
        }
        
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        return {}
    finally:
        _file_lock.release()


# ==============================================================================
# DASHBOARD METRICS FUNCTIONS
# ==============================================================================

from utils.file_manager import cargar_usuarios


def get_retention_metrics() -> Dict[str, any]:
    """
    Calculate retention metrics based on user activity.
    
    Returns:
        Dict with retention_7d, churn_rate, stickiness, dau, wau, mau
    """
    usuarios = cargar_usuarios()
    now = datetime.now()
    
    # Activity windows
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)
    
    dau = 0  # Daily Active Users (24h)
    wau = 0  # Weekly Active Users (7d)
    mau = 0  # Monthly Active Users (30d)
    active_7d_and_30d = 0  # Users active in both 7d and 30d windows
    
    for uid, u in usuarios.items():
        last_seen_str = u.get('last_seen') or u.get('last_alert_timestamp')
        if not last_seen_str:
            continue
            
        try:
            last_dt = datetime.strptime(last_seen_str, '%Y-%m-%d %H:%M:%S')
            delta = now - last_dt
            seconds = delta.total_seconds()
            
            # DAU (24h)
            if seconds < 86400:
                dau += 1
                wau += 1
                mau += 1
                active_7d_and_30d += 1
            # WAU (7d but not 24h)
            elif seconds < 86400 * 7:
                wau += 1
                mau += 1
                active_7d_and_30d += 1
            # MAU (30d but not 7d)
            elif seconds < 86400 * 30:
                mau += 1
                
        except (ValueError, TypeError):
            continue
    
    # Calculate metrics
    retention_7d = 0.0
    churn_rate = 0.0
    stickiness = 0.0
    
    if mau > 0:
        # Retention: users active 7d AND 30d / users active 30d
        retention_7d = (active_7d_and_30d / mau) * 100
        # Churn: 1 - retention
        churn_rate = 100 - retention_7d
        # Stickiness: DAU / MAU ratio
        stickiness = (dau / mau) * 100
    
    return {
        'retention_7d': round(retention_7d, 1),
        'churn_rate': round(churn_rate, 1),
        'stickiness': round(stickiness, 1),
        'dau': dau,
        'wau': wau,
        'mau': mau
    }


def get_commands_per_user() -> Dict[str, any]:
    """
    Calculate average commands per user for today.
    
    Returns:
        Dict with total_commands, active_users_today, and avg_per_user
    """
    usuarios = cargar_usuarios()
    today = datetime.now().strftime('%Y-%m-%d')
    
    total_commands = 0
    active_users_today = 0
    
    for uid, u in usuarios.items():
        daily = u.get('daily_usage', {})
        if daily.get('date') == today:
            user_commands = sum(
                count for cmd, count in daily.items() 
                if cmd != 'date' and isinstance(count, int)
            )
            if user_commands > 0:
                total_commands += user_commands
                active_users_today += 1
    
    avg_per_user = (
        round(total_commands / active_users_today, 1) 
        if active_users_today > 0 else 0.0
    )
    
    return {
        'total_commands': total_commands,
        'active_users_today': active_users_today,
        'avg_per_user': avg_per_user
    }


def get_daily_events() -> Dict[str, int]:
    """
    Get event counts for today (new joins, commands, etc.)
    
    Returns:
        Dict with joins_today, commands_today, alerts_today
    """
    usuarios = cargar_usuarios()
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = datetime.now().strftime('%Y-%m-%d')
    
    joins_today = 0
    commands_today = 0
    alerts_triggered = 0
    
    for uid, u in usuarios.items():
        # Count new joins today
        reg_str = u.get('registered_at')
        if reg_str:
            try:
                reg_dt = datetime.strptime(reg_str, '%Y-%m-%d %H:%M:%S')
                if reg_dt >= today_start:
                    joins_today += 1
            except (ValueError, TypeError):
                pass
        
        # Count today's commands
        daily = u.get('daily_usage', {})
        if daily.get('date') == today:
            commands_today += sum(
                count for cmd, count in daily.items() 
                if cmd != 'date' and isinstance(count, int)
            )
    
    return {
        'joins_today': joins_today,
        'commands_today': commands_today,
        'alerts_today': alerts_triggered
    }


def get_users_registration_stats() -> Dict[str, any]:
    """
    Get statistics about user registration data quality.
    
    Returns:
        Dict with counts and percentages of users with/without registration dates
    """
    usuarios = cargar_usuarios()
    now = datetime.now()
    
    total = len(usuarios)
    with_registered_at = 0
    without_registered_at = 0
    with_last_seen = 0
    could_estimate = 0
    
    for uid, u in usuarios.items():
        if u.get('registered_at'):
            with_registered_at += 1
        else:
            without_registered_at += 1
            # If no registered_at but has last_seen, we could estimate
            if u.get('last_seen'):
                could_estimate += 1
        
        if u.get('last_seen'):
            with_last_seen += 1
    
    return {
        'total_users': total,
        'with_registered_at': with_registered_at,
        'without_registered_at': without_registered_at,
        'with_last_seen': with_last_seen,
        'could_estimate': could_estimate,
        'data_quality_pct': round((with_registered_at / total * 100), 1) if total > 0 else 0
    }
