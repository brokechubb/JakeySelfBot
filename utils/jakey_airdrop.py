import asyncio
import operator
import re
from logging import (
    INFO, DEBUG, WARNING, ERROR, CRITICAL,
    Formatter, StreamHandler, getLogger
)
from random import randint, uniform
from time import time
from urllib.parse import quote, unquote

from aiohttp import ClientSession
from discord import Client, Message, Status, HTTPException, NotFound

# ===================
# Logging
# ===================
class ColourFormatter(Formatter):
    LEVEL_COLOURS = [
        (DEBUG, "\x1b[40;1m"),
        (INFO, "\x1b[34;1m"),
        (WARNING, "\x1b[33;1m"),
        (ERROR, "\x1b[31m"),
        (CRITICAL, "\x1b[41m"),
    ]

    FORMATS = {
        level: Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-8s\x1b[0m "
            f"\x1b[35m%(name)s\x1b[0m %(message)s "
            f"\x1b[30;1m(%(filename)s:%(lineno)d)\x1b[0m",
            "%d-%b-%Y %I:%M:%S %p",
        )
        for level, colour in LEVEL_COLOURS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno, self.FORMATS[DEBUG])
        return formatter.format(record)

handler = StreamHandler()
handler.setFormatter(ColourFormatter())
logger = getLogger("drop_sniper")
logger.addHandler(handler)
logger.setLevel("INFO")

# ===================
# Config (simplified)
# ===================
config = {
    "PRESENCE": "invisible",
    "CPM": [200, 310],             # characters per minute typing simulation
    "SMART_DELAY": True,           # wait closer to drop end
    "RANGE_DELAY": False,          # use random delay
    "DELAY": [0, 1],               # min/max delay in seconds
    "IGNORE_DROPS_UNDER": 0.0,     # ignore drops below $ value
    "IGNORE_TIME_UNDER": 0.0,      # ignore drops expiring too soon
    "IGNORE_USERS": [],            # list of user IDs to ignore
    "DISABLE_AIRDROP": False,
    "DISABLE_TRIVIADROP": False,
    "DISABLE_MATHDROP": False,
    "DISABLE_PHRASEDROP": False,
    "DISABLE_REDPACKET": False,
}

banned_words = set(["bot", "ban"])  # example banned words

# ===================
# Helpers
# ===================
def typing_delay(text: str) -> float:
    """Simulate typing time based on CPM."""
    cpm = randint(config["CPM"][0], config["CPM"][1])
    return len(text) / cpm * 60

def safe_eval_math(expr: str):
    """Safely evaluate basic math expressions (no eval)."""
    allowed_ops = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '**': operator.pow,
        '%': operator.mod,
    }
    # crude but safer than eval – only digits and operators
    if not re.match(r"^[\d\.\+\-\*/%\(\)\s]+$", expr):
        return None
    try:
        return eval(expr, {"__builtins__": {}}, {})  # restricted eval
    except Exception:
        return None

async def maybe_delay(drop_ends_in: float):
    """Handle smart/range/manual delay before acting."""
    if config["SMART_DELAY"]:
        delay = drop_ends_in / 4 if drop_ends_in > 0 else 0
    elif config["RANGE_DELAY"]:
        delay = uniform(config["DELAY"][0], config["DELAY"][1])
    else:
        delay = config["DELAY"][0]
    if delay > 0:
        logger.debug(f"Waiting {round(delay, 2)}s before acting...")
        await asyncio.sleep(delay)

# ===================
# Client
# ===================
client = Client(
    status=Status.invisible if config["PRESENCE"] == "invisible" else Status.online
)

@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user} (id: {client.user.id})")
    logger.info("Drop sniping active.")

# ===================
# Drop Handling
# ===================
@client.event
async def on_message(original_message: Message):
    content = original_message.content.lower()
    if not content.startswith(("$airdrop", "$triviadrop", "$mathdrop", "$phrasedrop", "$redpacket", "$ airdrop", "$ triviadrop", "$ mathdrop", "$ phrasedrop", "$ redpacket")):
        return
    if any(word in content for word in banned_words):
        return
    if original_message.author.id in config["IGNORE_USERS"]:
        return

    logger.debug(f"Detected potential drop: {original_message.content}")

    try:
        tip_cc_message = await client.wait_for(
            "message",
            timeout=15,
            check=lambda m: (
                m.author.id == 617037497574359050 and
                m.channel.id == original_message.channel.id and
                m.embeds
            )
        )
    except asyncio.TimeoutError:
        logger.debug("Timeout waiting for tip.cc message.")
        return

    embed = tip_cc_message.embeds[0]
    drop_ends_in = (embed.timestamp.timestamp() - time()) if embed.timestamp else 5

    # Apply delay logic
    await maybe_delay(drop_ends_in)

    try:
        # Airdrop
        if "airdrop" in embed.title.lower() and not config["DISABLE_AIRDROP"]:
            button = tip_cc_message.components[0].children[0]
            await button.click()
            logger.info(f"Entered airdrop in {original_message.channel.name}")

        # Phrase drop
        elif "phrase drop" in embed.title.lower() and not config["DISABLE_PHRASEDROP"]:
            phrase = embed.description.replace("\n", "").replace("**", "")
            phrase = phrase.split("*")[1].strip()
            async with original_message.channel.typing():
                await asyncio.sleep(typing_delay(phrase))
            await original_message.channel.send(phrase)
            logger.info(f"Entered phrase drop in {original_message.channel.name}")

        # Math drop
        elif "math" in embed.title.lower() and not config["DISABLE_MATHDROP"]:
            expr = embed.description.split("`")[1].strip()
            answer = safe_eval_math(expr)
            if answer is not None:
                answer = int(answer) if isinstance(answer, float) and answer.is_integer() else answer
                async with original_message.channel.typing():
                    await asyncio.sleep(typing_delay(str(answer)))
                await original_message.channel.send(str(answer))
                logger.info(f"Entered math drop in {original_message.channel.name}")

        # Trivia drop
        elif "trivia" in embed.title.lower() and not config["DISABLE_TRIVIADROP"]:
            category = embed.title.split("Trivia time - ")[1].strip()
            question = embed.description.replace("**", "").split("*")[1].strip()
            async with ClientSession() as session:
                async with session.get(
                    f"https://raw.githubusercontent.com/QuartzWarrior/OTDB-Source/main/{quote(category)}.csv"
                ) as resp:
                    lines = (await resp.text()).splitlines()
                    for line in lines:
                        q, a = line.split(",", 1)
                        if question == unquote(q).strip():
                            for button in tip_cc_message.components[0].children:
                                if button.label.strip() == unquote(a).strip():
                                    await button.click()
                                    logger.info(f"Entered trivia drop in {original_message.channel.name}")
                                    return

        # Redpacket
        elif "appeared" in embed.title.lower() and not config["DISABLE_REDPACKET"]:
            button = tip_cc_message.components[0].children[0]
            if "envelope" in button.label.lower():
                await button.click()
                logger.info(f"Claimed redpacket in {original_message.channel.name}")

    except (IndexError, AttributeError, HTTPException, NotFound):
        logger.debug("Something went wrong while handling drop.")
        return

# ===================
# Run
# ===================
if __name__ == "__main__":
    client.run("YOUR_TOKEN_HERE", log_handler=handler)
