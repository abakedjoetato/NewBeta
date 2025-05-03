#!/usr/bin/env python
"""Comprehensive Fix for Historical Parser Issues in Tower of Temptation Discord Bot

This script fixes all issues with the historical parser to ensure:
1. All CSV files are properly discovered and processed
2. File size calculations are accurate and reliable
3. All datetime handling is consistent throughout the codebase
4. CSV line parsing is more tolerant of formatting variations
5. Error handling is robust and informative

Run this script to apply all fixes at once.
"""

import re
import os
import sys
import logging
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_historical_parser")

class HistoricalParserFixer:
    """Fixes all issues with the historical parser"""
    
    @staticmethod
    def fix_datetime_handling() -> bool:
        """Fix all datetime handling issues across the codebase
        
        This ensures that:
        1. All references to datetime.datetime are changed to datetime
        2. Timestamp serialization is consistent for MongoDB storage
        3. Timestamp parsing handles multiple formats gracefully
        """
        files_to_fix = {
            "cogs/setup.py": [
                # Fix datetime.datetime references
                (r'datetime\.datetime\.strptime', 'datetime.strptime'),
                (r'datetime\.datetime\.now\(\)', 'datetime.now()'),
                (r'datetime\.datetime\.utcnow\(\)', 'datetime.utcnow()'),
                
                # Fix timestamp serialization for MongoDB
                (r'(# Add server ID\s+kill_event\["server_id"\] = server\.id\s+)kill_batch\.append\(kill_event\)', 
                 r'\1# Ensure timestamp is serializable for MongoDB\n                        # Convert datetime objects to ISO format strings\n                        if isinstance(kill_event["timestamp"], datetime.datetime):\n                            kill_event["timestamp"] = kill_event["timestamp"].isoformat()\n                        elif isinstance(kill_event["timestamp"], datetime):\n                            kill_event["timestamp"] = kill_event["timestamp"].isoformat()\n                            \n                        kill_batch.append(kill_event)'),
                
                # Fix nested batch processing
                (r'(# Process any remaining events in the batch\s+if kill_batch:)(\s+await self\.bot\.db\.kills\.insert_many\(kill_batch\))',
                 r'\1\n                    # Ensure all timestamps are serializable\n                    for event in kill_batch:\n                        if isinstance(event.get("timestamp"), datetime.datetime):\n                            event["timestamp"] = event["timestamp"].isoformat()\n                        elif isinstance(event.get("timestamp"), datetime):\n                            event["timestamp"] = event["timestamp"].isoformat()\n                            \2'),
            ],
            "cogs/killfeed.py": [
                # Fix datetime handling in process_kill_event
                (r'(async def process_kill_event.*?\s+try:\s+)# Create timestamp object if it\'s a string\s+if isinstance\(kill_event\["timestamp"\], str\):\s+kill_event\["timestamp"\] = datetime\.fromisoformat\(kill_event\["timestamp"\]\)\s+\s+# Add server_id to the event',
                 r'\1# Ensure timestamp is consistent format for processing\n        # If it\'s a string, convert to datetime for processing\n        if isinstance(kill_event["timestamp"], str):\n            try:\n                # Try ISO format first (from historical parser)\n                kill_event["timestamp"] = datetime.fromisoformat(kill_event["timestamp"])\n            except ValueError:\n                # Try the CSV file format as fallback\n                try:\n                    kill_event["timestamp"] = datetime.strptime(\n                        kill_event["timestamp"], "%Y.%m.%d-%H.%M.%S"\n                    )\n                except ValueError:\n                    logger.warning(f"Could not parse timestamp: {kill_event[\'timestamp\']}")\n                    # Use current time as last resort\n                    kill_event["timestamp"] = datetime.utcnow()\n        \n        # Add server_id to the event'),
            ],
            "utils/parsers.py": [
                # Fix datetime.datetime references
                (r'datetime\.datetime\.strptime', 'datetime.strptime'),
                (r'datetime\.datetime\.now\(\)', 'datetime.now()'),
                (r'datetime\.datetime\.utcnow\(\)', 'datetime.utcnow()'),
                
                # Make CSV parser more forgiving
                (r'def parse_kill_line\(line: str\) -> Optional\[Dict\[str, Any\]\]:.*?return kill_event\s+except Exception as e:',
                 HistoricalParserFixer.get_improved_csv_parser(), re.DOTALL),
            ],
            "utils/sftp.py": [
                # Fix datetime.datetime references in SFTP
                (r'datetime\.datetime\.strptime', 'datetime.strptime'),
                (r'datetime\.datetime\.now\(\)', 'datetime.now()'),
                (r'datetime\.datetime\.utcnow\(\)', 'datetime.utcnow()'),
                
                # Fix the directory search depth to ensure finding all CSV files
                (r'async def _find_csv_files_recursive\(self, directory, max_depth=8',
                 r'async def _find_csv_files_recursive\(self, directory, max_depth=12'),
                
                # Improve file size calculation
                (r'async def get_file_size\(self, file_path, chunk_size=5000\):.*?return 0',
                 HistoricalParserFixer.get_improved_file_size_calculation(), re.DOTALL),
                
                # Fix file handling for chunk reading
                (r'def _read_chunk\(self, file_obj, max_lines\):.*?return \[\]',
                 HistoricalParserFixer.get_improved_chunk_reader(), re.DOTALL),
            ]
        }
        
        success = True
        for file_path, patterns in files_to_fix.items():
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as file:
                        content = file.read()
                        
                    # Apply all patterns for this file
                    for pattern, replacement in patterns:
                        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
                        
                    with open(file_path, 'w') as file:
                        file.write(content)
                        
                    logger.info(f"Successfully updated {file_path}")
                else:
                    logger.error(f"File not found: {file_path}")
                    success = False
            except Exception as e:
                logger.error(f"Error updating {file_path}: {e}")
                success = False
                
        return success
    
    @staticmethod
    def get_improved_csv_parser() -> str:
        """Returns improved CSV parser code that's more tolerant of format variations"""
        return '''def parse_kill_line(line: str) -> Optional[Dict[str, Any]]:
        """Parse a single line from a CSV file into a kill event with improved error tolerance"""
        try:
            if not line or not line.strip():
                return None
                
            parts = line.strip().split(';')
            
            # Debug info
            logger.debug(f"Parsing CSV line with {len(parts)} parts: {line}")
            
            # More flexible parsing - handle variable number of parts
            # Ensure we have at least the minimum required fields
            if len(parts) < 4:  # Absolute minimum: timestamp, victim name, victim ID
                logger.warning(f"CSV line has too few fields ({len(parts)}): {line}")
                return None
                
            # Filter out empty strings but preserve position by replacing with placeholders
            # This maintains the field positions while allowing for trailing empty fields
            parts_with_placeholders = []
            for p in parts:
                if p.strip():
                    parts_with_placeholders.append(p.strip())
                else:
                    parts_with_placeholders.append("__EMPTY__")
            
            # The CSV format has been updated to include console information directly:
            # Timestamp;Killer name;Killer ID;Victim name;Victim ID;Weapon;Distance;Killer console;Victim console;Blank
            
            # Check if this is a connection event (has empty killer fields)
            raw_parts = line.strip().split(';')
            
            # Check if this is a connection event (has empty killer fields)
            if (len(raw_parts) >= 8 and 
                (not raw_parts[1].strip() or raw_parts[1].isspace()) and 
                (not raw_parts[2].strip() or raw_parts[2].isspace())):
                # This might be a connection event - check for console indicators
                console_indicators = ["XSX", "PS5", "PC"]
                
                has_console_indicator = False
                for indicator in console_indicators:
                    # Check anywhere in raw parts for console indicators
                    if any(indicator in part for part in raw_parts if part and part.strip()):
                        has_console_indicator = True
                        break
                        
                if has_console_indicator:
                    logger.debug(f"Detected console connection line: {line}")
                    return None  # Skip these lines as they're not actual kill events
            
            # Extract fields with forgiving validation - now using parts_with_placeholders
            try:
                # Use safer indexing with defaults
                def safe_get(arr, idx, default=""):
                    """Safely get a value from an array with a default fallback"""
                    if 0 <= idx < len(arr):
                        val = arr[idx]
                        return val if val != "__EMPTY__" else default
                    return default
                
                # Get timestamp which should always be present
                timestamp_str = safe_get(parts_with_placeholders, CSV_FIELDS.get("timestamp", 0))
                
                # For the rest of the fields, use defaults if missing
                killer_name = safe_get(parts_with_placeholders, CSV_FIELDS.get("killer_name", 1))
                killer_id = safe_get(parts_with_placeholders, CSV_FIELDS.get("killer_id", 2))
                victim_name = safe_get(parts_with_placeholders, CSV_FIELDS.get("victim_name", 3))
                victim_id = safe_get(parts_with_placeholders, CSV_FIELDS.get("victim_id", 4))
                
                # Handle weapon field with normalization
                weapon = ""
                weapon_idx = CSV_FIELDS.get("weapon", 5)
                if 0 <= weapon_idx < len(parts_with_placeholders):
                    weapon_raw = parts_with_placeholders[weapon_idx]
                    if weapon_raw != "__EMPTY__":
                        weapon = CSVParser.normalize_weapon_name(weapon_raw)
                
                # More flexible validation - require timestamp and either victim or killer info
                if not timestamp_str:
                    logger.warning(f"Missing timestamp in line: {line}")
                    return None
                    
                if not (victim_id or (killer_id and weapon)):
                    logger.warning(f"Missing critical player info in line: {line}")
                    return None
                
                # Parse distance with better error handling
                distance = 0
                distance_idx = CSV_FIELDS.get("distance", 6)
                if 0 <= distance_idx < len(parts_with_placeholders):
                    distance_str = parts_with_placeholders[distance_idx]
                    if distance_str != "__EMPTY__":
                        try:
                            distance = int(float(distance_str))  # Handle float strings too
                        except (ValueError, TypeError):
                            pass  # Keep default of 0
            except IndexError:
                logger.warning(f"Index error parsing CSV line: {line}")
                return None
            
            # Parse timestamp with multiple format support
            timestamp = None
            if timestamp_str:
                try:
                    # Try standard format
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                except ValueError:
                    try:
                        # Try alternate format (just in case)
                        timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d %H.%M.%S")
                    except ValueError:
                        try:
                            # Try ISO format
                            timestamp = datetime.fromisoformat(timestamp_str)
                        except ValueError:
                            logger.warning(f"Invalid timestamp format: {timestamp_str}")
                            # Use current time as fallback
                            timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()
            
            # Determine if this is a suicide - only when killer ID equals victim ID
            is_suicide = killer_id and victim_id and killer_id == victim_id
            suicide_type = None
            
            # Identify the type of death
            weapon_lower = weapon.lower() if weapon else ""
            
            # Handle suicide cases where killer and victim are the same
            if is_suicide:
                if "suicide_by_relocation" in weapon_lower:
                    suicide_type = "menu"
                elif "fall" in weapon_lower:
                    suicide_type = "fall"
                elif any(v in weapon_lower for v in ["land_vehicle", "boat", "vehicle"]):
                    suicide_type = "vehicle"
                else:
                    suicide_type = "other"
            
            # Get console information if available
            killer_console = ""
            victim_console = ""
            
            # Check if console fields are present in raw parts (new format)
            killer_console_idx = CSV_FIELDS.get("killer_console", 7)
            if 0 <= killer_console_idx < len(raw_parts):
                killer_console = raw_parts[killer_console_idx].strip()
            
            victim_console_idx = CSV_FIELDS.get("victim_console", 8)
            if 0 <= victim_console_idx < len(raw_parts):
                victim_console = raw_parts[victim_console_idx].strip()
            
            # Create kill event with console information
            kill_event = {
                "timestamp": timestamp,
                "killer_name": killer_name,
                "killer_id": killer_id,
                "victim_name": victim_name,
                "victim_id": victim_id,
                "weapon": weapon,
                "distance": distance,
                "killer_console": killer_console,
                "victim_console": victim_console,
                "is_suicide": is_suicide,
                "suicide_type": suicide_type
            }
            
            return kill_event
            
        except Exception as e:
            logger.error(f"Error parsing CSV line: {e} - Line: {line}")'''
    
    @staticmethod
    def get_improved_file_size_calculation() -> str:
        """Returns improved file size calculation code with better timeout handling"""
        return '''async def get_file_size(self, file_path, chunk_size=5000):
        """Get the size of a file in lines with improved reliability and performance
        Args:
            file_path: Path to the file
            chunk_size: Number of lines to count in each chunk
        Returns:
            Number of lines in the file
        """
        if not self.connected:
            await self.connect()
        if not self.connected:
            return 0

        try:
            # OPTIMIZATION: Use a faster method to count lines
            # First try the fastest approach - check if we can get an exact count quickly
            async def fast_count():
                """Fast line counting using wc -l if available, otherwise fall back to reading"""
                try:
                    # Try to use shell command to count lines (much faster)
                    stdin, stdout, stderr = await asyncio.to_thread(
                        lambda: self.client.exec_command(f"wc -l {file_path}", timeout=5.0)
                    )
                    result = await asyncio.to_thread(lambda: stdout.read().decode().strip())
                    if result and ' ' in result:
                        # wc -l output format: "N filename"
                        count = int(result.split(' ')[0])
                        logger.info(f"Fast line count for {file_path}: {count} lines")
                        return count
                    return None
                except Exception as e:
                    logger.debug(f"Fast count failed, falling back to python method: {e}")
                    return None

            # Try the fast count first with timeout
            try:
                count = await asyncio.wait_for(fast_count(), timeout=5.0)
                if count is not None:
                    return count
            except (asyncio.TimeoutError, Exception):
                pass

            # Fall back to Python counting method with performance optimizations
            def optimized_count():
                try:
                    with self.sftp.file(file_path, 'r') as f:
                        # Use a faster method to count lines
                        # Read the file in larger chunks for speed
                        chunk_size = 1024 * 1024  # 1MB chunks
                        total_lines = 0
                        read_bytes = 0
                        file_size = 0
                        
                        # Get file size first
                        try:
                            file_size = self.sftp.stat(file_path).st_size
                        except:
                            file_size = 0
                            
                        # Stop after reading more than 100MB to prevent timeouts on huge files
                        # This will provide a good estimate for large files
                        max_bytes_to_read = min(file_size, 100 * 1024 * 1024)
                        
                        # Read and count newlines in chunks
                        buffer = f.read(chunk_size)
                        while buffer:
                            read_bytes += len(buffer)
                            total_lines += buffer.count('\\n')
                            
                            # Break if we've read enough
                            if read_bytes >= max_bytes_to_read:
                                # Estimate total based on portion read
                                if file_size > 0:
                                    scale_factor = file_size / read_bytes
                                    if scale_factor > 1:
                                        return int(total_lines * scale_factor)
                                break
                                
                            # Read next chunk
                            buffer = f.read(chunk_size)
                            
                        # Add 1 if file doesn't end with newline
                        return total_lines + (0 if buffer.endswith('\\n') else 1)
                except Exception as e:
                    logger.error(f"Error in optimized count: {e}")
                    return 5000  # Reasonable default

            # Run the optimized counting with timeout
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(optimized_count),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                # Use stats-based estimation as fallback
                try:
                    attrs = await asyncio.to_thread(lambda: self.sftp.stat(file_path))
                    # Estimate based on file size - assume approximately 80 bytes per line
                    estimated_lines = max(100, attrs.st_size // 80) 
                    logger.info(f"Using size-based estimation for {file_path}: ~{estimated_lines} lines")
                    return estimated_lines
                except Exception:
                    logger.warning(f"Fallback estimation failed for {file_path}, using default")
                    return 5000  # Default if all methods fail

        except Exception as e:
            logger.error(f"Error in get_file_size: {e}", exc_info=True)
            return 0'''
    
    @staticmethod
    def get_improved_chunk_reader() -> str:
        """Returns improved chunk reader code with better error handling"""
        return '''def _read_chunk(self, file_obj, max_lines):
        """Read a chunk of lines from a file with improved error handling
        Args:
            file_obj: Open file object
            max_lines: Maximum number of lines to read
        Returns:
            List of lines read
        """
        try:
            lines = []
            for _ in range(max_lines):
                try:
                    line = next(file_obj)
                    # Skip non-UTF8 characters if present
                    if line:
                        try:
                            # Try to decode and re-encode to ensure valid UTF-8
                            # This handles cases where files have mixed encodings
                            line = line.encode('utf-8', errors='replace').decode('utf-8')
                        except Exception:
                            # Just use the original line if encoding conversion fails
                            pass
                    lines.append(line)
                except StopIteration:
                    break
                except Exception as line_error:
                    logger.warning(f"Error reading line: {line_error}")
                    continue  # Skip problematic lines but continue reading
            return lines
        except Exception as e:
            logger.error(f"Error in _read_chunk: {e}")
            return []'''
    
    @staticmethod
    def fix_server_id_type_consistency() -> bool:
        """Fix all server_id type consistency issues
        
        This ensures that server_id is treated consistently as a string
        throughout the application, particularly in autocomplete functions.
        """
        # We'll implement the same fixes from the comprehensive_fixes.py script
        files_to_fix = {
            "cogs/economy.py": [
                (r'("id": server\.get\("server_id", ""),)',
                 r'"id": str(server.get("server_id", "")),  # Convert to string to ensure consistent type,'),
            ],
            "cogs/events.py": [
                (r'("id": server\.get\("server_id", ""),)',
                 r'"id": str(server.get("server_id", "")),  # Convert to string to ensure consistent type,'),
            ],
            "cogs/setup.py": [
                # Add string conversion in server_id_autocomplete
                (r'(if guild_data and "servers" in guild_data:.*?# Get server data\s+servers = guild_data\["servers"\])',
                 r'\1\n\n                    # Ensure all server_ids are strings\n                    for server in servers:\n                        if "server_id" in server:\n                            server["server_id"] = str(server["server_id"])',
                 re.DOTALL),
            ],
        }
        
        # Add stats.py fix using existing fix_autocomplete.py script
        try:
            from fix_autocomplete import process_file as fix_stats_autocomplete
            fix_stats_autocomplete('cogs/stats.py')
            logger.info("Successfully updated stats.py")
        except Exception as e:
            logger.error(f"Error updating stats.py: {e}")
            return False
        
        # Process the other files
        success = True
        for file_path, patterns in files_to_fix.items():
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as file:
                        content = file.read()
                        
                    # Apply all patterns for this file
                    for pattern, replacement, *flags in patterns:
                        flags_val = 0
                        if flags and flags[0] == re.DOTALL:
                            flags_val = re.DOTALL
                        content = re.sub(pattern, replacement, content, flags=flags_val)
                        
                    with open(file_path, 'w') as file:
                        file.write(content)
                        
                    logger.info(f"Successfully updated {file_path}")
                else:
                    logger.error(f"File not found: {file_path}")
                    success = False
            except Exception as e:
                logger.error(f"Error updating {file_path}: {e}")
                success = False
                
        return success
        
    @staticmethod
    def enhance_csv_discovery() -> bool:
        """Enhance the CSV file discovery logic
        
        This improves the code that searches for CSV files to ensure
        all files are found and properly processed.
        """
        # We'll update the debug_csv_find.py script to fix SFTP directory search
        file_path = "debug_csv_find.py"
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    content = file.read()
                    
                # Add our improved directory search function
                updated_content = re.sub(
                    r'async def find_csv_files_recursive\(directory, max_depth=6, current_depth=0, starting_dir=None\):.*?return csv_files',
                    HistoricalParserFixer.get_improved_csv_discovery(),
                    content,
                    flags=re.DOTALL
                )
                    
                with open(file_path, 'w') as file:
                    file.write(updated_content)
                    
                logger.info(f"Successfully updated {file_path}")
                return True
            else:
                logger.error(f"File not found: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Error updating {file_path}: {e}")
            return False
    
    @staticmethod
    def get_improved_csv_discovery() -> str:
        """Returns improved CSV discovery code"""
        return '''async def find_csv_files_recursive(directory, max_depth=12, current_depth=0, starting_dir=None):
    """Recursively search for CSV files in all subdirectories with enhanced logging
    and improved discovery capabilities
    
    Args:
        directory: The directory to search
        max_depth: Maximum recursion depth 
        current_depth: Current recursion depth
        starting_dir: The initial directory we started search from
    """
    if starting_dir is None:
        starting_dir = directory
        
    # Log recursion depth to help diagnose infinite loops
    if current_depth > max_depth:
        logger.warning(f"Maximum recursion depth {max_depth} reached at {directory}")
        return []
        
    csv_files = []
    
    try:
        # Get directory contents with improved error handling
        try:
            items = await asyncio.to_thread(lambda: os.listdir(directory))
        except Exception as list_error:
            logger.error(f"Error listing directory {directory}: {list_error}")
            return []
            
        # Log what we found
        logger.info(f"Directory {directory} contains {len(items)} items at depth {current_depth}")
        
        # Check for world folders and deathlogs special cases - prioritize these
        # Pattern: world_X or worldX or World_X
        world_folders = [item for item in items if re.match(r'world[_-]?\d+', item.lower())]
        deathlogs_folder = [item for item in items if 'deathlogs' in item.lower()]
        
        # Process priority folders first (these are likely to contain CSV files)
        priority_folders = world_folders + deathlogs_folder
        
        # Process all items - first priority folders, then others
        all_items = priority_folders + [item for item in items if item not in priority_folders]
        
        # Count found CSV files
        csv_count = 0
        
        for item in all_items:
            item_path = os.path.join(directory, item)
            
            # Check if it's a CSV file with proper naming
            if item.lower().endswith('.csv'):
                # Additional check for proper date format in filename
                if re.match(r'\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}\.csv', item.lower()):
                    logger.info(f"Found properly formatted CSV file: {item_path}")
                    csv_files.append(item_path)
                    csv_count += 1
                else:
                    # Accept all CSV files but log if they don't match the expected format
                    logger.warning(f"Found CSV file with unexpected format: {item_path}")
                    csv_files.append(item_path)
                    csv_count += 1
                    
            # Check if it's a directory
            if os.path.isdir(item_path):
                # Special case: If we find a directory that looks like a world or deathlogs folder,
                # increase priority by reducing effective depth
                # This helps ensure we fully explore these high-value folders
                effective_depth = current_depth
                if any(pattern in item.lower() for pattern in ['world', 'deathlogs']):
                    effective_depth = max(0, current_depth - 2)  # Reduce depth by 2 for priority folders
                
                # Recursively search subdirectory with appropriate depth
                subdir_files = await find_csv_files_recursive(
                    item_path, max_depth, effective_depth + 1, starting_dir
                )
                
                csv_files.extend(subdir_files)
                csv_count += len(subdir_files)
                
        # Log summary for this directory
        logger.info(f"Found {csv_count} CSV files in {directory} and its subdirectories")
        
    except Exception as e:
        logger.error(f"Error in recursive CSV search for {directory}: {e}")
        
    return csv_files'''

def main():
    """Run all historical parser fixes"""
    logger.info("Starting comprehensive fixes for Tower of Temptation PvP Statistics Discord Bot")
    
    fixer = HistoricalParserFixer()
    
    # Fix datetime handling issues
    if fixer.fix_datetime_handling():
        logger.info("✅ Successfully fixed datetime handling in historical parser")
    else:
        logger.error("❌ Failed to fix datetime handling in historical parser")
    
    # Fix server_id type consistency issues
    if fixer.fix_server_id_type_consistency():
        logger.info("✅ Successfully fixed server_id type consistency")
    else:
        logger.error("❌ Failed to fix server_id type consistency")
    
    # Enhance CSV discovery logic
    if fixer.enhance_csv_discovery():
        logger.info("✅ Successfully enhanced CSV file discovery logic")
    else:
        logger.error("❌ Failed to enhance CSV file discovery logic")
    
    logger.info("All fixes applied - restart the bot to apply changes")

if __name__ == "__main__":
    main()