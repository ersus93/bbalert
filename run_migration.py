#!/usr/bin/env python3
"""
Script to run the migration to Redis.
This script will migrate all data from JSON files to Redis.
"""

import os
import sys

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.migrate_to_redis import main

if __name__ == "__main__":
    main()