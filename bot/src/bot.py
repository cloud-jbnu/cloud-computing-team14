"""디스코드 봇을 내 컴퓨터에서 켜 두는 방식 (Lambda를 배포하지 않고 명령어를 시험할 때).

배포한 뒤에는 interactions.py(Lambda)가 명령어를 받으므로 이 파일은 켜지 않아도 됩니다.
개발자 포털에 Interactions Endpoint URL을 등록해 두면 명령어가 그쪽으로만 가서, 이 프로그램에는 오지 않습니다.

구독은 interactions.py와 똑같이 DynamoDB(SUBSCRIPTIONS_TABLE)에 저장합니다 (subscriptions.py).
.env에 DISCORD_BOT_TOKEN, SUBSCRIPTIONS_TABLE(배포 Outputs의 SubscriptionsTableName)과 AWS 자격 증명이 필요합니다.
"""
import asyncio
import os

import boto3
import discord
from discord import app_commands
from dotenv import load_dotenv

import subscriptions

load_dotenv()

client = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)
table = boto3.resource("dynamodb").Table(os.environ["SUBSCRIPTIONS_TABLE"])


async def answer(interaction, command, keyword=None):
    user_id = str(interaction.user.id)
    try:
        # boto3는 응답을 기다리는 동안 멈추므로 다른 스레드에서 돌려 봇이 멎지 않게 합니다.
        text = await asyncio.to_thread(subscriptions.reply, table, command, user_id, keyword)
    except Exception as e:
        print(f"명령어 처리 실패 ({command}): {e}")
        text = "구독 정보를 처리하지 못했어요. 잠시 뒤 다시 해 주세요."
    await interaction.response.send_message(text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@tree.command(name="구독", description="키워드를 구독합니다")
async def subscribe(interaction: discord.Interaction, 키워드: str):
    await answer(interaction, "구독", 키워드)


@tree.command(name="해지", description="키워드 구독을 해지합니다")
async def unsubscribe(interaction: discord.Interaction, 키워드: str):
    await answer(interaction, "해지", 키워드)


@tree.command(name="목록", description="내 구독 목록을 봅니다")
async def list_subs(interaction: discord.Interaction):
    await answer(interaction, "목록")


@client.event
async def on_ready():
    await tree.sync()
    print(f"로그인: {client.user}")


if __name__ == "__main__":
    client.run(os.environ["DISCORD_BOT_TOKEN"])
