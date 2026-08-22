import discord
from discord.ext import commands
from discord import app_commands
from src.database import db
from src.utils.i18n import t

CROWDIN_LINK = 'https://crowdin.com/project/rivalsconnect'

class HelpDropdown(discord.ui.Select):
    def __init__(self, lang='es'):
        self.lang = lang
        options = [
            discord.SelectOption(
                label=t('help_cat_config', lang), 
                description=t('help_cat_config_desc', lang), 
                value='config'
            ),
            discord.SelectOption(
                label=t('help_cat_stats', lang), 
                description=t('help_cat_stats_desc', lang), 
                value='stats'
            )
        ]
        super().__init__(placeholder=t('help_placeholder', lang), min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        embed = discord.Embed(color=discord.Color.blue())
        
        if self.values[0] == 'config':
            embed.title = t('help_cat_config', self.lang)
            embed.add_field(name='/setup', value=t('cmd_setup', self.lang), inline=False)
            embed.add_field(name='/configprofile', value=t('cmd_configprofile', self.lang), inline=False)
            embed.add_field(name='/language', value=t('cmd_language', self.lang), inline=False)
            
        elif self.values[0] == 'stats':
            embed.title = t('help_cat_stats', self.lang)
            embed.add_field(name='/profile', value=t('cmd_profile', self.lang), inline=False)
            embed.add_field(name='/leaderboard', value=t('cmd_leaderboard', self.lang), inline=False)
            
        embed.set_footer(text='RivalsConnect | Datos Oficiales')
        await interaction.response.edit_message(embed=embed, view=view)

class HelpView(discord.ui.View):
    def __init__(self, lang='es'):
        super().__init__(timeout=300)
        self.lang = lang
        
        self.add_item(HelpDropdown(lang))
        
        home_btn = discord.ui.Button(label=t('help_btn_home', lang), style=discord.ButtonStyle.secondary, row=1)
        home_btn.callback = self.home_callback
        self.add_item(home_btn)
        
        close_btn = discord.ui.Button(label=t('help_btn_close', lang), style=discord.ButtonStyle.danger, row=1)
        close_btn.callback = self.close_callback
        self.add_item(close_btn)

    async def home_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=t('help_title', self.lang),
            description=t('help_desc_main', self.lang),
            color=discord.Color.blue()
        )
        embed.add_field(name='\u200b', value=t('help_commands_total', self.lang, num=5), inline=False)
        embed.add_field(name=t('help_links_title', self.lang), value=t('help_links_value', self.lang, crowdin=CROWDIN_LINK), inline=False)
        
        await interaction.response.edit_message(embed=embed, view=HelpView(self.lang))

    async def close_callback(self, interaction: discord.Interaction):
        await interaction.message.delete()

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='help', description='Muestra el menú de ayuda y los comandos del bot.')
    async def help_command(self, interaction: discord.Interaction):
        lang = await db.get_user_language(interaction.user.id)
        
        embed = discord.Embed(
            title=t('help_title', lang),
            description=t('help_desc_main', lang),
            color=discord.Color.blue()
        )
        embed.add_field(name='\u200b', value=t('help_commands_total', lang, num=5), inline=False)
        embed.add_field(name=t('help_links_title', lang), value=t('help_links_value', lang, crowdin=CROWDIN_LINK), inline=False)
        
        view = HelpView(lang)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Help(bot))
