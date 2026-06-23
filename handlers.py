"""
All Telegram bot handlers. Mak Cik Fatimah lives here. 🧕
"""

import logging
import random
import re
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

from data import HalalData

logger = logging.getLogger(__name__)

MODE, CUISINE, AREA, HALAL_TYPE = range(4)


# ═══════════════════════════════════════════════════════════════════════════════
# MAK CIK FATIMAH'S VOICE 🧕
# ═══════════════════════════════════════════════════════════════════════════════

def _greet() -> str:
    return random.choice([
        "Wah hello there! Welcome! 🧕",
        "Eh come come, sit down sit down! 🧕",
        "Assalamualaikum! Peace be upon you! 🧕",
        "Hi there! Mak Cik is here to help! 🧕",
        "Alhamdulillah, you found Mak Cik! 🧕",
        "Eh you came! Hungry already ah? 🧕",
    ])


def _pick_exclamation() -> str:
    return random.choice([
        "Wah lau, this one confirm very good one!",
        "Masya-Allah, this place damn shiok weh! 🔥",
        "Mak Cik thinks this one is really the best!",
        "Alhamdulillah, been wanting to recommend this for a while!",
        "Takeaway also sedap, eat there also shiok!",
        "One bite only, confirm you'll be hooked!",
        "Mak Cik gives this 5 stars ⭐⭐⭐⭐⭐",
        "Very good one lah, Mak Cik won't bluff you!",
        "You try this, come back thank Mak Cik later okay! 😂",
        "This one everyday also can eat, never get sick of it!",
    ])


def _no_result_msg() -> str:
    return random.choice([
        "Alamak, Mak Cik searched already but cannot find anything 🥲\nTry different options? Or just /random lah!",
        "Aiyoh… Mak Cik looked everywhere but nothing matches leh 😔\nMaybe try different preferences?",
        "Hmm, nothing in Mak Cik's list matches that 😤\nTry /random and see what comes up!",
    ])


def _bye() -> str:
    return random.choice([
        "Okay enjoy your meal! Say Bismillah before eating! 😊",
        "Don't forget to say Bismillah before you eat! Take care! 🧕✨",
        "Enjoy your food! If not enough, order more lah! 😋",
        "Eat well, stay full — cannot think properly when hungry! 🧕💪",
        "After makan, don't forget your prayers okay! 🕌",
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# ADDRESS CLEANUP & FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def _esc(text: str) -> str:
    """Escape only the characters Telegram Markdown v1 actually interprets.
    # does NOT need escaping — it's only special at the start of a line."""
    return (
        text
        .replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("`", "\\`")
        .replace("[", "\\[")
    )


def _clean_address(address: str, postal_code: str) -> str:
    """
    Clean up raw address for display.
    - Strips trailing postal code (shown separately)
    - Removes redundant stall/unit suffixes like ', Stall 6' ', MR1'
    - Collapses multiple spaces
    - Keeps #unit numbers (important for finding the stall)
    """
    addr = address

    # Remove trailing postal code if we have it separately
    if postal_code and postal_code in addr:
        addr = addr.replace(postal_code, "")

    # Remove redundant ", Stall X" / ", MR X" suffixes
    # (the #unit number already tells you where it is)
    addr = re.sub(r",?\s*(?:Stall|MR|Unit|stall|mr|unit)\s*\d+\s*$", "", addr)

    # Clean up trailing punctuation and whitespace
    addr = addr.rstrip(" ,.")

    # Collapse multiple spaces
    addr = re.sub(r"\s{2,}", " ", addr).strip()

    return addr


def _format_establishment(e, distance_km: Optional[float] = None) -> str:
    """Pretty-print one establishment — clean and readable."""
    lines = []

    # Name (bold, escaped)
    lines.append(f"*{_esc(e.name)}*")

    # Address (cleaned up)
    clean_addr = _clean_address(e.address, e.postal_code)
    lines.append(f"📍 {_esc(clean_addr)}")

    # Halal cert + postal code on one line
    cert = e.halal_cert_display
    if e.postal_code:
        lines.append(f"📮 {e.postal_code} · {cert}")
    else:
        lines.append(cert)

    # Distance
    if distance_km is not None:
        if distance_km < 0.1:
            dist_str = f"{distance_km * 1000:.0f}m away"
        elif distance_km < 0.5:
            dist_str = f"{distance_km:.1f}km — can walk one!"
        else:
            dist_str = f"{distance_km:.1f}km away"
        lines.append(f"🚶 {dist_str}")

    # Google Maps link
    if e.has_coords:
        maps_url = f"https://www.google.com/maps/search/?api=1&query={e.latitude},{e.longitude}"
        lines.append(f"🗺 [Open in Maps]({maps_url})")

    return "\n".join(lines)


def _get_data(context: ContextTypes.DEFAULT_TYPE) -> HalalData:
    return context.bot_data["halal_data"]


# ═══════════════════════════════════════════════════════════════════════════════
# /START & /HELP
# ═══════════════════════════════════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"{_greet()}\n\n"
        "I'm *Mak Cik Fatimah* 🧕 — your friendly neighbourhood halal food finder in *Singapore!* 🇸🇬\n\n"
        "Here's what I can do:\n\n"
        "🎲 `/random` — Let Mak Cik pick for you! Freestyle or by preference, up to you.\n"
        "📍 *Send your location* — I'll find halal food nearby!\n"
        "🔍 *Just type what you want* — e.g. \"nasi lemak\", \"briyani\", \"burger\"… I'll search!\n"
        "📏 `/nearby 3` — Set search radius in km (default is 2km)\n"
        "📊 `/stats` — See how much data Mak Cik has\n"
        "❓ `/help` — Show this menu again\n\n"
        "So… hungry already or not? 😋"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)


# ═══════════════════════════════════════════════════════════════════════════════
# /RANDOM CONVERSATION
# ═══════════════════════════════════════════════════════════════════════════════

async def random_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Surprise me! Anything also can", callback_data="mode_freestyle"),
            InlineKeyboardButton("🤔 I have a specific craving lah", callback_data="mode_guided"),
        ]
    ])
    await update.message.reply_text(
        f"{_greet()}\n\n"
        "You want Mak Cik to help pick your food ah? Best! 🎲\n\n"
        "You want a full surprise, or got something specific in mind? 🤔",
        reply_markup=keyboard,
    )
    return MODE


