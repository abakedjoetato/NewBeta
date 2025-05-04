"""
CSV Processor cog for the Tower of Temptation PvP Statistics Discord Bot.

This cog provides:
1. Background task for downloading and processing CSV files from game servers
2. Commands for manually processing CSV files
3. Admin commands for managing CSV processing
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.csv_parser import CSVParser
from utils.sftp import SFTPManager
from utils.embed_builder import EmbedBuilder
from utils.helpers import has_admin_permission

logger = logging.getLogger(__name__)

class CSVProcessorCog(commands.Cog):
    """Commands and background tasks for processing CSV files"""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the CSV processor cog
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.csv_parser = CSVParser()
        # Don't initialize SFTP manager here, we'll create instances as needed
        self.sftp_managers = {}  # Store SFTP managers by server_id
        self.processing_lock = asyncio.Lock()
        self.is_processing = False
        self.last_processed = {}  # Track last processed timestamp per server
        
        # Start background task
        self.process_csv_files_task.start()
    
    def cog_unload(self):
        """Stop background tasks and close connections when cog is unloaded"""
        self.process_csv_files_task.cancel()
        
        # Close all SFTP connections
        for server_id, sftp_manager in self.sftp_managers.items():
            try:
                asyncio.create_task(sftp_manager.disconnect())
            except Exception as e:
                logger.error(f"Error disconnecting SFTP for server {server_id}: {e}")
    
    @tasks.loop(minutes=5.0)
    async def process_csv_files_task(self):
        """Background task for processing CSV files
        
        This task runs every 5 minutes and checks for new CSV files on all configured servers.
        """
        if self.is_processing:
            logger.debug("Skipping CSV processing - already running")
            return
        
        self.is_processing = True
        
        try:
            # Get list of configured servers
            server_configs = await self._get_server_configs()
            
            for server_id, config in server_configs.items():
                try:
                    await self._process_server_csv_files(server_id, config)
                except Exception as e:
                    logger.error(f"Error processing CSV files for server {server_id}: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error in CSV processing task: {str(e)}")
        
        finally:
            self.is_processing = False
    
    @process_csv_files_task.before_loop
    async def before_process_csv_files_task(self):
        """Wait for bot to be ready before starting task"""
        await self.bot.wait_until_ready()
        # Add a small delay to avoid startup issues
        await asyncio.sleep(10)
    
    async def _get_server_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all servers with SFTP enabled
        
        Returns:
            Dict: Dictionary of server IDs to server configurations
        """
        # TODO: Implement actual server config retrieval
        # Placeholder for now
        return {
            "test_server": {
                "sftp_host": os.environ.get("SFTP_HOST", "localhost"),
                "sftp_port": int(os.environ.get("SFTP_PORT", "22")),
                "sftp_username": os.environ.get("SFTP_USERNAME", "user"),
                "sftp_password": os.environ.get("SFTP_PASSWORD", "password"),
                "sftp_path": os.environ.get("SFTP_PATH", "/logs"),
                "csv_pattern": r"\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}\.csv"
            }
        }
    
    async def _process_server_csv_files(self, server_id: str, config: Dict[str, Any]) -> Tuple[int, int]:
        """Process CSV files for a specific server
        
        Args:
            server_id: Server ID
            config: Server configuration
            
        Returns:
            Tuple[int, int]: Number of files processed and total death events processed
        """
        # Connect to SFTP server
        hostname = config["sftp_host"]
        port = config["sftp_port"]
        username = config["sftp_username"]
        password = config["sftp_password"]
        
        # Get last processed time or default to 24 hours ago
        last_time = self.last_processed.get(server_id, datetime.now() - timedelta(days=1))
        
        # Format for SFTP directory listing comparison
        last_time_str = last_time.strftime("%Y.%m.%d-%H.%M.%S")
        
        try:
            # Create a new SFTP client for this server if not already existing
            if server_id not in self.sftp_managers:
                self.sftp_managers[server_id] = SFTPManager(
                    hostname=hostname,
                    port=port,
                    username=username,
                    password=password
                )
            
            # Get the SFTP client for this server
            sftp = self.sftp_managers[server_id]
            
            # Connect to the SFTP server
            await sftp.connect()
            
            try:
                # List directory
                path = config["sftp_path"]
                files = await sftp.list_directory(path)
                
                # Filter for CSV files
                csv_pattern = config.get("csv_pattern", r".*\.csv$")
                csv_files = [f for f in files if re.match(csv_pattern, f)]
                
                # Sort chronologically
                csv_files.sort()
                
                # Filter for files newer than last processed
                new_files = [f for f in csv_files if f > last_time_str]
                
                # Process each file
                files_processed = 0
                events_processed = 0
                
                for file in new_files:
                    try:
                        # Download file content
                        file_path = f"{path}/{file}"
                        content = await sftp.download_file(file_path)
                        
                        if content:
                            # Process content
                            processed, errors = await self.csv_parser.process_and_update_rivalries(
                                server_id, content.decode('utf-8')
                            )
                            
                            events_processed += processed
                            files_processed += 1
                            
                            if errors:
                                logger.warning(f"Errors processing {file}: {len(errors)} errors")
                            
                            # Update last processed time if this is the newest file
                            if file == new_files[-1]:
                                try:
                                    file_time = datetime.strptime(file.split('.csv')[0], "%Y.%m.%d-%H.%M.%S")
                                    self.last_processed[server_id] = file_time
                                except ValueError:
                                    # If we can't parse the timestamp from filename, use current time
                                    self.last_processed[server_id] = datetime.now()
                    
                    except Exception as e:
                        logger.error(f"Error processing file {file}: {str(e)}")
                
                return files_processed, events_processed
                
            finally:
                # Disconnect from the SFTP server
                await sftp.disconnect()
                
        except Exception as e:
            logger.error(f"SFTP error for server {server_id}: {str(e)}")
            return 0, 0
    
    @app_commands.command(name="process_csv")
    @app_commands.describe(
        server_id="The server ID to process CSV files for",
        hours="Number of hours to look back (default: 24)"
    )
    async def process_csv_command(
        self,
        interaction: discord.Interaction,
        server_id: Optional[str] = None,
        hours: Optional[int] = 24
    ):
        """Manually process CSV files from the game server
        
        Args:
            interaction: Discord interaction
            server_id: Server ID to process (optional)
            hours: Number of hours to look back (default: 24)
        """
        # Check permissions
        if not has_admin_permission(interaction):
            embed = EmbedBuilder.error(
                title="Permission Denied",
                description="You don't have permission to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get server ID from guild config if not provided
        if not server_id:
            # For now, hardcode a test server ID
            server_id = "test_server"
        
        # Get server config
        server_configs = await self._get_server_configs()
        
        if server_id not in server_configs:
            embed = EmbedBuilder.error(
                title="Server Not Found",
                description=f"No SFTP configuration found for server `{server_id}`."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Calculate lookback time
        self.last_processed[server_id] = datetime.now() - timedelta(hours=hours)
        
        # Process CSV files
        async with self.processing_lock:
            try:
                files_processed, events_processed = await self._process_server_csv_files(
                    server_id, server_configs[server_id]
                )
                
                if files_processed > 0:
                    embed = EmbedBuilder.success(
                        title="CSV Processing Complete",
                        description=f"Processed {files_processed} file(s) with {events_processed} death events."
                    )
                else:
                    embed = EmbedBuilder.info(
                        title="No Files Found",
                        description=f"No new CSV files found for server `{server_id}` in the last {hours} hours."
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as e:
                logger.error(f"Error processing CSV files: {str(e)}")
                embed = EmbedBuilder.error(
                    title="Processing Error",
                    description=f"An error occurred while processing CSV files: {str(e)}"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="clear_csv_cache")
    async def clear_csv_cache_command(self, interaction: discord.Interaction):
        """Clear the CSV parser cache
        
        Args:
            interaction: Discord interaction
        """
        # Check permissions
        if not has_admin_permission(interaction):
            embed = EmbedBuilder.error(
                title="Permission Denied",
                description="You don't have permission to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Clear cache
        self.csv_parser.clear_cache()
        
        embed = EmbedBuilder.success(
            title="Cache Cleared",
            description="The CSV parser cache has been cleared."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="csv_status")
    async def csv_status_command(self, interaction: discord.Interaction):
        """Show CSV processor status
        
        Args:
            interaction: Discord interaction
        """
        # Check permissions
        if not has_admin_permission(interaction):
            embed = EmbedBuilder.error(
                title="Permission Denied",
                description="You don't have permission to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get server configs
        server_configs = await self._get_server_configs()
        
        # Create status embed
        embed = EmbedBuilder.info(
            title="CSV Processor Status",
            description="Current status of the CSV processor"
        )
        
        # Add processing status
        embed.add_field(
            name="Currently Processing",
            value="Yes" if self.is_processing else "No",
            inline=True
        )
        
        # Add configured servers
        server_list = []
        for server_id, config in server_configs.items():
            last_time = self.last_processed.get(server_id, "Never")
            if isinstance(last_time, datetime):
                last_time = last_time.strftime("%Y-%m-%d %H:%M:%S")
            
            server_list.append(f"• `{server_id}` - Last processed: {last_time}")
        
        if server_list:
            embed.add_field(
                name="Configured Servers",
                value="\n".join(server_list),
                inline=False
            )
        else:
            embed.add_field(
                name="Configured Servers",
                value="No servers configured",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    """Set up the CSV processor cog"""
    await bot.add_cog(CSVProcessorCog(bot))