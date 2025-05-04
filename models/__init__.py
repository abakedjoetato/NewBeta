"""
Models package for the Tower of Temptation PvP Statistics Discord Bot.

This package provides database models for interacting with MongoDB.
"""

# Import all models to make them available from the models package
from models.guild import Guild
from models.server import Server
from models.player import Player
from models.economy import Economy
from models.player_link import PlayerLink
from models.bounty import Bounty
from models.faction import Faction
from models.rivalry import Rivalry
from models.server_config import ServerConfig
from models.event import Event

# These models will be available via: from models import ModelName

__all__ = [
    'Guild', 
    'Server', 
    'Player', 
    'Economy', 
    'PlayerLink',
    'Bounty',
    'Faction',
    'Rivalry',
    'ServerConfig',
    'Event'
]