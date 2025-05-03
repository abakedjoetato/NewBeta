"""
Helper utilities for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Pagination for embeds
2. Permission checking utility functions
3. Interactive confirmation UI
4. Other general utility functions
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Callable

import discord
from discord.ext import commands

from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)

def has_admin_permission(interaction: discord.Interaction) -> bool:
    """Check if a user has admin permissions
    
    Args:
        interaction: Discord interaction
        
    Returns:
        bool: True if user has admin permissions
    """
    if interaction.user.guild_permissions.administrator:
        return True
    
    if interaction.user.id == interaction.guild.owner_id:
        return True
    
    return False

def has_mod_permission(interaction: discord.Interaction) -> bool:
    """Check if a user has moderator permissions
    
    Args:
        interaction: Discord interaction
        
    Returns:
        bool: True if user has moderator permissions
    """
    if has_admin_permission(interaction):
        return True
    
    if interaction.user.guild_permissions.manage_channels:
        return True
    
    if interaction.user.guild_permissions.kick_members:
        return True
    
    return False

async def confirm(
    interaction: discord.Interaction,
    message: str,
    timeout: int = 60,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    ephemeral: bool = True
) -> bool:
    """Ask for confirmation with buttons
    
    Args:
        interaction: Discord interaction
        message: Confirmation message
        timeout: Timeout in seconds
        confirm_label: Label for confirm button
        cancel_label: Label for cancel button
        ephemeral: Whether to send as ephemeral message
        
    Returns:
        bool: True if confirmed, False if canceled or timed out
    """
    # Create view with confirm/cancel buttons
    class ConfirmView(discord.ui.View):
        def __init__(self, timeout: int):
            super().__init__(timeout=timeout)
            self.value = None
        
        @discord.ui.button(label=confirm_label, style=discord.ButtonStyle.green)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = True
            self.stop()
            await interaction.response.defer()
        
        @discord.ui.button(label=cancel_label, style=discord.ButtonStyle.grey)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = False
            self.stop()
            await interaction.response.defer()
    
    # Create view and send confirmation
    view = ConfirmView(timeout=timeout)
    
    if interaction.response.is_done():
        # If response is already done, send followup
        msg = await interaction.followup.send(message, view=view, ephemeral=ephemeral)
    else:
        # Otherwise send initial response
        await interaction.response.send_message(message, view=view, ephemeral=ephemeral)
        msg = await interaction.original_response()
    
    # Wait for user response
    await view.wait()
    
    # Edit message to disable buttons if interaction timed out
    if view.value is None:
        view.disable_all_items()
        if ephemeral:
            await msg.edit(content=f"{message}\n\n*Timed out*", view=view)
        else:
            try:
                await msg.edit(content=f"{message}\n\n*Timed out*", view=view)
            except discord.HTTPException:
                pass
    
    return view.value or False

async def paginate_embeds(
    interaction: discord.Interaction,
    embeds: List[discord.Embed],
    timeout: int = 60,
    ephemeral: bool = False
) -> None:
    """Display paginated embeds
    
    Args:
        interaction: Discord interaction
        embeds: List of embeds to paginate
        timeout: Timeout in seconds
        ephemeral: Whether to send as ephemeral message
    """
    if not embeds:
        return
    
    # Create view with pagination buttons
    class PaginationView(discord.ui.View):
        def __init__(self, embeds: List[discord.Embed], timeout: int):
            super().__init__(timeout=timeout)
            self.embeds = embeds
            self.current_page = 0
            self.total_pages = len(embeds)
            self._update_buttons()
        
        def _update_buttons(self):
            # Update button states based on current page
            self.first_page.disabled = self.current_page == 0
            self.prev_page.disabled = self.current_page == 0
            self.next_page.disabled = self.current_page == self.total_pages - 1
            self.last_page.disabled = self.current_page == self.total_pages - 1
            
            # Update page counter
            self.page_counter.label = f"{self.current_page + 1}/{self.total_pages}"
        
        async def _update_message(self, interaction: discord.Interaction):
            # Update footer with page information
            embed = self.embeds[self.current_page]
            footer_text = embed.footer.text or EmbedBuilder.DEFAULT_FOOTER
            
            if not footer_text.endswith(f" • Page {self.current_page + 1}/{self.total_pages}"):
                footer_text = f"{footer_text} • Page {self.current_page + 1}/{self.total_pages}"
                embed.set_footer(text=footer_text, icon_url=embed.footer.icon_url)
            
            # Update buttons
            self._update_buttons()
            
            # Send update
            await interaction.response.edit_message(embed=embed, view=self)
        
        @discord.ui.button(label="<<", style=discord.ButtonStyle.grey)
        async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = 0
            await self._update_message(interaction)
        
        @discord.ui.button(label="<", style=discord.ButtonStyle.blurple)
        async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = max(0, self.current_page - 1)
            await self._update_message(interaction)
        
        @discord.ui.button(label="1/1", style=discord.ButtonStyle.grey, disabled=True)
        async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
            # This button is just a counter, doesn't do anything
            await interaction.response.defer()
        
        @discord.ui.button(label=">", style=discord.ButtonStyle.blurple)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = min(self.total_pages - 1, self.current_page + 1)
            await self._update_message(interaction)
        
        @discord.ui.button(label=">>", style=discord.ButtonStyle.grey)
        async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = self.total_pages - 1
            await self._update_message(interaction)
        
        async def on_timeout(self):
            # Disable all buttons on timeout
            for item in self.children:
                item.disabled = True
            
            # Try to update the message (may fail if message is deleted)
            try:
                await self.message.edit(view=self)
            except:
                pass
    
    # If only one embed, just send it without pagination
    if len(embeds) == 1:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embeds[0], ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embeds[0], ephemeral=ephemeral)
        return
    
    # Create view for pagination
    view = PaginationView(embeds, timeout=timeout)
    
    # Add page number to first embed footer
    first_embed = embeds[0]
    footer_text = first_embed.footer.text or EmbedBuilder.DEFAULT_FOOTER
    footer_text = f"{footer_text} • Page 1/{len(embeds)}"
    first_embed.set_footer(text=footer_text, icon_url=first_embed.footer.icon_url)
    
    # Send message with pagination
    if interaction.response.is_done():
        msg = await interaction.followup.send(embed=first_embed, view=view, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(embed=first_embed, view=view, ephemeral=ephemeral)
        msg = await interaction.original_response()
    
    # Store message for later reference (used in on_timeout)
    view.message = msg

def format_timedelta(seconds: int) -> str:
    """Format seconds as human-readable time
    
    Args:
        seconds: Number of seconds
        
    Returns:
        str: Formatted time string
    """
    if seconds < 60:
        return f"{seconds} seconds"
    
    minutes = seconds // 60
    seconds %= 60
    
    if minutes < 60:
        if seconds == 0:
            return f"{minutes} minutes"
        return f"{minutes} minutes, {seconds} seconds"
    
    hours = minutes // 60
    minutes %= 60
    
    if hours < 24:
        if minutes == 0:
            return f"{hours} hours"
        return f"{hours} hours, {minutes} minutes"
    
    days = hours // 24
    hours %= 24
    
    if days < 7:
        if hours == 0:
            return f"{days} days"
        return f"{days} days, {hours} hours"
    
    weeks = days // 7
    days %= 7
    
    if weeks < 4:
        if days == 0:
            return f"{weeks} weeks"
        return f"{weeks} weeks, {days} days"
    
    months = days // 30
    weeks %= 4
    
    if months == 0:
        return f"{weeks} weeks"
    if weeks == 0:
        return f"{months} months"
    
    return f"{months} months, {weeks} weeks"

def trim_string(text: str, max_length: int = 1024, ellipsis: str = "...") -> str:
    """Trim a string to fit within Discord embed limits
    
    Args:
        text: Text to trim
        max_length: Maximum length
        ellipsis: String to add at the end if trimmed
        
    Returns:
        str: Trimmed string
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(ellipsis)] + ellipsis