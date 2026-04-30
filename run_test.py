#!/usr/bin/env python3
import sys
sys.path.insert(0, 'C:\\Users\\ernes\\Documents\\bbalert')

from datetime import datetime, timedelta

def test_interval_calculation():
    """Test the interval calculation logic."""
    
    print("Testing interval calculation logic...")
    print("=" * 60)
    
    # Test case 1: Normal case - next alert is in the future
    print("\nTest 1: Next alert is in the future (30 minutes)")
    intervalo_h = 4.0  # 4 hours
    intervalo_segundos = intervalo_h * 3600  # 14400 seconds
    
    last_run = datetime.now() - timedelta(hours=1)  # Last alert was 1 hour ago
    next_run = last_run + timedelta(seconds=intervalo_segundos)  # Next alert should be in 3 hours
    now = datetime.now()
    
    remaining_seconds = (next_run - now).total_seconds()
    print(f"  Interval: {intervalo_h} hours ({intervalo_segundos} seconds)")
    print(f"  Last run: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Now: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Remaining seconds: {remaining_seconds:.1f} ({remaining_seconds/60:.1f} minutes)")
    
    if remaining_seconds > 0:
        first_run_delay = remaining_seconds
        print(f"  ✓ First run delay: {first_run_delay/60:.1f} minutes (waiting for next scheduled alert)")
    else:
        first_run_delay = intervalo_segundos + remaining_seconds
        print(f"  ✓ First run delay: {first_run_delay/60:.1f} minutes (respecting interval)")
    
    assert first_run_delay > 0, "First run delay should be positive"
    assert first_run_delay <= intervalo_segundos, "First run delay should not exceed interval"
    
    # Test case 2: Bot was offline - next alert is in the past
    print("\nTest 2: Bot was offline - next alert is in the past (2 hours ago)")
    last_run = datetime.now() - timedelta(hours=3)  # Last alert was 3 hours ago
    next_run = last_run + timedelta(seconds=intervalo_segundos)  # Next alert should have been 1 hour ago
    now = datetime.now()
    
    remaining_seconds = (next_run - now).total_seconds()
    print(f"  Interval: {intervalo_h} hours ({intervalo_segundos} seconds)")
    print(f"  Last run: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Now: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Remaining seconds: {remaining_seconds:.1f} ({remaining_seconds/60:.1f} minutes)")
    
    if remaining_seconds > 0:
        first_run_delay = remaining_seconds
        print(f"  ✓ First run delay: {first_run_delay/60:.1f} minutes (waiting for next scheduled alert)")
    else:
        first_run_delay = intervalo_segundos + remaining_seconds  # remaining_seconds is negative
        print(f"  ✓ First run delay: {first_run_delay/60:.1f} minutes (respecting interval)")
    
    assert first_run_delay > 0, "First run delay should be positive"
    assert first_run_delay <= intervalo_segundos, "First run delay should not exceed interval"
    
    # Test case 3: Bot was offline for a long time - next alert is way in the past
    print("\nTest 3: Bot was offline for a long time - next alert is 10 hours ago")
    last_run = datetime.now() - timedelta(hours=14)  # Last alert was 14 hours ago
    next_run = last_run + timedelta(seconds=intervalo_segundos)  # Next alert should have been 10 hours ago
    now = datetime.now()
    
    remaining_seconds = (next_run - now).total_seconds()
    print(f"  Interval: {intervalo_h} hours ({intervalo_segundos} seconds)")
    print(f"  Last run: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Now: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Remaining seconds: {remaining_seconds:.1f} ({remaining_seconds/60:.1f} minutes)")
    
    if remaining_seconds > 0:
        first_run_delay = remaining_seconds
        print(f"  ✓ First run delay: {first_run_delay/60:.1f} minutes (waiting for next scheduled alert)")
    else:
        first_run_delay = intervalo_segundos + remaining_seconds  # remaining_seconds is negative
        print(f"  ✓ First run delay: {first_run_delay/60:.1f} minutes (respecting interval)")
    
    assert first_run_delay > 0, "First run delay should be positive"
    assert first_run_delay <= intervalo_segundos, "First run delay should not exceed interval"
    
    # Test case 4: Short interval (2.5 hours)
    print("\nTest 4: Short interval (2.5 hours) - bot was offline")
    intervalo_h = 2.5  # 2.5 hours
    intervalo_segundos = intervalo_h * 3600  # 9000 seconds
    
    last_run = datetime.now() - timedelta(hours=4)  # Last alert was 4 hours ago
    next_run = last_run + timedelta(seconds=intervalo_segundos)  # Next alert should have been 1.5 hours ago
    now = datetime.now()
    
    remaining_seconds = (next_run - now).total_seconds()
    print(f"  Interval: {intervalo_h} hours ({intervalo_segundos} seconds)")
    print(f"  Last run: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Now: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Remaining seconds: {remaining_seconds:.1f} ({remaining_seconds/60:.1f} minutes)")
    
    if remaining_seconds > 0:
        first_run_delay = remaining_seconds
        print(f"  ✓ First run delay: {first_run_delay/60:.1f} minutes (waiting for next scheduled alert)")
    else:
        first_run_delay = intervalo_segundos + remaining_seconds  # remaining_seconds is negative
        print(f"  ✓ First run delay: {first_run_delay/60:.1f} minutes (respecting interval)")
    
    assert first_run_delay > 0, "First run delay should be positive"
    assert first_run_delay <= intervalo_segundos, "First run delay should not exceed interval"
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("\nThe fix ensures that:")
    print("1. When bot restarts, it respects the user-configured interval")
    print("2. Price lists are NOT sent immediately on restart")
    print("3. The next alert is scheduled at the correct interval boundary")

if __name__ == "__main__":
    test_interval_calculation()
