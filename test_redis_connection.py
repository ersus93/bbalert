#!/usr/bin/env python3
"""
Test script to verify Redis connectivity and the bot's Redis functions.
"""

import sys
import os

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.redis_fallback import (
    get_redis_client,
    get_user,
    save_user,
    get_all_user_ids,
    delete_user,
    get_price_alerts,
    save_price_alerts,
    get_hbd_history,
    save_hbd_history,
    get_custom_alert_history,
    save_custom_alert_history,
    get_eltoque_history,
    save_eltoque_history,
    get_last_prices,
    save_last_prices,
    get_ads,
    save_ads,
    get_hbd_thresholds,
    save_hbd_thresholds,
    get_weather_subs,
    save_weather_subs,
    get_weather_last_alerts,
    save_weather_last_alerts,
    get_year_quotes,
    save_year_quotes,
    get_year_subs,
    save_year_subs,
    get_events_log,
    save_events_log,
)

def test_redis_connection():
    """Test basic Redis connection."""
    print("🔌 Testing Redis connection...")
    client = get_redis_client()
    if client is None:
        print("❌ Redis client is None. Using fallback mode.")
        return False
    
    try:
        ping_result = client.ping()
        if ping_result:
            print("✅ Redis is connected and responding")
            return True
        else:
            print("❌ Redis did not respond to ping")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Redis: {e}")
        return False

def test_basic_operations():
    """Test basic Redis operations."""
    print("\n🧪 Testing basic Redis operations...")
    client = get_redis_client()
    if client is None:
        print("⚠️ Redis client is None, skipping basic operations test")
        return
    
    test_key = "test_key"
    test_value = "test_value"
    
    try:
        # Set a test key
        client.set(test_key, test_value)
        print(f"✅ Set key '{test_key}'")
        
        # Get the test key
        value = client.get(test_key)
        if value == test_value:
            print(f"✅ Got value '{value}' for key '{test_key}'")
        else:
            print(f"❌ Expected '{test_value}', got '{value}'")
        
        # Delete the test key
        client.delete(test_key)
        print(f"✅ Deleted key '{test_key}'")
        
    except Exception as e:
        print(f"❌ Error during basic operations: {e}")

def test_user_operations():
    """Test user-related Redis functions."""
    print("\n👤 Testing user operations...")
    
    # Create a test user
    test_user_id = 123456789
    test_user_data = {
        "language": "es",
        "registered_at": "2026-04-12 00:00:00",
        "monedas": ["BTC", "ETH"],
        "intervalo_alerta_h": 2.5,
        "last_seen": "2026-04-12 00:00:00",
        "subscriptions": {
            "alerts_extra": {"qty": 0, "expires": None},
            "coins_extra": {"qty": 0, "expires": None},
            "watchlist_bundle": {"active": False, "expires": None},
            "ta_vip": {"active": False, "expires": None},
            "sp_signals": {"active": False, "expires": None},
        },
        "hbd_alerts_enabled": False,
        "meta": {}
    }
    
    try:
        # Save user
        result = save_user(test_user_id, test_user_data)
        if result:
            print(f"✅ User {test_user_id} saved to Redis")
        else:
            print(f"❌ Failed to save user {test_user_id} to Redis")
            return
        
        # Get user
        user = get_user(test_user_id)
        if user:
            print(f"✅ User {test_user_id} retrieved from Redis")
            print(f"   User data: language={user.get('language')}, monedas={user.get('monedas')}")
        else:
            print(f"❌ Failed to retrieve user {test_user_id} from Redis")
        
        # Clean up test user
        client = get_redis_client()
        if client:
            client.delete(f"usuario:{test_user_id}")
            client.srem('usuarios:ids', str(test_user_id))
            print(f"🧹 Cleaned up test user {test_user_id}")
            
    except Exception as e:
        print(f"❌ Error during user operations: {e}")

def test_migration_script():
    """Test the migration script."""
    print("\n🔄 Testing migration script...")
    try:
        # Check if migration script exists
        import scripts.migrate_to_redis as migration_script
        
        # Run migration
        migration_script.main()
        print("✅ Migration script executed successfully")
    except Exception as e:
        print(f"❌ Error running migration script: {e}")

def test_all_functions():
    """Test all Redis functions."""
    print("\n🧰 Testing all Redis functions...")
    
    # Test each function
    functions_to_test = [
        ("get_hbd_history", get_hbd_history, save_hbd_history),
        ("get_custom_alert_history", get_custom_alert_history, save_custom_alert_history),
        ("get_eltoque_history", get_eltoque_history, save_eltoque_history),
        ("get_last_prices", get_last_prices, save_last_prices),
        ("get_ads", get_ads, save_ads),
        ("get_hbd_thresholds", get_hbd_thresholds, save_hbd_thresholds),
        ("get_weather_subs", get_weather_subs, save_weather_subs),
        ("get_weather_last_alerts", get_weather_last_alerts, save_weather_last_alerts),
        ("get_year_quotes", get_year_quotes, save_year_quotes),
        ("get_year_subs", get_year_subs, save_year_subs),
        ("get_events_log", get_events_log, save_events_log),
    ]
    
    for func_name, get_func, set_func in functions_to_test:
        try:
            # Test get (should return empty list/dict if not exists)
            data = get_func()
            if data is not None:
                print(f"✅ {func_name}() returned data (type: {type(data).__name__}, length: {len(data) if hasattr(data, '__len__') else 'N/A'})")
            else:
                print(f"⚠️ {func_name}() returned None")
        except Exception as e:
            print(f"❌ Error in {func_name}(): {e}")

def main():
    print("=" * 60)
    print("🤖 BBAlert Redis Test Script")
    print("=" * 60)
    
    # Test Redis connection
    if not test_redis_connection():
        print("\n❌ Redis connection failed. Please ensure Redis is running on localhost:6379.")
        print("   You can start Redis with: redis-server")
        return
    
    # Test basic operations
    test_basic_operations()
    
    # Test user operations
    test_user_operations()
    
    # Test migration script
    test_migration_script()
    
    # Test all Redis functions
    test_all_functions()
    
    print("\n" + "=" * 60)
    print("✅ All Redis tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()