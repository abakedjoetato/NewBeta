"""
CSV parser for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Parser for death event CSV files from game servers
2. Functions for extracting relevant PvP information
3. Data normalization and validation
"""
import csv
import logging
import re
from datetime import datetime
from io import StringIO
from typing import Dict, List, Optional, Set, Tuple, Any, Union

from models.rivalry import Rivalry

logger = logging.getLogger(__name__)

# Constants
SUICIDE_KEYWORDS = ["suicide", "fall_damage", "drowning", "relocation"]
VALID_WEAPON_CATEGORIES = {
    "melee", "pistol", "rifle", "shotgun", "sniper", 
    "smg", "explosive", "environment", "unknown"
}

class CSVParser:
    """Parser for CSV files containing death events"""
    
    def __init__(self):
        """Initialize CSV parser"""
        self.processed_entries = set()  # Track processed entries to avoid duplicates
    
    def parse_death_events(self, csv_content: str) -> List[Dict[str, Any]]:
        """Parse death events from CSV content
        
        Args:
            csv_content: Raw CSV content as string
            
        Returns:
            List[Dict]: List of parsed death events
        """
        # Check if the content is empty
        if not csv_content.strip():
            logger.warning("Empty CSV content provided")
            return []
            
        death_events = []
        
        try:
            # Split lines and process each line
            lines = csv_content.splitlines()
            for line in lines:
                if not line.strip():
                    continue
                    
                # Process the line
                event = self.parse_kill_line(line)
                if event:
                    # Skip suicides
                    if event.get('is_suicide', False):
                        continue
                        
                    # Generate unique identifier
                    event_id = self._generate_event_id(event)
                    
                    # Skip already processed entries
                    if event_id in self.processed_entries:
                        continue
                        
                    death_events.append(event)
                    self.processed_entries.add(event_id)
                    
                    # Limit processed entry cache
                    if len(self.processed_entries) > 10000:
                        self.processed_entries = set(list(self.processed_entries)[-5000:])
        
        except Exception as e:
            logger.error(f"Error parsing CSV: {str(e)}")
        
        return death_events
    
    def _generate_event_id(self, event: Dict[str, Any]) -> str:
        """Generate a unique identifier for a death event
        
        Args:
            event: Processed event data
            
        Returns:
            str: Unique event identifier
        """
        # Use timestamp, killer_id, and victim_id as a unique identifier
        timestamp = event.get("timestamp", "")
        if isinstance(timestamp, datetime):
            timestamp = timestamp.strftime("%Y.%m.%d-%H.%M.%S")
            
        killer_id = event.get("killer_id", "")
        victim_id = event.get("victim_id", "")
        
        return f"{timestamp}_{killer_id}_{victim_id}"
    
    def parse_kill_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single kill line from the CSV file
        
        Args:
            line: Raw CSV line
            
        Returns:
            Dict or None: Parsed kill data or None if invalid
        """
        try:
            # Split by semicolons
            parts = line.strip().split(';')
            
            # Validate line format
            if len(parts) < 7:
                logger.debug(f"Invalid line format (too few fields): {line}")
                return None
                
            # Extract fields based on position
            timestamp_str = parts[0]
            killer_name = parts[1]
            killer_id = parts[2]
            victim_name = parts[3]
            victim_id = parts[4]
            weapon = parts[5]
            distance = parts[6]
            
            # Check for empty essential fields
            if not killer_id or not victim_id:
                logger.debug(f"Missing essential fields (killer_id or victim_id): {line}")
                return None
                
            # Optional console fields
            killer_console = parts[7] if len(parts) > 7 else None
            victim_console = parts[8] if len(parts) > 8 else None
            
            # Parse timestamp
            timestamp = self._parse_timestamp(timestamp_str)
            if not timestamp:
                logger.debug(f"Invalid timestamp: {timestamp_str}")
                return None
                
            # Check for suicide (same killer and victim)
            is_suicide = killer_id == victim_id
            
            # Also check weapon for suicide keywords
            suicide_type = None
            if any(keyword in weapon.lower() for keyword in SUICIDE_KEYWORDS):
                is_suicide = True
                suicide_type = weapon
                
            # Create event data
            event = {
                "timestamp": timestamp,
                "killer_id": killer_id,
                "killer_name": killer_name,
                "victim_id": victim_id,
                "victim_name": victim_name,
                "weapon": self._normalize_weapon(weapon),
                "distance": int(distance) if distance and distance.isdigit() else 0,
                "is_suicide": is_suicide,
                "killer_console": killer_console,
                "victim_console": victim_console
            }
            
            # Add suicide type if this is a suicide
            if is_suicide and suicide_type:
                event["suicide_type"] = suicide_type
                
            return event
                
        except Exception as e:
            logger.error(f"Error parsing kill line: {str(e)}, Line: {line}")
            return None
            
    def parse_kill_lines(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse multiple kill lines
        
        Args:
            lines: List of raw CSV lines
            
        Returns:
            List[Dict]: List of parsed kill events
        """
        events = []
        for line in lines:
            event = self.parse_kill_line(line)
            if event:
                events.append(event)
                
        return events
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp from string
        
        Args:
            timestamp_str: Timestamp string
            
        Returns:
            datetime or None: Parsed timestamp or None if invalid
        """
        try:
            # First try the Deadside format: YYYY.MM.DD-HH.MM.SS
            try:
                return datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
            except ValueError:
                pass
                
            # Try alternative formats
            formats = [
                "%Y-%m-%d %H:%M:%S",  # Standard format
                "%Y-%m-%dT%H:%M:%S",  # ISO-like format
                "%Y/%m/%d %H:%M:%S",  # Alternative format
                "%Y%m%d%H%M%S"        # Compact format
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
            
            # If none of the formats match, try parsing Unix timestamp
            if timestamp_str.isdigit():
                return datetime.fromtimestamp(int(timestamp_str))
            
            logger.warning(f"Unknown timestamp format: {timestamp_str}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing timestamp '{timestamp_str}': {str(e)}")
            return None
    
    def _normalize_weapon(self, weapon_str: str) -> str:
        """Normalize weapon name
        
        Args:
            weapon_str: Raw weapon string
            
        Returns:
            str: Normalized weapon name
        """
        if not weapon_str:
            return "Unknown"
        
        # Special case for suicide
        if any(keyword in weapon_str.lower() for keyword in SUICIDE_KEYWORDS):
            return "Suicide"
        
        # Remove prefixes and suffixes
        weapon = weapon_str.strip()
        
        # Already normalized
        return weapon
    
    def _normalize_location(self, location_str: str) -> str:
        """Normalize location name
        
        Args:
            location_str: Raw location string
            
        Returns:
            str: Normalized location name
        """
        if not location_str:
            return "Unknown"
        
        # Remove prefixes and suffixes
        location = location_str.strip().lower()
        location = re.sub(r'(^loc_|^location_|_location$)', '', location)
        
        # Capitalize words and replace underscores
        location = ' '.join(word.capitalize() for word in location.split('_'))
        
        return location
    
    async def process_and_update_rivalries(
        self,
        server_id: str,
        csv_content: str
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Process CSV content and update rivalries
        
        Args:
            server_id: Server ID
            csv_content: Raw CSV content
            
        Returns:
            Tuple[int, List[Dict]]: Number of processed events and list of errors
        """
        death_events = self.parse_death_events(csv_content)
        processed_count = 0
        errors = []
        
        # Process each death event
        for event in death_events:
            try:
                # Skip suicides
                if event.get('is_suicide', False):
                    continue
                    
                # Extract data
                killer_id = event["killer_id"]
                killer_name = event["killer_name"]
                victim_id = event["victim_id"]
                victim_name = event["victim_name"]
                weapon = event.get("weapon")
                distance = event.get("distance", 0)
                
                # Use distance as "location" since deadside doesn't provide location
                location = f"Distance: {distance}m"
                
                # Skip empty names
                if not killer_name or not victim_name:
                    continue
                
                # Record kill in rivalry system
                await Rivalry.record_kill(
                    server_id=server_id,
                    killer_id=killer_id,
                    killer_name=killer_name,
                    victim_id=victim_id,
                    victim_name=victim_name,
                    weapon=weapon,
                    location=location
                )
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error updating rivalry: {str(e)}")
                errors.append({
                    "event": event,
                    "error": str(e)
                })
        
        return processed_count, errors
    
    def clear_cache(self):
        """Clear the processed entries cache"""
        self.processed_entries.clear()
        logger.info("Cleared CSV parser cache")