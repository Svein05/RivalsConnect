from aiohttp import web
import json
import logging
import aiosqlite
import discord
from src.utils.storage import get_channel
from src.utils.parser import create_embed_from_data
from src.database import db

logger = logging.getLogger("overwolf_server")

async def handle_options(request):
    """Maneja las peticiones OPTIONS pre-flight de CORS."""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
    }
    return web.Response(headers=headers, status=200)

async def handle_verify(request):
    """Endpoint para que la UI de Overwolf verifique el código."""
    headers = {"Access-Control-Allow-Origin": "*"}
    try:
        data = await request.json()
        code = data.get("code")
        user = await db.get_user_by_code(code)
        
        if user:
            # Notificar al usuario en Discord que la vinculación fue exitosa
            from src.cogs.auth import pending_links
            interaction = pending_links.get(code)
            if interaction:
                embed = discord.Embed(
                    title="✅ Vinculación Exitosa",
                    description=f"¡Tu cuenta ha sido conectada con RivalsConnect exitosamente, **{user[1]}**!",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Ya puedes cerrar la ventana de Overwolf.")
                try:
                    await interaction.edit_original_response(embed=embed)
                    del pending_links[code]
                except Exception as e:
                    logger.warning(f"No se pudo editar el mensaje de /link: {e}")
                    
            return web.json_response({
                "success": True,
                "discord_user": user[1],
                "discord_avatar": user[2]
            }, headers=headers)
        return web.json_response({"success": False}, headers=headers)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, headers=headers)

active_messages = {} # Diccionario para guardar el ID del mensaje de la partida activa

