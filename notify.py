import os, discord, aiohttp

NTFY = os.environ["NTFY_URL"]
TOKEN = os.environ["DISCORD_TOKEN"]
ACCOUNT = os.environ.get("ACCOUNT", "?")

class C(discord.Client):
    async def on_message(self, m):
        if m.author.id == self.user.id:
            return
        dm = isinstance(m.channel, (discord.DMChannel, discord.GroupChannel))
        if not (dm or self.user.mentioned_in(m)):
            return
        where = "DM" if dm else f"#{m.channel.name}"
        async with aiohttp.ClientSession() as s:
            await s.post(NTFY, data=(m.clean_content or "[attachment]")[:500],
                         headers={"Title": f"[{ACCOUNT}] {m.author.display_name} ({where})"})

C().run(TOKEN)