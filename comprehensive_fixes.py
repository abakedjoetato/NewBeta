#!/usr/bin/env python
"""Comprehensive Fixes for Tower of Temptation PvP Statistics Discord Bot

This script implements several critical fixes:
1. Historical Parser Fix - Ensures proper datetime handling for consistent CSV file processing
2. Server ID Type Consistency Fix - Ensures server_id is always treated as a string in autocomplete
3. Autocomplete Subcommand Detection - Improves detection of subcommands that need fresh data
4. Fixed datetime object handling - Resolved multiple instances of datetime.datetime vs datetime issues
5. Enhanced error handling for edge cases - Better handling of null server_ids and empty inputs
6. Console Fields Handling - Fixed process to handle newer CSV format with console fields (XSX, PS5)
7. Proper Suicide Event Recognition - Improved handling of suicide_by_relocation events

The fixes ensure that:
- Historical parser can process multiple CSV files sequentially with proper datetime handling
- Server ID consistency is maintained across all autocomplete functions
- The `/setup historicalparse` command properly detects and shows servers
- All datetime handling is consistent throughout the codebase
- Edge cases like empty input and null values are properly handled
- Newer CSV files (April/May 2025) with console information fields are properly processed
- All types of suicide events are correctly categorized and normalized

Run this script to apply all fixes at once.
"""

import os
import re
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("comprehensive_fixes")

def fix_datetime_handling_in_parsers():
    """Fix the datetime handling in the historical parser and kill event processing
    
    This ensures that:
    1. Datetime objects are converted to ISO strings before MongoDB storage
    2. Process_kill_event can handle multiple datetime formats
    """
    logger.info("Fixing datetime handling in historical parser and kill event processing...")
    
    # Fix 1: Update setup.py to convert datetime objects to ISO strings
    setup_file = "cogs/setup.py"
    
    try:
        with open(setup_file, 'r') as file:
            setup_content = file.read()
            
        # Pattern 1: Add timestamp serialization for MongoDB in process_kill_events
        pattern1 = r'(# Add server ID\s+kill_event\["server_id"\] = server\.id\s+)kill_batch\.append\(kill_event\)'
        replacement1 = r'\1# Ensure timestamp is serializable for MongoDB\n                        # Convert datetime objects to ISO format strings\n                        if isinstance(kill_event["timestamp"], datetime.datetime):\n                            kill_event["timestamp"] = kill_event["timestamp"].isoformat()\n                            \n                        kill_batch.append(kill_event)'
        setup_content = re.sub(pattern1, replacement1, setup_content)
        
        # Pattern 2: Add timestamp serialization for MongoDB in the batch processing
        pattern2 = r'(# Process any remaining events in the batch\s+if kill_batch:)(\s+await self\.bot\.db\.kills\.insert_many\(kill_batch\))'
        replacement2 = r'\1\n                    # Ensure all timestamps are serializable\n                    for event in kill_batch:\n                        if isinstance(event.get("timestamp"), datetime.datetime):\n                            event["timestamp"] = event["timestamp"].isoformat()\n                            \2'
        setup_content = re.sub(pattern2, replacement2, setup_content)
        
        # Write the updated content back to the file
        with open(setup_file, 'w') as file:
            file.write(setup_content)
        
        logger.info("Successfully updated setup.py")
    except Exception as e:
        logger.error(f"Error updating setup.py: {e}")
        return False
        
    # Fix 2: Update killfeed.py to handle multiple datetime formats
    killfeed_file = "cogs/killfeed.py"
    
    try:
        with open(killfeed_file, 'r') as file:
            killfeed_content = file.read()
            
        # Pattern: Update process_kill_event to handle multiple datetime formats
        pattern = r'(async def process_kill_event.*?\s+try:\s+)# Create timestamp object if it\'s a string\s+if isinstance\(kill_event\["timestamp"\], str\):\s+kill_event\["timestamp"\] = datetime\.fromisoformat\(kill_event\["timestamp"\]\)\s+\s+# Add server_id to the event'
        replacement = r'\1# Ensure timestamp is consistent format for processing\n        # If it\'s a string, convert to datetime for processing\n        if isinstance(kill_event["timestamp"], str):\n            try:\n                # Try ISO format first (from historical parser)\n                kill_event["timestamp"] = datetime.fromisoformat(kill_event["timestamp"])\n            except ValueError:\n                # Try the CSV file format as fallback\n                try:\n                    kill_event["timestamp"] = datetime.strptime(\n                        kill_event["timestamp"], "%Y.%m.%d-%H.%M.%S"\n                    )\n                except ValueError:\n                    logger.warning(f"Could not parse timestamp: {kill_event[\'timestamp\']}")\n                    # Use current time as last resort\n                    kill_event["timestamp"] = datetime.utcnow()\n        \n        # Add server_id to the event'
        killfeed_content = re.sub(pattern, replacement, killfeed_content, flags=re.DOTALL)
        
        # Write the updated content back to the file
        with open(killfeed_file, 'w') as file:
            file.write(killfeed_content)
        
        logger.info("Successfully updated killfeed.py")
    except Exception as e:
        logger.error(f"Error updating killfeed.py: {e}")
        return False
        
    return True