async def handle_overwolf_events(request):
    """Maneja las peticiones POST enviadas por la app de Overwolf."""
    bot = request.app['bot']
    headers = {
        "Access-Control-Allow-Origin": "*"
    }
    
    try:
        data = await request.json()
        
        # Si es un ping de comprobación de conexión o salud
        if data.get("event") == "ping":
            return web.Response(status=200, headers=headers, text="pong")

        link_code = data.get("link_code")
        if not link_code:
            return web.Response(status=401, headers=headers, text="Missing link_code")
            
        # Verificar usuario en DB
        user = await db.get_user_by_code(link_code)
        if not user:
            return web.Response(status=401, headers=headers, text="Invalid link_code")
            
        discord_id = user[0]
        discord_name = user[1]
        discord_avatar = user[2]
        
        # Procesar los eventos del juego simples (fuera del canal)
        event_name = data.get("event")
        
        if event_name == "ping":
            return web.Response(status=200, headers=headers, text="pong")
            
        elif event_name == "status_update":
            status = data.get("status", "Desconectado")
            async with aiosqlite.connect("rivalsconnect.db") as database:
                if status == "Desconectado":
                    await database.execute('UPDATE users SET status = ?, is_playing = 0 WHERE discord_id = ?', (status, discord_id))
                else:
                    await database.execute('UPDATE users SET status = ? WHERE discord_id = ?', (status, discord_id))
                await database.commit()
                
            # Actualizar live panel
            async with aiosqlite.connect("rivalsconnect.db") as db_conn:
                async with db_conn.execute('SELECT guild_id FROM guild_config LIMIT 1') as cursor:
                    row = await cursor.fetchone()
                    if row:
                        from src.cogs.live_panel import update_live_panel
                        await update_live_panel(bot, row[0])
            return web.Response(status=200, headers=headers, text="OK")
        
        # ...
        channel_id = None
        guild_id = None
        
        # Recuperar configuración
        async with aiosqlite.connect("rivalsconnect.db") as database:
            async with database.execute('SELECT guild_id, logs_channel_id FROM guild_config LIMIT 1') as cursor:
                row = await cursor.fetchone()
                if row:
                    guild_id = row[0]
                    channel_id = row[1]
                    
        if channel_id and guild_id:
            channel = bot.get_channel(channel_id)
            if channel:
                elo_change = 0
                
                # Procesar Estados del Usuario para el Live Panel
                if event_name == "match_start":
                    map_name = data.get("map", "Desconocido")
                    mode_name = data.get("mode", "Desconocido")
                    context = f"{mode_name} | {map_name}"
                    
                    async with aiosqlite.connect("rivalsconnect.db") as database:
                        await database.execute('UPDATE users SET is_playing = 1, match_context = ? WHERE discord_id = ?', (context, discord_id))
                        await database.commit()
                        
                    from src.cogs.live_panel import update_live_panel
                    await update_live_panel(bot, guild_id)
                    
                # Procesar ELO y Fin de Partida
                elif event_name == "match_end":
                    async with aiosqlite.connect("rivalsconnect.db") as database:
                        await database.execute('UPDATE users SET is_playing = 0 WHERE discord_id = ?', (discord_id,))
                        await database.commit()
                        
                    from src.cogs.live_panel import update_live_panel
                    await update_live_panel(bot, guild_id)
                    
                    stats = data.get("stats", {})
                    roster = data.get("roster", {})
                    
                    current_elo = 0
                    local_uid = None
                    
                    for k, v in roster.items():
                        if v.get("is_local"):
                            current_elo = v.get("elo_score", v.get("ranking_score", v.get("rank_score", v.get("mmr", 0))))
                            local_uid = v.get("uid")
                            break
                            
                    game_type = data.get("game_type", "")
                    has_bans = bool(data.get("bans"))
                    is_competitive = (game_type.lower() == "competitive") or has_bans

                    if local_uid:
                        async with aiosqlite.connect(db.DB_PATH) as _db:
                            await _db.execute('UPDATE users SET in_game_uid = ? WHERE discord_id = ? AND (in_game_uid IS NULL OR in_game_uid = "")', (local_uid, discord_id))
                            await _db.commit()

                    if current_elo > 0 and is_competitive:
                        old_elo = await db.update_user_elo(discord_id, current_elo, local_uid)
                        if old_elo > 0:
                            elo_change = current_elo - old_elo
                            
                        from src.cogs.leaderboard import update_leaderboard_panel
                        await update_leaderboard_panel(bot, guild_id)
                        
                    # Guardar partida en la BD para el historial
                    local_k = local_d = local_a = 0
                    local_hero = "???"
                    for k, v in roster.items():
                        if v.get("is_local"):
                            local_k = v.get("kills", 0)
                            local_d = v.get("deaths", 0)
                            local_a = v.get("assists", 0)
                            local_hero = v.get("character_name", "???")
                            break
                            
                    damage = stats.get("damage_dealt", 0)
                    heal = stats.get("total_heal", 0)
                    outcome = data.get("outcome", "Desconocido")
                    mode = data.get("mode", "Desconocido")
                    map_name = data.get("map", "Desconocido")
                    roster_json = json.dumps(roster) if roster else None
                    
                    await db.add_match(discord_id, elo_change, local_k, local_d, local_a, damage, heal, outcome, local_hero, mode, map_name, roster_json)
                
                # Obtener diccionario de Lords global
                lords_dict = await db.get_all_lords_by_uid()
                
                # Obtener idioma del usuario
                lang = await db.get_user_language(discord_id)
                
                # Crear embed estructurado
                embed = create_embed_from_data(data, discord_name, discord_avatar, elo_change, lords_dict, lang)
                
                if embed:
                    user_key = f"user_{discord_id}"
                    
                    if event_name == "match_start":
                        # Nueva partida: Enviamos un mensaje nuevo y lo guardamos
                        msg = await channel.send(embed=embed)
                        active_messages[user_key] = msg
                    elif event_name in ["match_playing", "match_end", "match_update_lobby"]:
                        # Partida iniciada o terminada: Editamos el mensaje existente
                        msg = active_messages.get(user_key)
                        if msg:
                            try:
                                await msg.edit(embed=embed)
                            except discord.NotFound:
                                # Si el usuario borró el mensaje manualmente, enviamos uno nuevo
                                msg = await channel.send(embed=embed)
                                active_messages[user_key] = msg
                        else:
                            # Fallback por si el bot se reinició en medio de la partida
                            msg = await channel.send(embed=embed)
                            active_messages[user_key] = msg
                            
                        # Si terminó la partida, lo borramos de la memoria activa
                        if event_name == "match_end":
                            active_messages.pop(user_key, None)

            else:
                logger.warning(f"No se encontró el canal con ID {channel_id} en caché.")
        else:
            logger.warning("Datos recibidos, pero no hay un canal vinculado.")

        return web.Response(headers=headers, status=200)
    except Exception as e:
        logger.error(f"Error en el servidor web: {e}")
        return web.Response(text="Bad Request", status=400, headers=headers)

