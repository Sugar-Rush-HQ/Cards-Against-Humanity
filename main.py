import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import uuid
import os
import json
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# --- 1. CONFIGURATION ---

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
TURN_TIMEOUT = 180  # 3 Minutes per turn
QUEUE_TIMEOUT = 180 # 3 Minutes to wait in queue before bots start
MAX_PLAYERS = 6     # Players per game

if not TOKEN:
    print("WARNING: DISCORD_TOKEN is missing. Set it in Render Environment Variables.")

# --- 2. LOAD DATA (SPLIT INTO MODES) ---
def load_cards():
    if not os.path.exists("cards.json"):
        print("ERROR: cards.json not found! Using fallback defaults.")
        return {"sfw": {"black_cards": ["Why?"], "white_cards": ["Because."]}, "nsfw": {"black_cards": ["Sex?"], "white_cards": ["Yes."]}}
    
    with open("cards.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        return data

CARD_DATA = load_cards()
print(f"Cards Loaded. Modes available: {list(CARD_DATA.keys())}")

# --- 3. RENDER KEEPALIVE SERVER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Global CAH Bot is Running!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# --- 4. GAME CLASSES ---

class Player:
    def __init__(self, user, channel):
        self.user = user 
        self.channel = channel 
        self.hand = []
        self.score = 0
        self.selected_card = None
        self.is_system = False

    def draw_to_7(self, white_deck):
        """Draws from the specific deck for the current game mode."""
        while len(self.hand) < 7:
            self.hand.append(random.choice(white_deck))

class SystemPlayer(Player):
    def __init__(self, index):
        super().__init__(None, None)
        self.name = f"System Bot {index+1}"
        self.is_system = True
        self.id = index 

    def pick_card(self, white_deck):
        self.draw_to_7(white_deck)
        self.selected_card = random.choice(self.hand)
        self.hand.remove(self.selected_card)
        return self.selected_card

    def judge_winner(self, submissions):
        return random.choice(submissions)

class Game:
    def __init__(self, game_id, mode):
        self.id = game_id
        self.mode = mode # 'sfw' or 'nsfw'
        self.players = []
        self.czar_index = 0
        self.active = False
        self.current_black_card = None
        
        # Select the correct decks based on mode
        self.black_deck = CARD_DATA[mode]["black_cards"]
        self.white_deck = CARD_DATA[mode]["white_cards"]

    async def broadcast(self, message=None, embed=None, view=None):
        for p in self.players:
            if not p.is_system:
                try:
                    await p.channel.send(content=message, embed=embed, view=view)
                except Exception as e:
                    print(f"Error broadcasting: {e}")

    async def start_game(self):
        self.active = True
        
        needed = MAX_PLAYERS - len(self.players)
        if needed > 0:
            for i in range(needed):
                sys_p = SystemPlayer(i)
                sys_p.draw_to_7(self.white_deck)
                self.players.append(sys_p)
            await self.broadcast(f"**{self.mode.upper()} Game Started!** Added {needed} Bots.")
        else:
            await self.broadcast(f"**{self.mode.upper()} Game Started!** Full table.")
        
        await self.game_loop()

    async def game_loop(self):
        for round_num in range(1, 6): 
            czar = self.players[self.czar_index]
            self.current_black_card = random.choice(self.black_deck)
            
            # Reset & Draw
            for p in self.players:
                p.selected_card = None
                p.draw_to_7(self.white_deck)

            # Announce
            czar_name = czar.name if czar.is_system else czar.user.display_name
            color = 0xe91e63 if self.mode == "nsfw" else 0x2ecc71
            
            embed = discord.Embed(
                title=f"Round {round_num} ({self.mode.upper()})", 
                description=f"**Black Card:** {self.current_black_card}", 
                color=color
            )
            embed.add_field(name="The Czar", value=czar_name)
            await self.broadcast(embed=embed)

            # Bots pick
            for p in self.players:
                if p.is_system and p != czar:
                    p.pick_card(self.white_deck)

            # Humans pick
            view = HandSelectionView(self.players, czar, self.current_black_card)
            for p in self.players:
                if not p.is_system and p != czar:
                    await p.channel.send("It is your turn to pick!", view=view)
                elif not p.is_system and p == czar:
                    await p.channel.send("You are the Czar! Waiting for players...", delete_after=10)

            # Timer
            timeout_occurred = await view.wait_for_everyone_or_timeout(TURN_TIMEOUT)
            if timeout_occurred:
                await self.broadcast("⏳ **Time is up!** Moving to judging...")
            
            # Judging
            submitted_players = [p for p in self.players if p.selected_card is not None and p != czar]
            
            if not submitted_players:
                await self.broadcast("No cards were submitted! Skipping round.")
                self.rotate_czar()
                continue

            random.shuffle(submitted_players) 
            display_text = "**Submissions:**\n"
            for i, p in enumerate(submitted_players):
                display_text += f"**{i+1}.** {p.selected_card}\n"
            
            await self.broadcast(display_text)

            winner = None
            if czar.is_system:
                await self.broadcast("The System Czar is thinking...")
                await asyncio.sleep(2) 
                winner = czar.judge_winner(submitted_players)
            else:
                czar_view = CzarJudgingView(submitted_players, czar.user.id)
                await czar.channel.send("**Judge the winner!**", view=czar_view)
                timed_out = await czar_view.wait() 
                if timed_out:
                    winner = random.choice(submitted_players)
                    await self.broadcast("Czar fell asleep! Random winner chosen.")
                else:
                    winner = czar_view.winner

            if winner:
                winner.score += 1
                winner_name = winner.name if winner.is_system else winner.user.display_name
                await self.broadcast(f"🏆 **{winner_name}** wins! ({winner.selected_card})")

            self.rotate_czar()
            await asyncio.sleep(4)

        await self.show_scoreboard()

    def rotate_czar(self):
        self.czar_index = (self.czar_index + 1) % len(self.players)

    async def show_scoreboard(self):
        text = "**Game Over! Final Scores:**\n"
        sorted_players = sorted(self.players, key=lambda x: x.score, reverse=True)
        for p in sorted_players:
            name = p.name if p.is_system else p.user.display_name
            text += f"{name}: {p.score}\n"
        await self.broadcast(text)

# --- 5. VIEWS (UI) ---

class HandSelectionView(discord.ui.View):
    def __init__(self, players, czar, black_card_text):
        super().__init__(timeout=None)
        self.players = players
        self.czar = czar
        self.black_card_text = black_card_text
        self.submitted_count = 0
        self.needed_count = len([p for p in players if not p.is_system and p != czar])
        self.done_event = asyncio.Event()

    async def wait_for_everyone_or_timeout(self, duration):
        try:
            await asyncio.wait_for(self.done_event.wait(), timeout=duration)
            return False 
        except asyncio.TimeoutError:
            return True 

    @discord.ui.button(label="Play Card", style=discord.ButtonStyle.primary, emoji="🃏")
    async def open_hand(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = next((p for p in self.players if p.user and p.user.id == interaction.user.id), None)
        
        if not player:
            return await interaction.response.send_message("Not in this game.", ephemeral=True)
        if player == self.czar:
            return await interaction.response.send_message("You are the Czar!", ephemeral=True)
        if player.selected_card:
            return await interaction.response.send_message("Already picked!", ephemeral=True)

        options = [
            discord.SelectOption(label=card[:100], value=card) for card in player.hand
        ]
        
        select = discord.ui.Select(placeholder="Pick a card...", options=options)

        async def select_callback(inter: discord.Interaction):
            choice = select.values[0]
            player.selected_card = choice
            player.hand.remove(choice)
            self.submitted_count += 1
            await inter.response.send_message(f"Played: **{choice}**", ephemeral=True)
            if self.submitted_count >= self.needed_count:
                self.done_event.set()

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message(f"**Prompt:** {self.black_card_text}", view=view, ephemeral=True)

class CzarJudgingView(discord.ui.View):
    def __init__(self, submitted_players, czar_id):
        super().__init__(timeout=90)
        self.czar_id = czar_id
        self.winner = None
        for index, p in enumerate(submitted_players):
            btn = discord.ui.Button(label=f"Card {index+1}", style=discord.ButtonStyle.secondary, custom_id=str(index))
            btn.callback = self.create_callback(p)
            self.add_item(btn)

    def create_callback(self, player):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.czar_id:
                return await interaction.response.send_message("Not Czar!", ephemeral=True)
            self.winner = player
            await interaction.response.send_message(f"Winner decided!", ephemeral=True)
            self.stop()
        return callback

# --- 6. MAIN BOT CLASS ---

class GlobalCAHBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        # We now have TWO queues
        self.queue_sfw = []
        self.queue_nsfw = []
        self.active_games = {}
        self.timer_sfw = None
        self.timer_nsfw = None

    async def on_ready(self):
        print(f"Logged in as {self.user}!")
        await self.tree.sync()

    async def start_queue_timer(self, mode):
        """Generic timer for either queue."""
        print(f"{mode.upper()} Queue timer started...")
        await asyncio.sleep(QUEUE_TIMEOUT)
        
        queue = self.queue_sfw if mode == "sfw" else self.queue_nsfw
        
        if queue:
            print(f"{mode} timeout reached! Force starting.")
            
            batch_size = min(len(queue), MAX_PLAYERS)
            current_players = queue[:batch_size]
            
            # Remove from correct queue list
            if mode == "sfw":
                self.queue_sfw = self.queue_sfw[batch_size:]
                self.timer_sfw = None
            else:
                self.queue_nsfw = self.queue_nsfw[batch_size:]
                self.timer_nsfw = None

            game_id = str(uuid.uuid4())
            new_game = Game(game_id, mode)
            new_game.players = current_players
            self.active_games[game_id] = new_game
            
            for p in new_game.players:
                try:
                    await p.channel.send(f"⏰ **Wait limit reached.** Starting {mode.upper()} game with bots!")
                except:
                    pass
            
            asyncio.create_task(new_game.start_game())

bot = GlobalCAHBot()

@bot.tree.command(name="join_global", description="Join a Global Game")
@app_commands.describe(mode="Choose Game Mode")
@app_commands.choices(mode=[
    app_commands.Choice(name="SFW (Family Friendly)", value="sfw"),
    app_commands.Choice(name="NSFW (Adults Only)", value="nsfw")
])
async def join_global(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    selected_mode = mode.value
    user = interaction.user
    
    # SAFETY CHECK
    if selected_mode == "nsfw" and not interaction.channel.is_nsfw():
        return await interaction.response.send_message("🔞 **Blocked:** NSFW mode requires an Age-Restricted channel.", ephemeral=True)

    # 1. Backfill (Join existing game of same mode)
    for game in bot.active_games.values():
        if any(p.user and p.user.id == user.id for p in game.players):
             return await interaction.response.send_message("You are already playing!", ephemeral=True)
        
        # Only backfill if modes match
        if game.mode == selected_mode:
            for index, player in enumerate(game.players):
                if player.is_system:
                    new_player = Player(user, interaction.channel)
                    new_player.hand = player.hand
                    new_player.score = player.score
                    new_player.selected_card = player.selected_card
                    game.players[index] = new_player
                    
                    await interaction.response.send_message(f"Replaced a bot in an active {selected_mode.upper()} game!", ephemeral=True)
                    await game.broadcast(f"♻️ **{user.display_name}** joined the game!")
                    return 

    # 2. Add to specific Queue
    target_queue = bot.queue_sfw if selected_mode == "sfw" else bot.queue_nsfw
    
    if any(p.user.id == user.id for p in bot.queue_sfw + bot.queue_nsfw):
        return await interaction.response.send_message("You are already in a queue.", ephemeral=True)

    new_player = Player(user, interaction.channel)
    target_queue.append(new_player)
    
    q_len = len(target_queue)
    await interaction.response.send_message(f"Joined {selected_mode.upper()} Queue! ({q_len}/{MAX_PLAYERS}).", ephemeral=False)

    # 3. Timer Logic
    if q_len == 1:
        if selected_mode == "sfw":
            bot.timer_sfw = asyncio.create_task(bot.start_queue_timer("sfw"))
        else:
            bot.timer_nsfw = asyncio.create_task(bot.start_queue_timer("nsfw"))

    # 4. Start Game Logic
    if q_len >= MAX_PLAYERS:
        # Cancel specific timer
        if selected_mode == "sfw" and bot.timer_sfw:
            bot.timer_sfw.cancel()
            bot.timer_sfw = None
        elif selected_mode == "nsfw" and bot.timer_nsfw:
            bot.timer_nsfw.cancel()
            bot.timer_nsfw = None
        
        game_id = str(uuid.uuid4())
        new_game = Game(game_id, selected_mode)
        
        # Slice queue
        if selected_mode == "sfw":
            new_game.players = bot.queue_sfw[:MAX_PLAYERS]
            bot.queue_sfw = bot.queue_sfw[MAX_PLAYERS:]
        else:
            new_game.players = bot.queue_nsfw[:MAX_PLAYERS]
            bot.queue_nsfw = bot.queue_nsfw[MAX_PLAYERS:]
        
        bot.active_games[game_id] = new_game
        asyncio.create_task(new_game.start_game())

@bot.tree.command(name="leave_queue", description="Leave the matchmaking queue")
async def leave_queue(interaction: discord.Interaction):
    # Remove from both queues just in case
    bot.queue_sfw = [p for p in bot.queue_sfw if p.user.id != interaction.user.id]
    bot.queue_nsfw = [p for p in bot.queue_nsfw if p.user.id != interaction.user.id]
    await interaction.response.send_message("You left the queue.", ephemeral=True)

if __name__ == "__main__":
    if TOKEN:
        keep_alive()
        bot.run(TOKEN)
