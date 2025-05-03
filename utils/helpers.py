"""
Helper utilities for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Pagination utilities for embeds and messages
2. Permission checking functions
3. UI components for interactive buttons and selects
4. Confirmation dialogs and message formatting
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# Permission check functions
def has_admin_permission(interaction: discord.Interaction) -> bool:
    """Check if user has administrator permission
    
    Args:
        interaction: Discord interaction
        
    Returns:
        bool: True if user has administrator permission
    """
    if interaction.guild is None:
        return False
    
    if interaction.user.id == interaction.guild.owner_id:
        return True
    
    if interaction.user.guild_permissions.administrator:
        return True
    
    return False

def has_mod_permission(interaction: discord.Interaction) -> bool:
    """Check if user has moderator permission
    
    Args:
        interaction: Discord interaction
        
    Returns:
        bool: True if user has moderator permission
    """
    if interaction.guild is None:
        return False
    
    if interaction.user.id == interaction.guild.owner_id:
        return True
    
    if interaction.user.guild_permissions.administrator:
        return True
    
    if interaction.user.guild_permissions.manage_guild:
        return True
    
    if interaction.user.guild_permissions.ban_members:
        return True
    
    return False

# Pagination components
class PaginationView(discord.ui.View):
    """View for paginating through embeds"""
    
    def __init__(
        self,
        embeds: List[discord.Embed],
        user_id: int,
        timeout: int = 300
    ):
        """Initialize pagination view
        
        Args:
            embeds: List of embeds to paginate
            user_id: User ID of the initiator
            timeout: Button timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.user_id = user_id
        self.current_page = 0
        self.total_pages = len(embeds)
        
        # Disable buttons if only one page
        if self.total_pages == 1:
            self.first_page_button.disabled = True
            self.prev_page_button.disabled = True
            self.next_page_button.disabled = True
            self.last_page_button.disabled = True
        
        # Update button labels
        self.page_indicator.label = f"Page {self.current_page + 1}/{self.total_pages}"
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if interaction is from the same user
        
        Args:
            interaction: Discord interaction
            
        Returns:
            bool: True if interaction is from the same user
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "These buttons are not for you!",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(
        emoji="⏮️",
        style=discord.ButtonStyle.gray,
        row=0
    )
    async def first_page_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """First page button callback
        
        Args:
            interaction: Discord interaction
            button: Button that was pressed
        """
        self.current_page = 0
        self.page_indicator.label = f"Page {self.current_page + 1}/{self.total_pages}"
        
        # Disable/enable buttons
        self.first_page_button.disabled = self.current_page == 0
        self.prev_page_button.disabled = self.current_page == 0
        self.next_page_button.disabled = self.current_page == self.total_pages - 1
        self.last_page_button.disabled = self.current_page == self.total_pages - 1
        
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )
    
    @discord.ui.button(
        emoji="◀️",
        style=discord.ButtonStyle.gray,
        row=0
    )
    async def prev_page_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Previous page button callback
        
        Args:
            interaction: Discord interaction
            button: Button that was pressed
        """
        self.current_page = max(0, self.current_page - 1)
        self.page_indicator.label = f"Page {self.current_page + 1}/{self.total_pages}"
        
        # Disable/enable buttons
        self.first_page_button.disabled = self.current_page == 0
        self.prev_page_button.disabled = self.current_page == 0
        self.next_page_button.disabled = self.current_page == self.total_pages - 1
        self.last_page_button.disabled = self.current_page == self.total_pages - 1
        
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )
    
    @discord.ui.button(
        label="Page 1/1",
        style=discord.ButtonStyle.gray,
        disabled=True,
        row=0
    )
    async def page_indicator(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Page indicator button callback (disabled)
        
        Args:
            interaction: Discord interaction
            button: Button that was pressed
        """
        # This button doesn't do anything, it's just an indicator
        pass
    
    @discord.ui.button(
        emoji="▶️",
        style=discord.ButtonStyle.gray,
        row=0
    )
    async def next_page_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Next page button callback
        
        Args:
            interaction: Discord interaction
            button: Button that was pressed
        """
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.page_indicator.label = f"Page {self.current_page + 1}/{self.total_pages}"
        
        # Disable/enable buttons
        self.first_page_button.disabled = self.current_page == 0
        self.prev_page_button.disabled = self.current_page == 0
        self.next_page_button.disabled = self.current_page == self.total_pages - 1
        self.last_page_button.disabled = self.current_page == self.total_pages - 1
        
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )
    
    @discord.ui.button(
        emoji="⏭️",
        style=discord.ButtonStyle.gray,
        row=0
    )
    async def last_page_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Last page button callback
        
        Args:
            interaction: Discord interaction
            button: Button that was pressed
        """
        self.current_page = self.total_pages - 1
        self.page_indicator.label = f"Page {self.current_page + 1}/{self.total_pages}"
        
        # Disable/enable buttons
        self.first_page_button.disabled = self.current_page == 0
        self.prev_page_button.disabled = self.current_page == 0
        self.next_page_button.disabled = self.current_page == self.total_pages - 1
        self.last_page_button.disabled = self.current_page == self.total_pages - 1
        
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )

async def paginate_embeds(
    interaction: discord.Interaction,
    embeds: List[discord.Embed],
    timeout: int = 300,
    ephemeral: bool = False
) -> None:
    """Paginate a list of embeds
    
    Args:
        interaction: Discord interaction
        embeds: List of embeds to paginate
        timeout: Timeout for buttons in seconds
        ephemeral: Whether to send as ephemeral message
    """
    if not embeds:
        return
    
    # Create pagination view
    view = PaginationView(embeds, interaction.user.id, timeout)
    
    # Check if interaction has been responded to
    if interaction.response.is_done():
        # Send new message
        await interaction.followup.send(
            embed=embeds[0],
            view=view,
            ephemeral=ephemeral
        )
    else:
        # Respond to interaction
        await interaction.response.send_message(
            embed=embeds[0],
            view=view,
            ephemeral=ephemeral
        )

