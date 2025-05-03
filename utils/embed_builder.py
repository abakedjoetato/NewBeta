"""
Embed builder module for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. EmbedBuilder class for creating consistent themed embeds
2. Predefined color schemes and styles
3. Utility methods for various embed types
"""
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple

import discord

logger = logging.getLogger(__name__)

class EmbedBuilder:
    """EmbedBuilder class for creating consistent themed embeds"""
    
    # Discord embed color constants
    BLUE_COLOR = 0x3498DB
    RED_COLOR = 0xE74C3C
    GREEN_COLOR = 0x2ECC71
    GOLD_COLOR = 0xF1C40F
    PURPLE_COLOR = 0x9B59B6
    ORANGE_COLOR = 0xE67E22
    TEAL_COLOR = 0x1ABC9C
    DARK_BLUE_COLOR = 0x206694
    DEFAULT_COLOR = 0x7289DA
    ERROR_COLOR = 0xFF0000
    
    # Bot branding constants
    DEFAULT_ICON_URL = "https://cdn.discordapp.com/emojis/1111111111111111111.png"  # Replace with actual default icon
    DEFAULT_FOOTER = "Tower of Temptation PvP Stats"
    
    # Faction color mapping
    FACTION_COLORS = {
        "red": RED_COLOR,
        "blue": BLUE_COLOR,
        "green": GREEN_COLOR,
        "gold": GOLD_COLOR,
        "purple": PURPLE_COLOR,
        "orange": ORANGE_COLOR,
        "teal": TEAL_COLOR,
        "dark_blue": DARK_BLUE_COLOR
    }
    
    @classmethod
    def primary(
        cls,
        title: str,
        description: Optional[str] = None,
        timestamp: bool = True,
        color: Optional[int] = None,
        footer: Optional[str] = None,
        footer_icon: Optional[str] = None,
        thumbnail: Optional[str] = None,
        image: Optional[str] = None,
        author_name: Optional[str] = None,
        author_icon: Optional[str] = None,
        author_url: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None
    ) -> discord.Embed:
        """Create a primary styled embed
        
        Args:
            title: Embed title
            description: Embed description (optional)
            timestamp: Whether to add timestamp (default: True)
            color: Embed color (optional - defaults to PRIMARY_COLOR)
            footer: Footer text (optional)
            footer_icon: Footer icon URL (optional)
            thumbnail: Thumbnail URL (optional)
            image: Image URL (optional)
            author_name: Author name (optional)
            author_icon: Author icon URL (optional)
            author_url: Author URL (optional)
            fields: List of field dictionaries (optional)
            
        Returns:
            discord.Embed: Created embed
        """
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or cls.DEFAULT_COLOR
        )
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        # Add footer
        if footer or footer_icon:
            embed.set_footer(
                text=footer or cls.DEFAULT_FOOTER,
                icon_url=footer_icon
            )
        
        # Add thumbnail
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        # Add image
        if image:
            embed.set_image(url=image)
        
        # Add author
        if author_name:
            embed.set_author(
                name=author_name,
                icon_url=author_icon,
                url=author_url
            )
        
        # Add fields
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get("name", ""),
                    value=field.get("value", ""),
                    inline=field.get("inline", False)
                )
        
        return embed
    
    @classmethod
    def info(
        cls,
        title: str,
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create an info styled embed
        
        Args:
            title: Embed title
            description: Embed description (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        kwargs.setdefault("color", cls.BLUE_COLOR)
        return cls.primary(title, description, **kwargs)
    
    @classmethod
    def success(
        cls,
        title: str,
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a success styled embed
        
        Args:
            title: Embed title
            description: Embed description (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        kwargs.setdefault("color", cls.GREEN_COLOR)
        return cls.primary(title, description, **kwargs)
    
    @classmethod
    def error(
        cls,
        title: str,
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create an error styled embed
        
        Args:
            title: Embed title
            description: Embed description (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        kwargs.setdefault("color", cls.ERROR_COLOR)
        return cls.primary(title, description, **kwargs)
    
    @classmethod
    def warning(
        cls,
        title: str,
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a warning styled embed
        
        Args:
            title: Embed title
            description: Embed description (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        kwargs.setdefault("color", cls.ORANGE_COLOR)
        return cls.primary(title, description, **kwargs)
    
    @classmethod
    def faction(
        cls,
        faction_name: str,
        faction_tag: str,
        description: Optional[str] = None,
        color: Optional[int] = None,
        icon_url: Optional[str] = None,
        banner_url: Optional[str] = None,
        member_count: Optional[int] = None,
        stats: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a faction styled embed
        
        Args:
            faction_name: Faction name
            faction_tag: Faction tag
            description: Faction description (optional)
            color: Faction color (optional)
            icon_url: Faction icon URL (optional)
            banner_url: Faction banner URL (optional)
            member_count: Faction member count (optional)
            stats: Faction stats (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        # Set title with faction tag
        title = f"{faction_name} [{faction_tag}]"
        
        # Create embed
        embed = cls.primary(
            title=title,
            description=description,
            color=color or cls.DEFAULT_COLOR,
            thumbnail=icon_url,
            image=banner_url,
            **kwargs
        )
        
        # Add member count
        if member_count is not None:
            embed.add_field(
                name="Members",
                value=str(member_count),
                inline=True
            )
        
        # Add stats
        if stats:
            for stat_name, stat_value in stats.items():
                if isinstance(stat_value, (int, float)):
                    embed.add_field(
                        name=stat_name.replace("_", " ").title(),
                        value=str(stat_value),
                        inline=True
                    )
        
        return embed
    
    @classmethod
    def player(
        cls,
        player_name: str,
        server_name: str,
        description: Optional[str] = None,
        avatar_url: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
        rank: Optional[int] = None,
        faction: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a player styled embed
        
        Args:
            player_name: Player name
            server_name: Server name
            description: Player description (optional)
            avatar_url: Player avatar URL (optional)
            stats: Player stats (optional)
            rank: Player rank (optional)
            faction: Player faction (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        # Set title with rank if available
        if rank:
            title = f"#{rank} {player_name}"
        else:
            title = player_name
        
        # Set color based on faction if available
        color = cls.DEFAULT_COLOR
        if faction and "color" in faction:
            color = faction.get("color")
        
        # Create embed
        embed = cls.primary(
            title=title,
            description=description,
            color=color,
            thumbnail=avatar_url,
            **kwargs
        )
        
        # Add server
        embed.add_field(
            name="Server",
            value=server_name,
            inline=True
        )
        
        # Add faction
        if faction:
            faction_text = f"{faction.get('name')} [{faction.get('tag')}]"
            embed.add_field(
                name="Faction",
                value=faction_text,
                inline=True
            )
        
        # Add stats
        if stats:
            # First add kills and deaths
            if "kills" in stats:
                embed.add_field(
                    name="Kills",
                    value=str(stats.get("kills", 0)),
                    inline=True
                )
            
            if "deaths" in stats:
                embed.add_field(
                    name="Deaths",
                    value=str(stats.get("deaths", 0)),
                    inline=True
                )
            
            # Calculate and add K/D ratio
            kills = stats.get("kills", 0)
            deaths = stats.get("deaths", 0)
            if kills or deaths:
                kd_ratio = kills / max(deaths, 1)
                embed.add_field(
                    name="K/D Ratio",
                    value=f"{kd_ratio:.2f}",
                    inline=True
                )
            
            # Add other stats
            for stat_name, stat_value in stats.items():
                if stat_name not in ["kills", "deaths"] and isinstance(stat_value, (int, float)):
                    embed.add_field(
                        name=stat_name.replace("_", " ").title(),
                        value=str(stat_value),
                        inline=True
                    )
        
        return embed
    
    @classmethod
    def rivalry(
        cls,
        player1_name: str,
        player2_name: str,
        player1_kills: int,
        player2_kills: int,
        total_kills: int,
        description: Optional[str] = None,
        player1_avatar: Optional[str] = None,
        player2_avatar: Optional[str] = None,
        last_kill: Optional[datetime] = None,
        last_weapon: Optional[str] = None,
        last_location: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a rivalry styled embed
        
        Args:
            player1_name: First player name
            player2_name: Second player name
            player1_kills: First player kills
            player2_kills: Second player kills
            total_kills: Total kills
            description: Rivalry description (optional)
            player1_avatar: First player avatar URL (optional)
            player2_avatar: Second player avatar URL (optional)
            last_kill: Last kill timestamp (optional)
            last_weapon: Last weapon used (optional)
            last_location: Last kill location (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        # Set title and colors
        title = f"{player1_name} vs {player2_name}"
        
        if player1_kills > player2_kills:
            color = cls.RED_COLOR  # Player 1 leading
            score_text = f"**{player1_kills}** : {player2_kills}"
        elif player2_kills > player1_kills:
            color = cls.BLUE_COLOR  # Player 2 leading
            score_text = f"{player1_kills} : **{player2_kills}**"
        else:
            color = cls.GOLD_COLOR  # Tied
            score_text = f"**{player1_kills}** : **{player2_kills}**"
        
        # Calculate intensity score
        if total_kills <= 1:
            intensity = 0
        else:
            score_diff = abs(player1_kills - player2_kills)
            balance = 1.0 - (score_diff / total_kills)
            intensity = total_kills * (balance ** 2)
        
        # Create rivalry description
        if not description:
            # Generate different descriptions based on the intensity
            if intensity >= 20:
                description = "🔥 This rivalry is heating up with fierce competition!"
            elif intensity >= 10:
                description = "⚔️ A developing rivalry with consistent engagement."
            elif intensity >= 5:
                description = "👀 A budding rivalry worth keeping an eye on."
            else:
                description = "🏁 A new rivalry has begun."
        
        # Create embed
        embed = cls.primary(
            title=title,
            description=description,
            color=color,
            **kwargs
        )
        
        # Add score field
        embed.add_field(
            name="Score",
            value=score_text,
            inline=False
        )
        
        # Add total encounters
        embed.add_field(
            name="Total Encounters",
            value=str(total_kills),
            inline=True
        )
        
        # Add intensity rating
        embed.add_field(
            name="Intensity Rating",
            value=f"{intensity:.1f}/100",
            inline=True
        )
        
        # Add last kill details
        if last_kill:
            # Format last kill details
            kill_details = []
            
            if last_weapon:
                kill_details.append(f"Weapon: {last_weapon}")
            
            if last_location:
                kill_details.append(f"Location: {last_location}")
            
            # Add last kill field
            embed.add_field(
                name="Last Kill",
                value="\n".join(kill_details) if kill_details else "No details available",
                inline=False
            )
            
            # Set timestamp to last kill
            embed.timestamp = last_kill
        
        return embed
    
    @classmethod
    def server(
        cls,
        server_name: str,
        description: Optional[str] = None,
        icon_url: Optional[str] = None,
        player_count: Optional[int] = None,
        top_players: Optional[List[Dict[str, Any]]] = None,
        stats: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a server styled embed
        
        Args:
            server_name: Server name
            description: Server description (optional)
            icon_url: Server icon URL (optional)
            player_count: Player count (optional)
            top_players: Top players (optional)
            stats: Server stats (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        # Create embed
        embed = cls.primary(
            title=server_name,
            description=description,
            color=cls.TEAL_COLOR,
            thumbnail=icon_url,
            **kwargs
        )
        
        # Add player count
        if player_count is not None:
            embed.add_field(
                name="Players",
                value=str(player_count),
                inline=True
            )
        
        # Add stats
        if stats:
            for stat_name, stat_value in stats.items():
                if isinstance(stat_value, (int, float)):
                    embed.add_field(
                        name=stat_name.replace("_", " ").title(),
                        value=str(stat_value),
                        inline=True
                    )
        
        # Add top players
        if top_players and len(top_players) > 0:
            # Format top players as list
            top_players_text = ""
            for i, player in enumerate(top_players[:5], 1):
                player_name = player.get("name", "Unknown")
                kills = player.get("kills", 0)
                top_players_text += f"#{i} **{player_name}** - {kills} kills\n"
            
            embed.add_field(
                name="Top Players",
                value=top_players_text,
                inline=False
            )
        
        return embed
    
    @classmethod
    def leaderboard(
        cls,
        title: str,
        entries: List[Dict[str, Any]],
        description: Optional[str] = None,
        value_name: str = "Kills",
        max_entries: int = 10,
        thumbnail: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a leaderboard styled embed
        
        Args:
            title: Leaderboard title
            entries: Leaderboard entries
            description: Leaderboard description (optional)
            value_name: Name of value field (default: Kills)
            max_entries: Maximum number of entries to show (default: 10)
            thumbnail: Thumbnail URL (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        # Create embed
        embed = cls.primary(
            title=title,
            description=description,
            color=cls.GOLD_COLOR,
            thumbnail=thumbnail,
            **kwargs
        )
        
        # Add leaderboard entries
        if entries:
            # Format entries as fields or single field
            if len(entries) <= 3:
                # Format as separate fields
                for i, entry in enumerate(entries[:max_entries], 1):
                    name = entry.get("name", "Unknown")
                    value = entry.get("value", 0)
                    
                    embed.add_field(
                        name=f"#{i} {name}",
                        value=f"{value} {value_name}",
                        inline=True
                    )
            else:
                # Format as single field
                leaderboard_text = ""
                for i, entry in enumerate(entries[:max_entries], 1):
                    name = entry.get("name", "Unknown")
                    value = entry.get("value", 0)
                    
                    leaderboard_text += f"**#{i}** {name} - {value} {value_name}\n"
                
                embed.add_field(
                    name="Leaderboard",
                    value=leaderboard_text,
                    inline=False
                )
        else:
            embed.add_field(
                name="No entries",
                value="The leaderboard is currently empty.",
                inline=False
            )
        
        return embed
    
    @classmethod
    def paginated(
        cls,
        title: str,
        entries: List[Dict[str, Any]],
        page: int,
        total_pages: int,
        description: Optional[str] = None,
        color: Optional[int] = None,
        thumbnail: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a paginated embed
        
        Args:
            title: Embed title
            entries: List of entries for current page
            page: Current page number (1-indexed)
            total_pages: Total number of pages
            description: Embed description (optional)
            color: Embed color (optional)
            thumbnail: Thumbnail URL (optional)
            **kwargs: Additional arguments for primary method
            
        Returns:
            discord.Embed: Created embed
        """
        # Create embed
        embed = cls.primary(
            title=title,
            description=description,
            color=color or cls.DEFAULT_COLOR,
            thumbnail=thumbnail,
            **kwargs
        )
        
        # Add entries
        if entries:
            # Format entries as fields
            for entry in entries:
                name = entry.get("name", "")
                value = entry.get("value", "")
                inline = entry.get("inline", False)
                
                embed.add_field(
                    name=name,
                    value=value,
                    inline=inline
                )
        else:
            embed.add_field(
                name="No entries",
                value="There are no entries to display.",
                inline=False
            )
        
        # Add page indicator to footer
        footer_text = kwargs.get("footer", cls.DEFAULT_FOOTER)
        footer_icon = kwargs.get("footer_icon")
        
        embed.set_footer(
            text=f"{footer_text} • Page {page}/{total_pages}",
            icon_url=footer_icon
        )
        
        return embed