async def handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data

    if choice == "mode_freestyle":
        data = _get_data(context)
        results = data.get_random(1)
        if not results:
            await query.edit_message_text(_no_result_msg())
            return ConversationHandler.END

        e = results[0]
        text = (
            f"🎉 *Tadaaa~ Mak Cik's Pick!*\n\n"
            f"{_pick_exclamation()}\n\n"
            f"{_format_establishment(e)}\n\n"
            "Not happy? Press again lah! 😂"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎲 Give me another one!", callback_data="another_random"),
                InlineKeyboardButton("👌 This is good, thank you!", callback_data="another_done"),
            ]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        context.user_data["last_filters"] = None
        return HALAL_TYPE

    else:  # guided
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🍛 Malay", callback_data="cuisine_malay"),
                InlineKeyboardButton("🫓 Indian / Mamak", callback_data="cuisine_indian"),
            ],
            [
                InlineKeyboardButton("🥡 Chinese (Halal)", callback_data="cuisine_chinese"),
                InlineKeyboardButton("🍔 Western", callback_data="cuisine_western"),
            ],
            [
                InlineKeyboardButton("🥙 Middle Eastern", callback_data="cuisine_middle_eastern"),
                InlineKeyboardButton("🍣 Japanese", callback_data="cuisine_japanese"),
            ],
            [
                InlineKeyboardButton("🌶️ Thai", callback_data="cuisine_thai"),
                InlineKeyboardButton("🍲 Indonesian", callback_data="cuisine_indonesian"),
            ],
            [
                InlineKeyboardButton("🤷 Anything also can!", callback_data="cuisine_any"),
            ],
        ])
        await query.edit_message_text(
            "Okay okay, Mak Cik help you choose! 😊\n\n"
            "First — what type of food you feel like? 🍽️\n"
            "Don't be shy, just pick!",
            reply_markup=keyboard,
        )
        return CUISINE


