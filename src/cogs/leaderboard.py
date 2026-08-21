import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite

async def update_leaderboard_panel(bot, guild_id):
    """Actualiza la tabla de líderes estática."""
    try:
        async with aiosqlite.connect("rivalsconnect.db") as db:
            async with db.execute('SELECT leaderboard_channel_id, leaderboard_msg_id FROM guild_config WHERE guild_id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return
                channel_id, msg_id = row
                
            async with db.execute('SELECT discord_name, current_elo FROM users WHERE current_elo > 0 ORDER BY current_elo DESC LIMIT 10') as cursor:
                top_players = await cursor.fetchall()
                
        channel = bot.get_channel(channel_id)
        if not channel: return
        
        try:
            msg = await channel.fetch_message(msg_id)
        except discord.NotFound:
            return
            
        embed = discord.Embed(
            title="🏆 Clasificación del Servidor",
            description="Ranking oficial de RivalsConnect.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        if not top_players:
            embed.description = "Aún no hay partidas jugadas para mostrar ranking."
        else:
            medals = ["🥇", "🥈", "🥉"]
            for index, player in enumerate(top_players):
                name, elo = player
                rank_icon = medals[index] if index < 3 else f"**{index+1}.**"
                embed.add_field(name=f"{rank_icon} {name}", value=f"**{elo}** ELO", inline=False)
                
        embed.set_footer(text="RivalsConnect | Actualización automática")
        await msg.edit(embed=embed)
    except Exception as e:
        print(f"Error actualizando leaderboard: {e}")

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Muestra los jugadores con mayor ELO en el servidor.")
    async def leaderboard(self, interaction: discord.Interaction):
        import aiosqlite
        
        # Buscar los top 10 usuarios en BD
        async with aiosqlite.connect("rivalsconnect.db") as database:
            async with database.execute('SELECT discord_name, current_elo, highest_elo FROM users WHERE current_elo > 0 ORDER BY current_elo DESC LIMIT 10') as cursor:
                top_players = await cursor.fetchall()
                
        if not top_players:
            await interaction.response.send_message("Aún no hay suficientes partidas jugadas para mostrar una clasificación.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🏆 Clasificación del Servidor",
            description="Los mejores agentes de Marvel Rivals.",
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for index, player in enumerate(top_players):
            name = player[0]
            elo = player[1]
            
            rank_icon = medals[index] if index < 3 else f"**{index+1}.**"
            embed.add_field(name=f"{rank_icon} {name}", value=f"**{elo}** ELO", inline=False)
            
        embed.set_footer(text="RivalsConnect | Se actualiza en tiempo real")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
