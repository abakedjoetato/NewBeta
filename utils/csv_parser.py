"""
CSV Parser for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. CSV file parsing
2. Event extraction
3. Log processing
4. Statistics aggregation
"""
import csv
import io
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple, BinaryIO, TextIO, Iterator

logger = logging.getLogger(__name__)

class CSVParser:
    """CSV file parser for game log files"""
    
    # Define standard log formats
    LOG_FORMATS = {
        "deadside": {
            "separator": ";",
            "columns": ["timestamp", "killer_name", "killer_id", "victim_name", "victim_id", "weapon", "distance", "platform"],
            "datetime_format": "%Y-%m-%d %H:%M:%S",
            "datetime_column": "timestamp"
        },
        "custom": {
            "separator": ",",
            "columns": ["timestamp", "event_type", "player1_name", "player1_id", "player2_name", "player2_id", "details", "location"],
            "datetime_format": "%Y-%m-%d %H:%M:%S",
            "datetime_column": "timestamp"
        }
    }
    
    def __init__(self, format_name: str = "deadside"):
        """Initialize CSV parser with specified format
        
        Args:
            format_name: Log format name (default: "deadside")
        """
        self.format_name = format_name
        
        # Get format configuration
        if format_name in self.LOG_FORMATS:
            self.format_config = self.LOG_FORMATS[format_name]
        else:
            # Default to deadside format
            logger.warning(f"Unknown log format: {format_name}, using deadside format")
            self.format_name = "deadside"
            self.format_config = self.LOG_FORMATS["deadside"]
            
        # Extract configuration
        self.separator = self.format_config["separator"]
        self.columns = self.format_config["columns"]
        self.datetime_format = self.format_config["datetime_format"]
        self.datetime_column = self.format_config["datetime_column"]
    
    def parse_csv_data(self, data: Union[str, bytes]) -> List[Dict[str, Any]]:
        """Parse CSV data and return list of events
        
        Args:
            data: CSV data string or bytes
            
        Returns:
            List[Dict]: List of parsed event dictionaries
        """
        # Convert bytes to string if needed
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
            
        # Create CSV reader
        csv_file = io.StringIO(data)
        
        # Parse CSV data
        try:
            return self._parse_csv_file(csv_file)
        finally:
            csv_file.close()
    
    def parse_csv_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse CSV file and return list of events
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            List[Dict]: List of parsed event dictionaries
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return self._parse_csv_file(file)
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, "r", encoding="latin-1") as file:
                return self._parse_csv_file(file)
    
    def _parse_csv_file(self, file: TextIO) -> List[Dict[str, Any]]:
        """Parse CSV file and return list of events
        
        Args:
            file: File-like object
            
        Returns:
            List[Dict]: List of parsed event dictionaries
        """
        # Create CSV reader
        csv_reader = csv.reader(file, delimiter=self.separator)
        
        # Skip header row if present
        first_row = next(csv_reader, None)
        
        # Check if first row is header
        is_header = False
        if first_row:
            # Check if first row contains column names
            if all(col.lower() in [c.lower() for c in self.columns] for col in first_row):
                is_header = True
                
        # Reset file position if first row is not header
        if first_row and not is_header:
            file.seek(0)
            csv_reader = csv.reader(file, delimiter=self.separator)
        
        # Parse rows
        events = []
        for row in csv_reader:
            # Skip empty rows
            if not row or len(row) < len(self.columns):
                continue
                
            # Create event dictionary
            event = {}
            for i, column in enumerate(self.columns):
                if i < len(row):
                    event[column] = row[i].strip()
                else:
                    event[column] = ""
            
            # Convert datetime column
            if self.datetime_column in event:
                try:
                    event[self.datetime_column] = datetime.strptime(
                        event[self.datetime_column], 
                        self.datetime_format
                    )
                except (ValueError, TypeError):
                    # Keep original string if parsing fails
                    pass
            
            # Convert numeric columns
            if self.format_name == "deadside":
                # Convert distance to float
                if "distance" in event:
                    try:
                        event["distance"] = float(event["distance"])
                    except (ValueError, TypeError):
                        event["distance"] = 0.0
            
            # Add event to list
            events.append(event)
            
        return events
    
    def filter_events(self, events: List[Dict[str, Any]], 
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None,
                     player_id: Optional[str] = None,
                     min_distance: Optional[float] = None,
                     max_distance: Optional[float] = None,
                     weapon: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filter events by criteria
        
        Args:
            events: List of events to filter
            start_time: Start time for filtering (default: None)
            end_time: End time for filtering (default: None)
            player_id: Player ID for filtering (default: None)
            min_distance: Minimum distance for filtering (default: None)
            max_distance: Maximum distance for filtering (default: None)
            weapon: Weapon name for filtering (default: None)
            
        Returns:
            List[Dict]: Filtered events
        """
        # Start with all events
        filtered_events = events
        
        # Filter by time range
        if start_time or end_time:
            filtered_events = [
                event for event in filtered_events
                if (not start_time or event.get(self.datetime_column, datetime.min) >= start_time) and
                   (not end_time or event.get(self.datetime_column, datetime.max) <= end_time)
            ]
            
        # Filter by player ID
        if player_id:
            if self.format_name == "deadside":
                filtered_events = [
                    event for event in filtered_events
                    if event.get("killer_id") == player_id or event.get("victim_id") == player_id
                ]
            elif self.format_name == "custom":
                filtered_events = [
                    event for event in filtered_events
                    if event.get("player1_id") == player_id or event.get("player2_id") == player_id
                ]
                
        # Filter by distance range
        if (min_distance is not None or max_distance is not None) and "distance" in self.columns:
            filtered_events = [
                event for event in filtered_events
                if ((min_distance is None or event.get("distance", 0) >= min_distance) and
                    (max_distance is None or event.get("distance", float("inf")) <= max_distance))
            ]
            
        # Filter by weapon
        if weapon and "weapon" in self.columns:
            filtered_events = [
                event for event in filtered_events
                if event.get("weapon", "").lower() == weapon.lower()
            ]
            
        return filtered_events
    
    def aggregate_player_stats(self, events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Aggregate player statistics from events
        
        Args:
            events: List of events
            
        Returns:
            Dict[str, Dict]: Dictionary of player statistics by player ID
        """
        # Initialize player stats
        player_stats = {}
        
        if self.format_name == "deadside":
            # Process deadside format
            for event in events:
                killer_id = event.get("killer_id")
                victim_id = event.get("victim_id")
                
                # Skip invalid events
                if not killer_id or not victim_id:
                    continue
                    
                # Extract event details
                killer_name = event.get("killer_name", "Unknown")
                victim_name = event.get("victim_name", "Unknown")
                weapon = event.get("weapon", "Unknown")
                distance = event.get("distance", 0)
                timestamp = event.get(self.datetime_column, datetime.now())
                
                # Update killer stats
                if killer_id not in player_stats:
                    player_stats[killer_id] = {
                        "player_id": killer_id,
                        "player_name": killer_name,
                        "kills": 0,
                        "deaths": 0,
                        "weapons": {},
                        "victims": {},
                        "killers": {},
                        "longest_kill": 0,
                        "total_distance": 0,
                        "first_seen": timestamp,
                        "last_seen": timestamp
                    }
                    
                killer_stats = player_stats[killer_id]
                killer_stats["kills"] += 1
                killer_stats["weapons"][weapon] = killer_stats["weapons"].get(weapon, 0) + 1
                killer_stats["victims"][victim_id] = killer_stats["victims"].get(victim_id, 0) + 1
                killer_stats["total_distance"] += distance
                killer_stats["longest_kill"] = max(killer_stats["longest_kill"], distance)
                killer_stats["last_seen"] = max(killer_stats["last_seen"], timestamp)
                
                # Update victim stats
                if victim_id not in player_stats:
                    player_stats[victim_id] = {
                        "player_id": victim_id,
                        "player_name": victim_name,
                        "kills": 0,
                        "deaths": 0,
                        "weapons": {},
                        "victims": {},
                        "killers": {},
                        "longest_kill": 0,
                        "total_distance": 0,
                        "first_seen": timestamp,
                        "last_seen": timestamp
                    }
                    
                victim_stats = player_stats[victim_id]
                victim_stats["deaths"] += 1
                victim_stats["killers"][killer_id] = victim_stats["killers"].get(killer_id, 0) + 1
                victim_stats["last_seen"] = max(victim_stats["last_seen"], timestamp)
                
        elif self.format_name == "custom":
            # Process custom format
            pass
        
        # Calculate additional statistics
        for player_id, stats in player_stats.items():
            # Calculate K/D ratio
            stats["kd_ratio"] = stats["kills"] / max(stats["deaths"], 1)
            
            # Calculate average kill distance
            if stats["kills"] > 0:
                stats["avg_kill_distance"] = stats["total_distance"] / stats["kills"]
            else:
                stats["avg_kill_distance"] = 0
                
            # Calculate playtime estimate
            stats["playtime"] = (stats["last_seen"] - stats["first_seen"]).total_seconds() / 3600
            
            # Get favorite weapon
            if stats["weapons"]:
                stats["favorite_weapon"] = max(stats["weapons"].items(), key=lambda x: x[1])[0]
            else:
                stats["favorite_weapon"] = "None"
                
            # Get most killed player
            if stats["victims"]:
                most_killed_id = max(stats["victims"].items(), key=lambda x: x[1])[0]
                stats["most_killed"] = {
                    "player_id": most_killed_id,
                    "player_name": player_stats.get(most_killed_id, {}).get("player_name", "Unknown"),
                    "count": stats["victims"][most_killed_id]
                }
            else:
                stats["most_killed"] = None
                
            # Get nemesis (player killed by the most)
            if stats["killers"]:
                nemesis_id = max(stats["killers"].items(), key=lambda x: x[1])[0]
                stats["nemesis"] = {
                    "player_id": nemesis_id,
                    "player_name": player_stats.get(nemesis_id, {}).get("player_name", "Unknown"),
                    "count": stats["killers"][nemesis_id]
                }
            else:
                stats["nemesis"] = None
        
        return player_stats
    
    def get_leaderboard(self, player_stats: Dict[str, Dict[str, Any]], stat_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Generate leaderboard from player statistics
        
        Args:
            player_stats: Dictionary of player statistics by player ID
            stat_name: Statistic name to rank by
            limit: Maximum number of entries (default: 10)
            
        Returns:
            List[Dict]: Leaderboard entries
        """
        # Sort players by statistic
        sorted_players = sorted(
            [stats for _, stats in player_stats.items()],
            key=lambda x: x.get(stat_name, 0),
            reverse=True
        )
        
        # Create leaderboard entries
        leaderboard = []
        for i, player in enumerate(sorted_players[:limit]):
            leaderboard.append({
                "rank": i + 1,
                "player_id": player["player_id"],
                "player_name": player["player_name"],
                "value": player.get(stat_name, 0)
            })
            
        return leaderboard
    
    def detect_format(self, data: Union[str, bytes]) -> str:
        """Detect log format from data
        
        Args:
            data: CSV data string or bytes
            
        Returns:
            str: Detected format name
        """
        # Convert bytes to string if needed
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
            
        # Create CSV reader for each format
        csv_file = io.StringIO(data)
        
        try:
            # Get first line
            first_line = csv_file.readline().strip()
            
            # Reset file position
            csv_file.seek(0)
            
            # Check semicolon separator (deadside)
            if ";" in first_line and len(first_line.split(";")) >= 7:
                separator = ";"
                parts = first_line.split(";")
                
                # Check for timestamp format
                if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", parts[0]):
                    return "deadside"
            
            # Check comma separator (custom)
            if "," in first_line and len(first_line.split(",")) >= 6:
                separator = ","
                parts = first_line.split(",")
                
                # Check for timestamp format
                if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", parts[0]):
                    return "custom"
            
            # Default to deadside
            return "deadside"
            
        finally:
            csv_file.close()
    
    def add_custom_format(self, format_name: str, format_config: Dict[str, Any]) -> None:
        """Add custom log format
        
        Args:
            format_name: Format name
            format_config: Format configuration
        """
        # Validate format configuration
        required_keys = ["separator", "columns", "datetime_format", "datetime_column"]
        for key in required_keys:
            if key not in format_config:
                raise ValueError(f"Missing required key in format config: {key}")
                
        # Add format to LOG_FORMATS
        self.LOG_FORMATS[format_name] = format_config
        
        # Update current format if matching
        if format_name == self.format_name:
            self.format_config = format_config
            self.separator = format_config["separator"]
            self.columns = format_config["columns"]
            self.datetime_format = format_config["datetime_format"]
            self.datetime_column = format_config["datetime_column"]