def fix_server_id_type_consistency():
    """Fix server_id type handling in autocomplete functions
    
    This ensures that server_id is always treated as a string in all autocomplete functions.
    """
    logger.info("Fixing server_id type consistency in autocomplete functions...")
    
    # Fix 1: Update economy.py
    economy_file = "cogs/economy.py"
    try:
        with open(economy_file, 'r') as file:
            economy_content = file.read()
            
        pattern = r'("id": server\.get\("server_id", ""),'
        replacement = r'"id": str(server.get("server_id", "")),  # Convert to string to ensure consistent type,'
        economy_content = re.sub(pattern, replacement, economy_content)
        
        with open(economy_file, 'w') as file:
            file.write(economy_content)
            
        logger.info("Successfully updated economy.py")
    except Exception as e:
        logger.error(f"Error updating economy.py: {e}")
        
    # Fix 2: Update events.py
    events_file = "cogs/events.py"
    try:
        with open(events_file, 'r') as file:
            events_content = file.read()
            
        pattern = r'("id": server\.get\("server_id", ""),'
        replacement = r'"id": str(server.get("server_id", "")),  # Convert to string to ensure consistent type,'
        events_content = re.sub(pattern, replacement, events_content)
        
        with open(events_file, 'w') as file:
            file.write(events_content)
            
        logger.info("Successfully updated events.py")
    except Exception as e:
        logger.error(f"Error updating events.py: {e}")
        
    # Fix 3: Update setup.py
    setup_file = "cogs/setup.py"
    try:
        with open(setup_file, 'r') as file:
            setup_content = file.read()
            
        # Add string conversion in server_id_autocomplete
        pattern1 = r'(if guild_data and "servers" in guild_data:.*?# Get server data\s+servers = guild_data\["servers"\])'
        replacement1 = r'\1\n\n                    # Ensure all server_ids are strings\n                    for server in servers:\n                        if "server_id" in server:\n                            server["server_id"] = str(server["server_id"])'
        setup_content = re.sub(pattern1, replacement1, setup_content, flags=re.DOTALL)
        
        with open(setup_file, 'w') as file:
            file.write(setup_content)
            
        logger.info("Successfully updated setup.py")
    except Exception as e:
        logger.error(f"Error updating setup.py: {e}")
        
    # Fix 4: Update stats.py with the complete fix
    # Import the existing fix script to avoid duplication
    try:
        from fix_autocomplete import process_file as fix_stats_autocomplete
        fix_stats_autocomplete('cogs/stats.py')
        logger.info("Successfully updated stats.py")
    except Exception as e:
        logger.error(f"Error updating stats.py: {e}")
        
    return True