# Confirmation dialog
class ConfirmView(discord.ui.View):
    """View for confirmation buttons"""
    
    def __init__(
        self,
        user_id: int,
        on_confirm: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
        timeout: int = 60
    ):
        """Initialize confirmation view
        
        Args:
            user_id: User ID of the initiator
            on_confirm: Callback for confirmation
            on_cancel: Callback for cancellation
            timeout: Button timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.value = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if interaction is from the same user
        
        Args:
            interaction: Discord interaction
            
        Returns:
            bool: True if interaction is from the same user
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "These buttons are not for you!",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.green,
        row=0
    )
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Confirm button callback
        
        Args:
            interaction: Discord interaction
            button: Button that was pressed
        """
        self.value = True
        self.stop()
        
        if self.on_confirm:
            await self.on_confirm(interaction)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.red,
        row=0
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Cancel button callback
        
        Args:
            interaction: Discord interaction
            button: Button that was pressed
        """
        self.value = False
        self.stop()
        
        if self.on_cancel:
            await self.on_cancel(interaction)
        else:
            await interaction.response.defer()

async def confirm(
    interaction: discord.Interaction,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    timeout: int = 60,
    ephemeral: bool = False
) -> bool:
    """Show a confirmation dialog
    
    Args:
        interaction: Discord interaction
        content: Message content
        embed: Message embed
        timeout: Button timeout in seconds
        ephemeral: Whether to show as ephemeral message
        
    Returns:
        bool: True if confirmed, False if cancelled or timed out
    """
    view = ConfirmView(interaction.user.id, timeout=timeout)
    
    # Check if interaction has been responded to
    if interaction.response.is_done():
        # Send new message
        message = await interaction.followup.send(
            content=content,
            embed=embed,
            view=view,
            ephemeral=ephemeral
        )
    else:
        # Respond to interaction
        await interaction.response.send_message(
            content=content,
            embed=embed,
            view=view,
            ephemeral=ephemeral
        )
        # Get the message
        message = await interaction.original_response()
    
    # Wait for button press or timeout
    await view.wait()
    
    # Clean up buttons if not timed out
    if view.value is not None and not ephemeral:
        await message.edit(view=None)
    
    return view.value or False

# Select menus
class BaseSelectMenu(discord.ui.Select):
    """Base class for select menus"""
    
    def __init__(
        self,
        placeholder: str,
        options: List[discord.SelectOption],
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        row: Optional[int] = None
    ):
        """Initialize select menu
        
        Args:
            placeholder: Placeholder text
            options: Select options
            min_values: Minimum number of values to select
            max_values: Maximum number of values to select
            disabled: Whether the select is disabled
            row: Row to place the select in
        """
        super().__init__(
            placeholder=placeholder,
            options=options,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            row=row
        )
        
    async def callback(self, interaction: discord.Interaction):
        """Callback when an option is selected
        
        Args:
            interaction: Discord interaction
        """
        view = self.view
        view.selected_values = self.values
        view.stop()

class SelectView(discord.ui.View):
    """View for select menus"""
    
    def __init__(
        self,
        user_id: int,
        select_menu: BaseSelectMenu,
        timeout: int = 60
    ):
        """Initialize select view
        
        Args:
            user_id: User ID of the initiator
            select_menu: Select menu to show
            timeout: Button timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.selected_values = None
        
        # Add the select menu
        self.add_item(select_menu)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if interaction is from the same user
        
        Args:
            interaction: Discord interaction
            
        Returns:
            bool: True if interaction is from the same user
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This select menu is not for you!",
                ephemeral=True
            )
            return False
        return True

async def show_select_menu(
    interaction: discord.Interaction,
    placeholder: str,
    options: List[discord.SelectOption],
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    min_values: int = 1,
    max_values: int = 1,
    timeout: int = 60,
    ephemeral: bool = False
) -> List[str]:
    """Show a select menu and get selected values
    
    Args:
        interaction: Discord interaction
        placeholder: Placeholder text
        options: Select options
        content: Message content
        embed: Message embed
        min_values: Minimum number of values to select
        max_values: Maximum number of values to select
        timeout: Button timeout in seconds
        ephemeral: Whether to show as ephemeral message
        
    Returns:
        List[str]: Selected values, or empty list if cancelled or timed out
    """
    # Create select menu
    select_menu = BaseSelectMenu(
        placeholder=placeholder,
        options=options,
        min_values=min_values,
        max_values=max_values
    )
    
    # Create view
    view = SelectView(interaction.user.id, select_menu, timeout=timeout)
    
    # Check if interaction has been responded to
    if interaction.response.is_done():
        # Send new message
        message = await interaction.followup.send(
            content=content,
            embed=embed,
            view=view,
            ephemeral=ephemeral
        )
    else:
        # Respond to interaction
        await interaction.response.send_message(
            content=content,
            embed=embed,
            view=view,
            ephemeral=ephemeral
        )
        # Get the message
        message = await interaction.original_response()
    
    # Wait for selection or timeout
    await view.wait()
    
    # Clean up buttons if not timed out
    if view.selected_values is not None and not ephemeral:
        await message.edit(view=None)
    
    return view.selected_values or []