async def handle_cuisine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cuisine = query.data.replace("cuisine_", "")
    context.user_data["cuisine"] = cuisine
    cuisine_display = cuisine.replace("_", " ").title()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏙️ Central", callback_data="area_central"),
            InlineKeyboardButton("🌊 East", callback_data="area_east"),
        ],
        [
            InlineKeyboardButton("🌅 West", callback_data="area_west"),
            InlineKeyboardButton("🌲 North", callback_data="area_north"),
        ],
        [
            InlineKeyboardButton("🏘️ North-East", callback_data="area_northeast"),
            InlineKeyboardButton("🤷 Any area also can!", callback_data="area_any"),
        ],
    ])

    msg = f"Ooh {cuisine_display}! Good choice lah! 👍\n\n" if cuisine != "any" else \
          "Wah, anything also can eat! Very open minded, Mak Cik like! 👍\n\n"
    msg += (
        "Next — which area are you in, or where you want to eat? 🗺️\n"
        "If you don't mind the location, just pick any area!"
    )

    await query.edit_message_text(msg, reply_markup=keyboard)
    return AREA


async def handle_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    area = query.data.replace("area_", "")
    context.user_data["area"] = area

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("MUIS Certified only (safer)", callback_data="halal_muis"),
            InlineKeyboardButton("Muslim-owned is fine too", callback_data="halal_all"),
        ],
    ])
    await query.edit_message_text(
        "Got it! 📍\n\n"
        "Last question — \n\n"
        "Do you want *MUIS certified* places only (officially certified by Singapore's Islamic authority), "
        "or Muslim-owned is also okay? 🤔\n\n"
        "Some Muslim-owned places don't have MUIS cert but only sell halal food. "
        "Up to you lah, Mak Cik will follow!",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return HALAL_TYPE


async def handle_halal_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    halal_choice = query.data.replace("halal_", "")
    muis_only = halal_choice == "muis"

    cuisine = context.user_data.get("cuisine", "any")
    area = context.user_data.get("area", "any")

    data = _get_data(context)
    pool = data.query(cuisine=cuisine, area=area, muis_only=muis_only)

    if not pool:
        await query.edit_message_text(_no_result_msg())
        return ConversationHandler.END

    count = min(3, len(pool))
    picks = random.sample(pool, count)

    header = "🎉 *Mak Cik found a place for you!*\n" if count == 1 else \
             f"🎉 *Mak Cik found {count} places for you!*\n"

    lines = [header, _pick_exclamation(), ""]

    for i, e in enumerate(picks, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        lines.append(f"{medal} {_format_establishment(e)}")
        lines.append("")  # blank line between entries

    lines.append(
        "Not happy? Press *Give me another one!* Or share your location, "
        "Mak Cik will find what's nearby! 📍"
    )

    context.user_data["last_filters"] = {
        "cuisine": cuisine, "area": area, "muis_only": muis_only
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Give me another one!", callback_data="another_random"),
            InlineKeyboardButton("👌 This is good, thank you!", callback_data="another_done"),
        ]
    ])
    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=keyboard
    )
    return HALAL_TYPE