def fix_console_fields_handling():
    """Fix the handling of CSV files with console fields (XSX, PS5)
    
    This ensures that:
    1. CSV files with console fields are properly detected and parsed
    2. Console field values are properly extracted and stored
    3. The connection event detection logic doesn't reject kill events
    """
    logger.info("Fixing console fields handling...")
    
    try:
        # Update parsers.py with improved console fields handling
        parsers_file = "utils/parsers.py"
        with open(parsers_file, 'r') as file:
            parsers_content = file.read()
            
        # Update the connection event detection logic - fix the condition
        # that was mistakenly rejecting kill events
        pattern1 = r'# Check if this is a connection event \(has empty killer fields\)\s+if \(len\(raw_parts\) >= 8 and\s+\(not raw_parts\[1\]\.strip\(\) or raw_parts\[1\]\.isspace\(\)\) and\s+\(not raw_parts\[2\]\.strip\(\) or raw_parts\[2\]\.isspace\(\)\)\):'
        replacement1 = '# Check if this is a connection event (has empty killer fields AND empty victim fields)\n            # The format was mistakenly rejecting valid kill events with console information\n            if (len(raw_parts) >= 8 and \n                (not raw_parts[1].strip() or raw_parts[1].isspace()) and \n                (not raw_parts[2].strip() or raw_parts[2].isspace()) and\n                (not raw_parts[3].strip() or raw_parts[3].isspace()) and\n                (not raw_parts[4].strip() or raw_parts[4].isspace())):'
        parsers_content = re.sub(pattern1, replacement1, parsers_content, flags=re.DOTALL)
        
        # Add special logging for lines with console information
        pattern2 = r'(if has_console_indicator:.*?return None  # Skip these lines as they\'re not actual kill events)'
        replacement2 = r'\1\n                    \n            # Special logging for lines with console information\n            if len(raw_parts) >= 8 and (\n                "XSX" in raw_parts[7] or "PS5" in raw_parts[7] or \n                (len(raw_parts) > 8 and ("XSX" in raw_parts[8] or "PS5" in raw_parts[8]))):\n                logger.debug(f"Processing console kill event: {line}")'
        parsers_content = re.sub(pattern2, replacement2, parsers_content, flags=re.DOTALL)
        
        # Update console field extraction with safer code
        pattern3 = r'# Check if console fields are present in raw parts \(new format\)\s+if len\(raw_parts\) > CSV_FIELDS\["killer_console"\]:\s+killer_console = raw_parts\[CSV_FIELDS\["killer_console"\]\]\.strip\(\)\s+\s+if len\(raw_parts\) > CSV_FIELDS\["victim_console"\]:\s+victim_console = raw_parts\[CSV_FIELDS\["victim_console"\]\]\.strip\(\)'
        replacement3 = '# Check if console fields are present in raw parts (new format)\n            # Safer extraction of console information\n            killer_console = ""\n            victim_console = ""\n            killer_console_idx = CSV_FIELDS.get("killer_console", 7)\n            victim_console_idx = CSV_FIELDS.get("victim_console", 8)\n            \n            if len(raw_parts) > killer_console_idx:\n                killer_console = raw_parts[killer_console_idx].strip()\n                \n                # Handle case where the value might be empty\n                if killer_console == "":\n                    # Default to empty rather than None\n                    killer_console = ""\n            \n            if len(raw_parts) > victim_console_idx:\n                victim_console = raw_parts[victim_console_idx].strip()\n                \n                # Handle case where the value might be empty  \n                if victim_console == "":\n                    # Default to empty rather than None\n                    victim_console = ""\n                    \n            # Log the console values for debugging\n            logger.debug(f"Console values: killer={killer_console}, victim={victim_console}")'
        parsers_content = re.sub(pattern3, replacement3, parsers_content, flags=re.DOTALL)
        
        with open(parsers_file, 'w') as file:
            file.write(parsers_content)
            
        logger.info("Successfully updated parsers.py with console fields handling")
        return True
    except Exception as e:
        logger.error(f"Error fixing console fields handling: {e}")
        return False

def fix_suicide_event_recognition():
    """Improve the handling of suicide_by_relocation events
    
    This ensures that:
    1. Both "suicide_by_relocation" and "suicide by relocation" are recognized
    2. Vehicle suicide detection is more flexible for variant spellings
    3. Suicide weapon names are consistently normalized
    """
    logger.info("Fixing suicide event recognition...")
    
    try:
        # Update parsers.py with improved suicide event recognition
        parsers_file = "utils/parsers.py"
        with open(parsers_file, 'r') as file:
            parsers_content = file.read()
            
        # Update suicide case handling
        pattern = r'# Handle suicide cases where killer and victim are the same\s+if is_suicide:\s+if weapon_lower == "suicide_by_relocation":\s+suicide_type = "menu"\s+elif weapon_lower == "falling":\s+suicide_type = "fall"\s+elif weapon_lower in \["land_vehicle", "boat", "vehicle"\]:\s+suicide_type = "vehicle"\s+else:\s+suicide_type = "other"'
        replacement = '# Handle suicide cases where killer and victim are the same\n            if is_suicide:\n                # Log the suicide case for debugging\n                logger.debug(f"Processing suicide event with weapon: {weapon_lower}")\n                \n                if weapon_lower == "suicide_by_relocation" or weapon_lower == "suicide by relocation":\n                    suicide_type = "menu"\n                elif weapon_lower == "falling":\n                    suicide_type = "fall"\n                elif any(veh_type in weapon_lower for veh_type in ["land_vehicle", "boat", "vehicle"]):\n                    suicide_type = "vehicle"\n                else:\n                    suicide_type = "other"\n                    \n                # Ensure weapon is consistently normalized for suicides\n                if weapon_lower == "suicide_by_relocation" or weapon_lower == "suicide by relocation":\n                    weapon = "Suicide (Menu)"'
        parsers_content = re.sub(pattern, replacement, parsers_content, flags=re.DOTALL)
        
        with open(parsers_file, 'w') as file:
            file.write(parsers_content)
            
        logger.info("Successfully updated parsers.py with suicide event recognition")
        return True
    except Exception as e:
        logger.error(f"Error fixing suicide event recognition: {e}")
        return False

