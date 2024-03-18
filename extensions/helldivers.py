from __future__ import annotations

import asyncio
import random
import time
from typing import TYPE_CHECKING, ClassVar, NamedTuple

from discord.ext import commands

if TYPE_CHECKING:
    import discord

    from bot import Mipha
    from utilities.context import Context

# W A S D input
EMOJI = {
    "w": "<:HDUp:1216530187076894730>",
    "s": "<:HDDown:1216530232031580270>",
    "d": "<:HDRight:1216530291401687141>",
    "a": "<:HDLeft:1216530265363451904>",
}
HJKL_INPUT = {
    "k": "w",
    "j": "s",
    "l": "d",
    "h": "a",
}
HJKL_INPUT_REV = {v: k for k, v in HJKL_INPUT.items()}
HJKL_TRANSLATE = str.maketrans(HJKL_INPUT)


def _translate_wasd_hjkl(input_: str) -> str:
    return input_.translate(HJKL_TRANSLATE)


class GameElapsed(commands.CommandError):
    pass


class Strategem(NamedTuple):
    name: str
    input: str

    @property
    def emoji(self) -> list[str]:
        return [EMOJI[char] for char in self.input]

    @property
    def hjkl(self) -> str:
        return "".join([HJKL_INPUT_REV[char] for char in self.input])

    def clean_emoji(self) -> str:
        return " ".join(self.emoji)


class StrategemGame:
    STRATEGEMS: ClassVar[list[Strategem]] = [
        # region: support
        Strategem("Resupply", input="sswd"),
        Strategem("Reinforce", input="wsdaw"),
        # Strategem("Eagle Rearm", input=""),
        Strategem("NUX-223 Hellbomb", input="swaswdsw"),
        # endregion: support
        # region: backpacks
        Strategem("AX/LAS-5 'Guard Dog' Rover", input="swawdd"),
        Strategem("AD-334 Guard Dog", input="swawds"),
        Strategem("LIFT-850 Jump Pack", input="swwsw"),
        Strategem("B-1 Supply Pack", input="swssd"),
        Strategem("SH-32 Shield Generator Pack", input="swadad"),
        Strategem("SH-20 Ballistic Shield Backpack", input="sasswa"),
        # endregion: backpacks
        # region: secondaries
        Strategem("AC-8 Autocannon", input="saswwd"),
        Strategem("EAT-17 Expendable Anti-Tank", input="sadws"),
        Strategem("FLAM-40 'Incinerator' Flamethrower", input="sasda"),
        Strategem("LAS-98 Laser Cannon", input="saswa"),
        Strategem("M-105 Stalwart", input="saswwa"),
        Strategem("MG-43 Machine Gun", input="saswd"),
        Strategem("ARC-3 Arc Thrower", input="sdswaa"),
        Strategem("GL-21 Grenade Launcher", input="sawas"),
        Strategem("APW-1 Anti-Materiel Rifle", input="sadws"),
        Strategem("RS-422 Railgun", input="sdswad"),
        Strategem("GR-8 Recoilless Rifle", input="sadda"),
        Strategem("FAF-14 Spear", input="saswwd"),
        # endregion: secondaries
        # region: vehicles
        Strategem("EXO-45 Patriot Exosuit", input="asdwass"),
        # endregion: vehicles
        # region: defensive
        # endregion: defensive
        # region: orbital
        # endregion: orbital
        # region: eagle
        # endregion: eagle
    ]
    start_time: float
    end_time: float
    last_success: float
    _total_reductions: float

    __slots__ = (
        "owner",
        "strategems",
        "resolutions",
        "start_time",
        "end_time",
        "last_success",
        "_total_reductions",
    )

    def __init__(self, *, owner: int, limit: int) -> None:
        self.owner: int = owner
        self.strategems: list[Strategem] = self._choose_strategems(limit)
        self.resolutions: list[tuple[int, float]] = []
        self._total_reductions: float = 0

    def _choose_strategems(self, limit: int) -> list[Strategem]:
        return random.choices(self.STRATEGEMS, k=limit)

    def total_time(self) -> float:
        return round(sum(r[1] for r in self.resolutions) - self._total_reductions, 2)


class Helldivers(commands.Cog):
    def __init__(self, bot: Mipha, /) -> None:
        self.bot: Mipha = bot

    async def _sender(self, ctx: Context, /, game: StrategemGame) -> None:
        for idx, item in enumerate(game.strategems):
            await ctx.send(f"## {item.name} :: {item.clean_emoji()}")
            if idx == 0:
                game.start_time = time.time()
                game.last_success = game.start_time

            pre_game = time.perf_counter()
            message: discord.Message = await self.bot.wait_for(
                "message",
                check=lambda m: m.author.id == game.owner
                and m.channel.id == ctx.channel.id
                and m.content
                and _translate_wasd_hjkl(m.content.casefold()) == item.input,
                timeout=45,
            )
            after_game = time.perf_counter()
            game.resolutions.append((idx, after_game - pre_game))
            game.last_success = time.time()
            await message.add_reaction(ctx.tick(True))

    async def _game_handler(self, ctx: Context, amount: int, /) -> StrategemGame:
        game = StrategemGame(owner=ctx.author.id, limit=amount)
        try:
            await asyncio.wait_for(self._sender(ctx, game), timeout=45)
        except TimeoutError:
            raise GameElapsed()
        game.end_time = time.time()

        return game

    def _resolve_avg_time(self, start_time: float, input_: str, resolution: tuple[int, float]) -> tuple[float, float]:
        taken = resolution[1] - start_time
        avg_per_char = taken / len(input_)

        return taken, avg_per_char

    @commands.group(name="strategem", aliases=["strats", "hero"], invoke_without_command=True)
    async def strategem_input(self, ctx: Context, limit: int = 5) -> None:
        """
        Start a game of strategem input.
        """
        if ctx.invoked_subcommand:
            return

        limit = min(max(limit, 3), 10)

        try:
            game = await self._game_handler(ctx, limit)
        except GameElapsed:
            return await ctx.send("Sorry, your time to create liberty has elapsed.")

        results: list[str] = []
        for idx, (strategem, resolution) in enumerate(zip(game.strategems, game.resolutions), start=1):
            avg_per_character = resolution[1] / len(strategem.input) + 1
            results.append(
                f"{idx}. {strategem.name} ({strategem.clean_emoji()}) :: **{round(resolution[1]-avg_per_character, 2)} seconds**."
            )

        results.insert(0, f"Total game time taken was **{game.total_time()} seconds**.")
        results.insert(1, "\n")
        await ctx.send("\n".join(results))

    @strategem_input.command(name="example")
    async def strategem_example(self, ctx: Context, /) -> None:
        """
        Shows the example and how to play the strategem input game.
        """
        game = StrategemGame(owner=ctx.author.id, limit=1)

        strategem = random.choice(game.strategems)

        await ctx.send(
            "An example run of the game is that we send the name and input for the strategem:-"
            f"\n## {strategem.name} :: {strategem.clean_emoji()}"
            f"\nYou would then send the WASD/HJKL equivalent input as a message, like so:-\n### {strategem.input} // {strategem.hjkl}"
            "\nand this would be counted and recorded if correct. An emoji will be added when correct. We average the time taken per keystroke to remove the one used to hit 'enter'."
            f"\n\nNow you can the game with '{ctx.clean_prefix}{ctx.invoked_parents[0]}'"
        )


async def setup(bot: Mipha, /) -> None:
    await bot.add_cog(Helldivers(bot))