async def handle_another(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "another_done":
        await query.edit_message_text(_bye())
        return ConversationHandler.END

    data = _get_data(context)
    filters = context.user_data.get("last_filters")

    if filters:
        pool = data.query(
            cuisine=filters.get("cuisine", "any"),
            area=filters.get("area", "any"),
            muis_only=filters.get("muis_only", False),
        )
    else:
        pool = data.establishments

    if not pool:
        await query.edit_message_text(_no_result_msg())
        return ConversationHandler.END

    pick = random.choice(pool)
    text = (
        f"🎉 *One more from Mak Cik!*\n\n"
        f"{_pick_exclamation()}\n\n"
        f"{_format_establishment(pick)}\n\n"
        "Still want more? Press again! 😂"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Give me another one!", callback_data="another_random"),
            InlineKeyboardButton("👌 This is good, thank you!", callback_data="another_done"),
        ]
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    return HALAL_TYPE


async def random_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Okay no problem! If you get hungry later, come find Mak Cik again okay! 😊\n"
        "Try /random or just send your location 📍"
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
# LOCATION HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_loc = update.message.location
    lat, lon = user_loc.latitude, user_loc.longitude

    data = _get_data(context)

    with_coords = sum(1 for e in data.establishments if e.has_coords)
    if with_coords == 0:
        await update.message.reply_text(
            "Alamak 😔 Mak Cik's data doesn't have GPS coordinates yet lah...\n\n"
            "Try /random or just type what you want to eat! 🍛\n"
            "Mak Cik is still processing the data, come back in a bit! 🧕"
        )
        return

    radius = context.user_data.get("nearby_radius_km", 2.0)
    max_results = context.bot_data.get("nearby_max_results", 5)

    nearby = data.nearby(lat, lon, radius_km=radius, max_results=max_results)

    if not nearby:
        nearby = data.nearby(lat, lon, radius_km=5.0, max_results=max_results)
        if nearby:
            radius_note = "Hmm, nothing within 2km… Mak Cik expanded to 5km! 😅\n\n"
        else:
            await update.message.reply_text(
                "Alamak 😭 Mak Cik searched far and wide but no halal food found near you leh…\n\n"
                "Maybe try /random? Or move to a different spot? 📍\n"
                "Or just cook yourself lah! 😂🍛"
            )
            return
    else:
        radius_note = ""

    # Build message with consistent spacing
    lines = []
    lines.append("📍 *Halal Food Near You*")
    lines.append("")

    if radius_note:
        lines.append(radius_note)
        lines.append("")

    for e, dist in nearby:
        lines.append(_format_establishment(e, distance_km=dist))
        lines.append("")  # blank line between entries

    lines.append("💡 *Tip:* Change search radius with `/nearby 3` (in km)")
    lines.append("Want Mak Cik to pick randomly? Try /random 🎲")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def nearby_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            radius = float(context.args[0])
            if 0.5 <= radius <= 20:
                context.user_data["nearby_radius_km"] = radius
                await update.message.reply_text(
                    f"Done! When you send your location, Mak Cik will search within {radius}km 📍"
                )
                return
            else:
                await update.message.reply_text(
                    "Eh, the distance must be between 0.5km and 20km lah! 📏\n"
                    "20km already reach Johor liao! 😂"
                )
                return
        except ValueError:
            pass

    current = context.user_data.get("nearby_radius_km", 2.0)
    await update.message.reply_text(
        f"📏 Right now Mak Cik searches within *{current}km* of you 📍\n\n"
        "Want to change? Just type `/nearby 3` (example: set to 3km)\n\n"
        "Or just send your location and Mak Cik will find halal food nearby! 📍\n"
        "Tap 📎 below → Location → Share current location",
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT SEARCH HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()

    if len(query_text) < 2:
        await update.message.reply_text(
            "Eh? Type a bit more lah, like \"nasi lemak\" or \"briyani\"… 😊\n"
            "Mak Cik is not a mind reader okay! 🔮"
        )
        return

    data = _get_data(context)
    results = data.search_text(query_text, max_results=5)

    if not results:
        await update.message.reply_text(
            f"Alamak, Mak Cik searched for \"{query_text}\" but cannot find anything leh 😔\n\n"
            "Try a different keyword? Or just /random lah!\n"
            "Sometimes what we want not available, but what's available is even better! 😋"
        )
        return

    lines = [f"🔍 *Results for \"{query_text}\"*", ""]

    for i, e in enumerate(results, 1):
        lines.append(f"{i}. {_format_establishment(e)}")
        lines.append("")

    lines.append("Want Mak Cik to pick randomly? Try /random 🎲")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════════
# STATS COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = _get_data(context)
    total = data.total_count
    with_coords = sum(1 for e in data.establishments if e.has_coords)

    muis_count = sum(
        1 for e in data.establishments
        if "muis" in e.halal_type.lower()
        or "certified" in e.halal_type.lower()
        or "eating establishment" in e.halal_type.lower()
        or "food preparation" in e.halal_type.lower()
    )

    geocode_pct = f"{with_coords / total * 100:.1f}%" if total else "0%"

    await update.message.reply_text(
        f"📊 *Mak Cik Fatimah's Stats*\n\n"
        f"🍛 Total halal places: *{total}*\n"
        f"📍 With GPS coordinates: *{with_coords}* ({geocode_pct})\n"
        f"✅ MUIS Certified: *{muis_count}*\n\n"
        f"Data from: *singapore-halal-establishments*\n\n"
        f"Mak Cik remembers all of them okay! 😤💪",
        parse_mode="Markdown",
    )