async def handle_user_stats(request):
    """Endpoint para que Overwolf consulte el perfil completo y estadísticas del usuario."""
    headers = {"Access-Control-Allow-Origin": "*"}
    try:
        data = await request.json()
        link_code = data.get("link_code")
        if not link_code:
            return web.json_response({"success": False, "error": "Missing link_code"}, headers=headers, status=400)
            
        user = await db.get_user_by_code(link_code)
        if not user:
            return web.json_response({"success": False, "error": "User not found"}, headers=headers, status=404)
            
        discord_id = user[0]
        user_data = await db.get_user(discord_id)
        if not user_data:
            return web.json_response({"success": False, "error": "User data not found"}, headers=headers, status=404)
            
        elo_score = user_data[6] or 0
        in_game_uid = user_data[7]
        rank_key = await db.get_user_rank(elo_score)
        user_lords = await db.get_user_lords(discord_id)
        top_chars = await db.get_top_characters(discord_id, limit=5)
        role_stats = await db.get_top_roles(discord_id)
        recent_matches = await db.get_recent_matches(discord_id, limit=100)
        
        matches_formatted = []
        for m in recent_matches:
            roster_data = {}
            if len(m) > 11 and m[11]:
                try:
                    roster_data = json.loads(m[11])
                except Exception:
                    roster_data = {}
            matches_formatted.append({
                "elo_change": m[0],
                "kills": m[1],
                "deaths": m[2],
                "assists": m[3],
                "damage": m[4],
                "heal": m[5],
                "outcome": m[6],
                "character_name": m[7],
                "mode": m[8],
                "map_name": m[9],
                "match_date": m[10],
                "roster": roster_data
            })
            
        return web.json_response({
            "success": True,
            "discord_id": discord_id,
            "discord_name": user_data[1],
            "discord_avatar": user_data[2],
            "elo_score": elo_score,
            "rank_key": rank_key,
            "in_game_uid": in_game_uid,
            "lords": user_lords,
            "top_characters": top_chars,
            "role_stats": role_stats,
            "recent_matches": matches_formatted
        }, headers=headers)
    except Exception as e:
        logger.error(f"Error en /api/user-stats: {e}")
        return web.json_response({"success": False, "error": str(e)}, headers=headers, status=500)

async def handle_history(request):
    """Endpoint para que Overwolf consulte el historial de partidas almacenado en la nube."""
    headers = {"Access-Control-Allow-Origin": "*"}
    try:
        data = await request.json()
        link_code = data.get("link_code")
        limit = data.get("limit", 20)
        
        user = await db.get_user_by_code(link_code)
        if not user:
            return web.json_response({"success": False, "error": "Invalid link_code"}, headers=headers, status=401)
            
        discord_id = user[0]
        recent_matches = await db.get_recent_matches(discord_id, limit=limit)
        
        matches_formatted = []
        for m in recent_matches:
            roster_data = {}
            if len(m) > 11 and m[11]:
                try:
                    roster_data = json.loads(m[11])
                except Exception:
                    roster_data = {}
            matches_formatted.append({
                "elo_change": m[0],
                "kills": m[1],
                "deaths": m[2],
                "assists": m[3],
                "damage": m[4],
                "heal": m[5],
                "outcome": m[6],
                "character_name": m[7],
                "mode": m[8],
                "map_name": m[9],
                "match_date": m[10],
                "roster": roster_data
            })
            
        return web.json_response({"success": True, "matches": matches_formatted}, headers=headers)
    except Exception as e:
        logger.error(f"Error en /api/history: {e}")
        return web.json_response({"success": False, "error": str(e)}, headers=headers, status=500)

async def start_web_server(bot, port: int):
    """Inicia el servidor HTTP de aiohttp."""
    app = web.Application()
    app['bot'] = bot
    
    app.router.add_route('OPTIONS', '/api/verify', handle_options)
    app.router.add_post('/api/verify', handle_verify)
    
    app.router.add_options('/api/overwolf-events', handle_options)
    app.router.add_post('/api/overwolf-events', handle_overwolf_events)
    
    app.router.add_options('/api/user-stats', handle_options)
    app.router.add_post('/api/user-stats', handle_user_stats)
    
    app.router.add_options('/api/history', handle_options)
    app.router.add_post('/api/history', handle_history)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()
    print(f"🌍 Servidor web local para Overwolf escuchando en http://localhost:{port}/api/overwolf-events")

