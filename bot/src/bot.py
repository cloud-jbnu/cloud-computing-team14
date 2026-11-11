"""디스코드 봇 뼈대. 구독 저장은 DynamoDB 설계가 정해지면 연결합니다."""
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# TODO: DynamoDB(SUBSCRIPTIONS_TABLE)로 교체
subscriptions: dict[int, set[str]] = {}


@tree.command(name="구독", description="키워드를 구독합니다")
async def subscribe(interaction: discord.Interaction, 키워드: str):
    subscriptions.setdefault(interaction.user.id, set()).add(키워드)
    await interaction.response.send_message(f"`{키워드}` 구독을 시작했어요.", ephemeral=True)


@tree.command(name="해지", description="키워드 구독을 해지합니다")
async def unsubscribe(interaction: discord.Interaction, 키워드: str):
    subscriptions.get(interaction.user.id, set()).discard(키워드)
    await interaction.response.send_message(f"`{키워드}` 구독을 해지했어요.", ephemeral=True)


@tree.command(name="목록", description="내 구독 목록을 봅니다")
async def list_subs(interaction: discord.Interaction):
    subs = subscriptions.get(interaction.user.id) or set()
    text = ", ".join(sorted(subs)) if subs else "구독한 키워드가 없어요."
    await interaction.response.send_message(text, ephemeral=True)


@client.event
async def on_ready():
    await tree.sync()
    print(f"로그인: {client.user}")


if __name__ == "__main__":
    client.run(os.environ["DISCORD_BOT_TOKEN"])
