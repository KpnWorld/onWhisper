import discord
from discord.ext import commands
from utils.db_manager import DBManager
import json
from typing import Optional

class Debug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui = self.bot.ui_manager

    @commands.command(name="dbcheck")
    @commands.is_owner()
    async def db_check(self, ctx, collection: str, id: Optional[str] = None):
        """Check raw database entries for a collection"""
        try:
            if id:
                # Get specific entry
                data = await self.db_manager.get_data(collection, id)
                if data:
                    formatted = json.dumps(data, indent=2)
                    embed = self.ui.system_embed(
                        f"Database Entry: {collection}:{id}",
                        f"```json\n{formatted}\n```",
                        codeblock=False
                    )
                else:
                    embed = self.ui.error_embed(
                        "Not Found",
                        f"No data found for {collection}:{id}"
                    )
            else:
                # List all entries in collection
                prefix = f"{self.db_manager.prefix}{collection}:"
                entries = [key.replace(prefix, '') for key in self.db_manager.db.keys() 
                          if key.startswith(prefix)]
                
                if entries:
                    description = "\n".join(entries)
                    embed = self.ui.system_embed(
                        f"Database Entries in {collection}",
                        f"Total entries: {len(entries)}\n\nKeys:\n{description}"
                    )
                else:
                    embed = self.ui.error_embed(
                        "Empty Collection",
                        f"No entries found in {collection}"
                    )
                    
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

    @commands.command(name="dblookup")
    @commands.is_owner()
    async def db_lookup(self, ctx, collection: str, key: str, field: str):
        """Look up a specific field in a database entry"""
        try:
            data = await self.db_manager.get_data(collection, key)
            if not data:
                embed = self.ui.error_embed(
                    "Not Found",
                    f"No data found for {collection}:{key}"
                )
            elif field not in data:
                embed = self.ui.error_embed(
                    "Field Not Found",
                    f"Field '{field}' not found in {collection}:{key}"
                )
            else:
                value = data[field]
                embed = self.ui.system_embed(
                    f"Field Value: {field}",
                    f"Collection: {collection}\nKey: {key}\nValue: {value}"
                )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

    @commands.command(name="dbstats")
    @commands.is_owner()
    async def db_stats(self, ctx):
        """Show database statistics"""
        try:
            stats = await self.db_manager.get_connection_stats()
            if not stats:
                await ctx.send("Failed to get database stats")
                return

            description = (
                f"Total Keys: {stats['total_keys']}\n\n"
                "Collections:\n" + 
                "\n".join(f"• {k}: {v} entries" for k, v in stats['collections'].items())
            )
            
            embed = self.ui.system_embed(
                "Database Statistics",
                description
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

    @commands.command(name="guilddata")
    @commands.has_permissions(administrator=True)
    async def view_guild_data(self, ctx, collection: str = None):
        """View all data for the current guild, optionally filtered by collection"""
        try:
            data = await self.db_manager.get_all_guild_data(ctx.guild.id)
            
            if not data:
                embed = self.ui.error_embed(
                    "No Data",
                    "No data found for this guild"
                )
                await ctx.send(embed=embed)
                return
                
            if collection:
                if collection not in data:
                    embed = self.ui.error_embed(
                        "Collection Not Found",
                        f"No data found for collection '{collection}'"
                    )
                    await ctx.send(embed=embed)
                    return
                    
                # Show specific collection
                formatted = json.dumps(data[collection], indent=2)
                pages = []
                
                # Split into pages if too long
                chunk_size = 1900  # Discord limit minus some padding
                chunks = [formatted[i:i + chunk_size] for i in range(0, len(formatted), chunk_size)]
                
                for i, chunk in enumerate(chunks):
                    embed = self.ui.system_embed(
                        f"Guild Data - {collection} (Page {i+1}/{len(chunks)})",
                        f"```json\n{chunk}\n```",
                        codeblock=False
                    )
                    pages.append(embed)
                
                if len(pages) > 1:
                    await self.ui.paginate(ctx, pages, timeout=180)
                else:
                    await ctx.send(embed=pages[0])
            
            else:
                # Show overview
                description = "**Available Collections:**\n\n"
                for coll, entries in data.items():
                    description += f"• {coll}: {len(entries)} entries\n"
                description += "\nUse `!guilddata <collection>` to view specific data"
                
                embed = self.ui.system_embed(
                    f"Guild Data Overview - {ctx.guild.name}",
                    description
                )
                await ctx.send(embed=embed)
                
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

    @commands.command(name="dblist")
    @commands.is_owner()
    async def list_raw_db(self, ctx, filter_text: str = None):
        """List raw database key-value pairs, optionally filtered"""
        try:
            # Get all keys, optionally filtered
            keys = [k for k in self.db_manager.db.keys() 
                   if not filter_text or filter_text in k]
            
            if not keys:
                embed = self.ui.error_embed(
                    "No Data",
                    "No keys found" + (f" matching '{filter_text}'" if filter_text else "")
                )
                await ctx.send(embed=embed)
                return

            # Create pages of key-value pairs
            pages = []
            pairs_per_page = 5
            
            for i in range(0, len(keys), pairs_per_page):
                page_keys = keys[i:i + pairs_per_page]
                content = []
                
                for key in page_keys:
                    try:
                        value = self.db_manager.db[key]
                        # Try to parse and format JSON values
                        try:
                            parsed = json.loads(value)
                            formatted_value = json.dumps(parsed, indent=2)
                        except:
                            formatted_value = str(value)
                            
                        content.append(f"Key: {key}\nValue:\n```json\n{formatted_value}\n```")
                    except Exception as e:
                        content.append(f"Key: {key}\nError reading value: {str(e)}")

                description = "\n\n".join(content)
                embed = self.ui.system_embed(
                    f"Database Contents (Page {len(pages)+1})",
                    description,
                    codeblock=False
                )
                embed.set_footer(text=f"Showing {i+1}-{min(i+pairs_per_page, len(keys))} of {len(keys)} keys")
                pages.append(embed)

            if len(pages) > 1:
                await self.ui.paginate(ctx, pages, timeout=180)
            else:
                await ctx.send(embed=pages[0])

        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

async def setup(bot):
    await bot.add_cog(Debug(bot))