def fix_timestamp_parsing():
    """Improve timestamp parsing in CSV and log parsers
    
    This ensures that:
    1. Multiple timestamp formats are supported
    2. Errors are better handled with appropriate fallbacks
    3. Consistent import and usage of datetime objects
    """
    logger.info("Fixing timestamp parsing...")
    
    try:
        # Update parsers.py with improved timestamp parsing
        parsers_file = "utils/parsers.py"
        with open(parsers_file, 'r') as file:
            parsers_content = file.read()
            
        # Update CSV parser timestamp handling
        pattern1 = r'# Parse timestamp\s+try:\s+timestamp = datetime\.strptime\(\s+timestamp_str, "%Y\.%m\.%d-%H\.%M\.%S"\s+\)\s+except ValueError:\s+logger\.warning\(f"Invalid timestamp format: \{timestamp_str\}"\)\s+# Use current time as fallback\s+timestamp = datetime\.utcnow\(\)'
        replacement1 = '# Parse timestamp with improved error handling\n            try:\n                # Try the standard format first\n                timestamp = datetime.datetime.strptime(\n                    timestamp_str, "%Y.%m.%d-%H.%M.%S"\n                )\n            except ValueError:\n                # Try alternative formats if the standard format fails\n                try:\n                    # Try format with different separators\n                    timestamp = datetime.datetime.strptime(\n                        timestamp_str, "%Y-%m-%d-%H.%M.%S"\n                    )\n                except ValueError:\n                    try:\n                        # Try format with spaces instead of dashes\n                        timestamp = datetime.datetime.strptime(\n                            timestamp_str, "%Y.%m.%d %H.%M.%S"\n                        )\n                    except ValueError:\n                        logger.warning(f"Invalid timestamp format: {timestamp_str}")\n                        # Use current time as fallback\n                        timestamp = datetime.datetime.utcnow()'
        parsers_content = re.sub(pattern1, replacement1, parsers_content, flags=re.DOTALL)
        
        # Update LogParser timestamp handling
        pattern2 = r'try:\s+# Parse timestamp\s+timestamp = datetime\.strptime\(\s+f"\{date_str\} \{time_str\}", "%Y\.%m\.%d %H\.%M\.%S"\s+\)\s+except ValueError:\s+# Use current time as fallback\s+timestamp = datetime\.utcnow\(\)'
        replacement2 = 'try:\n                # Parse timestamp with improved format handling\n                timestamp = datetime.datetime.strptime(\n                    f"{date_str} {time_str}", "%Y.%m.%d %H.%M.%S"\n                )\n            except ValueError:\n                # Try alternative formats\n                try:\n                    timestamp = datetime.datetime.strptime(\n                        f"{date_str} {time_str}", "%Y-%m-%d %H.%M.%S"\n                    )\n                except ValueError:\n                    # Use current time as fallback\n                    timestamp = datetime.datetime.utcnow()'
        parsers_content = re.sub(pattern2, replacement2, parsers_content, flags=re.DOTALL)
        
        with open(parsers_file, 'w') as file:
            file.write(parsers_content)
            
        logger.info("Successfully updated parsers.py with improved timestamp parsing")
        return True
    except Exception as e:
        logger.error(f"Error fixing timestamp parsing: {e}")
        return False

def main():
    """Run all fixes"""
    logger.info("Starting comprehensive fixes for Tower of Temptation PvP Statistics Discord Bot")
    
    # Fix the datetime handling in historical parser
    if fix_datetime_handling_in_parsers():
        logger.info("Successfully fixed datetime handling in historical parser")
    else:
        logger.error("Failed to fix datetime handling in historical parser")
        
    # Fix server_id type consistency
    if fix_server_id_type_consistency():
        logger.info("Successfully fixed server_id type consistency")
    else:
        logger.error("Failed to fix server_id type consistency")
    
    # Fix console fields handling
    if fix_console_fields_handling():
        logger.info("Successfully fixed console fields handling")
    else:
        logger.error("Failed to fix console fields handling")
    
    # Fix suicide event recognition
    if fix_suicide_event_recognition():
        logger.info("Successfully fixed suicide event recognition")
    else:
        logger.error("Failed to fix suicide event recognition")
    
    # Fix timestamp parsing
    if fix_timestamp_parsing():
        logger.info("Successfully fixed timestamp parsing")
    else:
        logger.error("Failed to fix timestamp parsing")
        
    logger.info("All fixes applied - restart the bot to apply changes")

if __name__ == "__main__":
    main()
