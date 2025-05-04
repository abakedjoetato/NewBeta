"""
Embed Builder for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Standard embed generation
2. Themed embed styles
3. Common embed layouts
4. Utility functions for embed creation
"""
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple

import discord

logger = logging.getLogger(__name__)

class EmbedBuilder:
    """Utility class for building Discord embeds"""
    
    # Embed color palette
    COLORS = {
        "primary": 0x3498db,    # Blue
        "success": 0x2ecc71,    # Green
        "warning": 0xf39c12,    # Orange
        "error": 0xe74c3c,      # Red
        "info": 0x9b59b6,       # Purple
        "neutral": 0x95a5a6,    # Gray
        "faction_a": 0xe74c3c,  # Red for Faction A
        "faction_b": 0x3498db,  # Blue for Faction B
        
        # Additional colors for variety
        "gold": 0xf1c40f,
        "silver": 0xbdc3c7,
        "bronze": 0xcd6133,
        "emerald": 0x2ecc71,
        "ruby": 0xe74c3c,
        "sapphire": 0x3498db,
        "amethyst": 0x9b59b6,
        "topaz": 0xf39c12,
        "diamond": 0x1abc9c,
    }
    
    # Common icons
    ICONS = {
        "success": "https://i.imgur.com/FcaXvqo.png",  # Green checkmark
        "warning": "https://i.imgur.com/rYMeoCZ.png",  # Yellow warning
        "error": "https://i.imgur.com/gfo8TJj.png",    # Red error
        "info": "https://i.imgur.com/wMFN7Qj.png",     # Blue info
        "neutral": "https://i.imgur.com/ViHN3X2.png",  # Gray neutral
        "sword": "https://i.imgur.com/JGocbFP.png",    # Sword icon
        "shield": "https://i.imgur.com/4HkY3BB.png",   # Shield icon
        "trophy": "https://i.imgur.com/lPJeQXG.png",   # Trophy icon
        "skull": "https://i.imgur.com/X8QUQxS.png",    # Skull icon
        "crown": "https://i.imgur.com/TzUnLSU.png",    # Crown icon
        "stats": "https://i.imgur.com/YVgjUHM.png",    # Stats icon
        "settings": "https://i.imgur.com/K4JZrZ4.png", # Settings icon
        "faction_a": "https://i.imgur.com/DLXqXXa.png", # Faction A icon (placeholder)
        "faction_b": "https://i.imgur.com/2uDQ7m1.png", # Faction B icon (placeholder)
    }
    
    @classmethod
    async def create_embed(cls, 
                          title: Optional[str] = None, 
                          description: Optional[str] = None, 
                          color: Optional[int] = None,
                          fields: Optional[List[Dict[str, Any]]] = None,
                          thumbnail_url: Optional[str] = None,
                          image_url: Optional[str] = None,
                          author_name: Optional[str] = None,
                          author_url: Optional[str] = None,
                          author_icon_url: Optional[str] = None,
                          footer_text: Optional[str] = None,
                          footer_icon_url: Optional[str] = None,
                          timestamp: Optional[datetime] = None,
                          url: Optional[str] = None,
                          guild: Optional[discord.Guild] = None,
                          bot: Optional[discord.Client] = None) -> discord.Embed:
        """Create a Discord embed with the given parameters
        
        Args:
            title: Embed title (default: None)
            description: Embed description (default: None)
            color: Embed color (default: None)
            fields: List of field dictionaries with name, value, and inline keys (default: None)
            thumbnail_url: URL for thumbnail image (default: None)
            image_url: URL for main image (default: None)
            author_name: Name for author field (default: None)
            author_url: URL for author field (default: None)
            author_icon_url: Icon URL for author field (default: None)
            footer_text: Text for footer (default: None)
            footer_icon_url: Icon URL for footer (default: None)
            timestamp: Timestamp to display (default: None)
            url: URL for title (default: None)
            
        Returns:
            discord.Embed: Created embed
        """
        # Create embed with color or default
        embed = discord.Embed(color=color or cls.COLORS["primary"])
        
        # Set title and description if provided
        if title:
            embed.title = title
            
        if description:
            embed.description = description
            
        if url:
            embed.url = url
        
        # Add fields if provided
        if fields:
            for field in fields:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", False)
                )
        
        # Set thumbnail if provided
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
            
        # Set image if provided
        if image_url:
            embed.set_image(url=image_url)
            
        # Set author if provided
        if author_name:
            embed.set_author(
                name=author_name,
                url=author_url,
                icon_url=author_icon_url
            )
            
        # Set footer if provided
        if footer_text:
            # If our footer contains "Powered By", let's use the bot's nickname if available
            from utils.helpers import get_bot_name
            
            if footer_text and "Powered By" in footer_text and bot and guild:
                # Replace the standard bot name with the nickname if available
                bot_name = get_bot_name(bot, guild)
                footer_text = footer_text.replace("Discord Bot", bot_name)
            
            embed.set_footer(
                text=footer_text,
                icon_url=footer_icon_url
            )
            
        # Set timestamp if provided
        if timestamp:
            embed.timestamp = timestamp
        
        return embed
    
    @classmethod
    async def success_embed(cls, 
                           title: Optional[str] = None, 
                           description: Optional[str] = None,
                           thumbnail: bool = False,
                           guild: Optional[discord.Guild] = None,
                           bot: Optional[discord.Client] = None,
                           **kwargs) -> discord.Embed:
        """Create a success-themed embed
        
        Args:
            title: Embed title (default: None)
            description: Embed description (default: None)
            thumbnail: Whether to show success icon as thumbnail (default: False)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            **kwargs: Additional arguments for create_embed
            
        Returns:
            discord.Embed: Success-themed embed
        """
        # Set success color
        kwargs["color"] = cls.COLORS["success"]
        
        # Add success icon as thumbnail if requested
        if thumbnail and "thumbnail_url" not in kwargs:
            kwargs["thumbnail_url"] = cls.ICONS["success"]
            
        # Set default title if not provided
        if not title:
            title = "Success"
        
        # Add guild and bot to kwargs if not already present
        if "guild" not in kwargs and guild is not None:
            kwargs["guild"] = guild
            
        if "bot" not in kwargs and bot is not None:
            kwargs["bot"] = bot
            
        return await cls.create_embed(
            title=title,
            description=description,
            **kwargs
        )
    
    @classmethod
    async def error_embed(cls, 
                         title: Optional[str] = None, 
                         description: Optional[str] = None,
                         thumbnail: bool = False,
                         guild: Optional[discord.Guild] = None,
                         bot: Optional[discord.Client] = None,
                         **kwargs) -> discord.Embed:
        """Create an error-themed embed
        
        Args:
            title: Embed title (default: None)
            description: Embed description (default: None)
            thumbnail: Whether to show error icon as thumbnail (default: False)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            **kwargs: Additional arguments for create_embed
            
        Returns:
            discord.Embed: Error-themed embed
        """
        # Set error color
        kwargs["color"] = cls.COLORS["error"]
        
        # Add error icon as thumbnail if requested
        if thumbnail and "thumbnail_url" not in kwargs:
            kwargs["thumbnail_url"] = cls.ICONS["error"]
            
        # Set default title if not provided
        if not title:
            title = "Error"
        
        # Add guild and bot to kwargs if not already present
        if "guild" not in kwargs and guild is not None:
            kwargs["guild"] = guild
            
        if "bot" not in kwargs and bot is not None:
            kwargs["bot"] = bot
            
        return await cls.create_embed(
            title=title,
            description=description,
            **kwargs
        )
    
    @classmethod
    async def warning_embed(cls, 
                           title: Optional[str] = None, 
                           description: Optional[str] = None,
                           thumbnail: bool = False,
                           guild: Optional[discord.Guild] = None,
                           bot: Optional[discord.Client] = None,
                           **kwargs) -> discord.Embed:
        """Create a warning-themed embed
        
        Args:
            title: Embed title (default: None)
            description: Embed description (default: None)
            thumbnail: Whether to show warning icon as thumbnail (default: False)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            **kwargs: Additional arguments for create_embed
            
        Returns:
            discord.Embed: Warning-themed embed
        """
        # Set warning color
        kwargs["color"] = cls.COLORS["warning"]
        
        # Add warning icon as thumbnail if requested
        if thumbnail and "thumbnail_url" not in kwargs:
            kwargs["thumbnail_url"] = cls.ICONS["warning"]
            
        # Set default title if not provided
        if not title:
            title = "Warning"
            
        # Add guild and bot to kwargs if not already present
        if "guild" not in kwargs and guild is not None:
            kwargs["guild"] = guild
            
        if "bot" not in kwargs and bot is not None:
            kwargs["bot"] = bot
            
        return await cls.create_embed(
            title=title,
            description=description,
            **kwargs
        )
    
    @classmethod
    async def info_embed(cls, 
                        title: Optional[str] = None, 
                        description: Optional[str] = None,
                        thumbnail: bool = False,
                        guild: Optional[discord.Guild] = None,
                        bot: Optional[discord.Client] = None,
                        **kwargs) -> discord.Embed:
        """Create an info-themed embed
        
        Args:
            title: Embed title (default: None)
            description: Embed description (default: None)
            thumbnail: Whether to show info icon as thumbnail (default: False)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            **kwargs: Additional arguments for create_embed
            
        Returns:
            discord.Embed: Info-themed embed
        """
        # Set info color
        kwargs["color"] = cls.COLORS["info"]
        
        # Add info icon as thumbnail if requested
        if thumbnail and "thumbnail_url" not in kwargs:
            kwargs["thumbnail_url"] = cls.ICONS["info"]
            
        # Set default title if not provided
        if not title:
            title = "Information"
            
        # Add guild and bot to kwargs if not already present
        if "guild" not in kwargs and guild is not None:
            kwargs["guild"] = guild
            
        if "bot" not in kwargs and bot is not None:
            kwargs["bot"] = bot
            
        return await cls.create_embed(
            title=title,
            description=description,
            **kwargs
        )
    
    @classmethod
    async def player_stats_embed(cls, 
                                player_name: str, 
                                stats: Dict[str, Any], 
                                avatar_url: Optional[str] = None,
                                faction_color: Optional[int] = None,
                                guild: Optional[discord.Guild] = None,
                                bot: Optional[discord.Client] = None) -> discord.Embed:
        """Create a player statistics embed
        
        Args:
            player_name: Player name
            stats: Player statistics dictionary
            avatar_url: Player avatar URL (default: None)
            faction_color: Faction color (default: None)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            
        Returns:
            discord.Embed: Player statistics embed
        """
        # Set color based on faction or default
        color = faction_color or cls.COLORS["primary"]
        
        # Format player stats
        fields = [
            {"name": "Kills", "value": str(stats.get("kills", 0)), "inline": True},
            {"name": "Deaths", "value": str(stats.get("deaths", 0)), "inline": True},
            {"name": "K/D Ratio", "value": f"{stats.get('kd_ratio', 0.0):.2f}", "inline": True},
            {"name": "Favorite Weapon", "value": stats.get("favorite_weapon", "None"), "inline": True},
            {"name": "Longest Kill", "value": f"{stats.get('longest_kill', 0)}m", "inline": True},
            {"name": "Playtime", "value": stats.get("playtime", "0h"), "inline": True},
        ]
        
        # Add additional stats if available
        if "level" in stats:
            fields.append({"name": "Level", "value": str(stats["level"]), "inline": True})
            
        if "rank" in stats:
            fields.append({"name": "Rank", "value": f"#{stats['rank']}", "inline": True})
            
        # Create embed
        return await cls.create_embed(
            title=f"{player_name}'s Statistics",
            color=color,
            fields=fields,
            thumbnail_url=avatar_url or cls.ICONS["stats"],
            footer_text="Last updated",
            timestamp=datetime.utcnow(),
            guild=guild,
            bot=bot
        )
    
    @classmethod
    async def faction_stats_embed(cls, 
                                faction_name: str, 
                                stats: Dict[str, Any], 
                                faction_icon: Optional[str] = None,
                                faction_color: Optional[int] = None,
                                guild: Optional[discord.Guild] = None,
                                bot: Optional[discord.Client] = None) -> discord.Embed:
        """Create a faction statistics embed
        
        Args:
            faction_name: Faction name
            stats: Faction statistics dictionary
            faction_icon: Faction icon URL (default: None)
            faction_color: Faction color (default: None)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            
        Returns:
            discord.Embed: Faction statistics embed
        """
        # Set color based on faction or default
        if faction_color:
            color = faction_color
        elif faction_name.lower() == "faction a":
            color = cls.COLORS["faction_a"]
        elif faction_name.lower() == "faction b":
            color = cls.COLORS["faction_b"]
        else:
            color = cls.COLORS["primary"]
        
        # Set icon based on faction or default
        if faction_icon:
            icon = faction_icon
        elif faction_name.lower() == "faction a":
            icon = cls.ICONS["faction_a"]
        elif faction_name.lower() == "faction b":
            icon = cls.ICONS["faction_b"]
        else:
            icon = cls.ICONS["stats"]
        
        # Format faction stats
        fields = [
            {"name": "Members", "value": str(stats.get("members", 0)), "inline": True},
            {"name": "Total Kills", "value": str(stats.get("total_kills", 0)), "inline": True},
            {"name": "Total Deaths", "value": str(stats.get("total_deaths", 0)), "inline": True},
            {"name": "K/D Ratio", "value": f"{stats.get('kd_ratio', 0.0):.2f}", "inline": True},
            {"name": "Territory", "value": stats.get("territory", "None"), "inline": True},
            {"name": "Ranking", "value": f"#{stats.get('rank', 0)}", "inline": True},
        ]
        
        # Add top players if available
        if "top_players" in stats and stats["top_players"]:
            top_players = "\n".join([f"{i+1}. {player}" for i, player in enumerate(stats["top_players"])])
            fields.append({"name": "Top Players", "value": top_players, "inline": False})
        
        # Create embed
        return await cls.create_embed(
            title=f"{faction_name} Statistics",
            color=color,
            fields=fields,
            thumbnail_url=icon,
            footer_text="Last updated",
            timestamp=datetime.utcnow(),
            guild=guild,
            bot=bot
        )
    
    @classmethod
    async def leaderboard_embed(cls, 
                              title: str, 
                              leaderboard: List[Dict[str, Any]],
                              color: Optional[int] = None,
                              icon: Optional[str] = None,
                              guild: Optional[discord.Guild] = None,
                              bot: Optional[discord.Client] = None) -> discord.Embed:
        """Create a leaderboard embed
        
        Args:
            title: Leaderboard title
            leaderboard: List of player/faction dictionaries with name, value, and rank
            color: Embed color (default: None)
            icon: Icon URL (default: None)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            
        Returns:
            discord.Embed: Leaderboard embed
        """
        # Set default color
        color = color or cls.COLORS["gold"]
        
        # Set default icon
        icon = icon or cls.ICONS["trophy"]
        
        # Format leaderboard
        description = ""
        
        for i, entry in enumerate(leaderboard[:10]):  # Show top 10
            # Generate medal emoji for top 3
            if i == 0:
                medal = "🥇"
            elif i == 1:
                medal = "🥈"
            elif i == 2:
                medal = "🥉"
            else:
                medal = f"`{i+1}.`"
                
            # Add entry to description
            description += f"{medal} **{entry['name']}** - {entry['value']}\n"
        
        # Create embed
        return await cls.create_embed(
            title=title,
            description=description,
            color=color,
            thumbnail_url=icon,
            footer_text="Last updated",
            timestamp=datetime.utcnow(),
            guild=guild,
            bot=bot
        )
    
    @classmethod
    async def create_base_embed(cls, 
                              title: str,
                              description: str,
                              color: Optional[int] = None,
                              guild: Optional[discord.Guild] = None,
                              bot: Optional[discord.Client] = None,
                              **kwargs) -> discord.Embed:
        """Create a base embed with standard formatting
        
        Args:
            title: Embed title
            description: Embed description
            color: Embed color (default: None)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            **kwargs: Additional arguments for create_embed
            
        Returns:
            discord.Embed: Base embed
        """
        # Set default color if not provided
        color = color or cls.COLORS["primary"]
        
        # Set timestamp to now if not provided
        if "timestamp" not in kwargs:
            kwargs["timestamp"] = datetime.utcnow()
            
        # Set default footer if not provided
        if "footer_text" not in kwargs:
            # Get bot name to use in footer
            from utils.helpers import get_bot_name
            bot_name = "Tower of Temptation"
            if bot and guild:
                bot_name = get_bot_name(bot, guild)
            
            kwargs["footer_text"] = f"Powered By {bot_name}"
        
        # Create embed
        return await cls.create_embed(
            title=title,
            description=description,
            color=color,
            guild=guild,
            bot=bot,
            **kwargs
        )
        
    @classmethod
    async def help_embed(cls, 
                        title: str, 
                        description: str,
                        commands: List[Dict[str, str]],
                        footer_text: Optional[str] = None,
                        guild: Optional[discord.Guild] = None,
                        bot: Optional[discord.Client] = None) -> discord.Embed:
        """Create a help embed
        
        Args:
            title: Help title
            description: Help description
            commands: List of command dictionaries with name and description
            footer_text: Footer text (default: None)
            guild: The Discord guild for customization (default: None)
            bot: The Discord bot instance for customization (default: None)
            
        Returns:
            discord.Embed: Help embed
        """
        # Create fields for commands
        fields = []
        
        for cmd in commands:
            fields.append({
                "name": cmd["name"],
                "value": cmd["description"],
                "inline": False
            })
        
        # If no custom footer text is provided, use a default with bot name
        if not footer_text and bot and guild:
            from utils.helpers import get_bot_name
            bot_name = get_bot_name(bot, guild)
            footer_text = f"Use /{bot_name} help <command> for more details"
        
        # Create embed
        return await cls.create_embed(
            title=title,
            description=description,
            color=cls.COLORS["info"],
            fields=fields,
            thumbnail_url=cls.ICONS["info"],
            footer_text=footer_text,
            timestamp=datetime.utcnow(),
            guild=guild,
            bot=bot
        )