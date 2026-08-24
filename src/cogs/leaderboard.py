import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from src.utils.i18n import t, translate_rank

async def update_leaderboard_panel(bot, guild_id):
    """Actualiza la tabla de líderes estática."""
    try:
        from src.database import db as database_module
        lang = await database_module.get_guild_language(guild_id)

        async with aiosqlite.connect("rivalsconnect.db") as db:
            async with db.execute('SELECT leaderboard_channel_id, leaderboard_msg_id FROM guild_config WHERE guild_id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return
                channel_id, msg_id = row
                
            async with db.execute('SELECT discord_name, elo_score FROM users WHERE elo_score > 0 ORDER BY elo_score DESC LIMIT 10') as cursor:
                top_players = await cursor.fetchall()
                
        channel = bot.get_channel(channel_id)
        if not channel: return
        
        try:
            msg = await channel.fetch_message(msg_id)
        except discord.NotFound:
            return
            
        embed = discord.Embed(
            title=t("lb_title", lang),
            description=t("lb_panel_desc", lang),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        if not top_players:
            embed.description = t("lb_panel_empty", lang)
        else:
            medals = ["🥇", "🥈", "🥉"]
            import src.database.db as db_mod
            for index, player in enumerate(top_players):
                name, elo = player
                rank_icon = medals[index] if index < 3 else f"**{index+1}.**"
                rank_key = await db_mod.get_user_rank(elo)
                rango = translate_rank(rank_key, lang)
                embed.add_field(name=f"{rank_icon} {name}", value=f"**{rango}** | {elo} ELO", inline=False)
                
        embed.set_footer(text=t("lb_panel_footer", lang))
        await msg.edit(embed=embed)
    except Exception as e:
        print(f"Error actualizando leaderboard: {e}")

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Muestra los jugadores con mayor ELO en el servidor.")
    async def leaderboard(self, interaction: discord.Interaction):
        from src.database import db as database_module
        lang = await database_module.get_user_language(interaction.user.id)
        
        # Buscar los top 10 usuarios en BD
        async with aiosqlite.connect("rivalsconnect.db") as database:
            async with database.execute('SELECT discord_name, elo_score FROM users WHERE elo_score > 0 ORDER BY elo_score DESC LIMIT 10') as cursor:
                top_players = await cursor.fetchall()
                
        if not top_players:
            await interaction.response.send_message(t("lb_empty", lang), ephemeral=True)
            return
            
        embed = discord.Embed(
            title=t("lb_title", lang),
            description=t("lb_desc", lang),
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for index, player in enumerate(top_players):
            name = player[0]
            elo = player[1]
            
            rank_icon = medals[index] if index < 3 else f"**{index+1}.**"
            embed.add_field(name=f"{rank_icon} {name}", value=f"**{elo}** ELO", inline=False)
            
        embed.set_footer(text=t("lb_footer", lang))
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))

