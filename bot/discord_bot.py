"""Bot do Discord — comandos do time no canal Projeto Agente Midia Paga.

Comandos:
  /report   — resumo das campanhas (semana atual)
  /status   — campanhas ativas e orcamento
  /budget   — gasto vs limite do mes
  /pendentes — recomendacoes aguardando aprovacao
  /aprovar <id> — aprova e executa (so autorizados)
  /rejeitar <id> — rejeita (so autorizados)

A lista de aprovadores fica na variavel DISCORD_APPROVER_IDS
(IDs de usuario do Discord separados por virgula).
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from discord import app_commands

from src import approvals, config
from src.report_builder import build_report_for_period

APPROVER_IDS = {
    int(x) for x in os.getenv("DISCORD_APPROVER_IDS", "").split(",") if x.strip()
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def _is_approver(user: discord.User) -> bool:
    return user.id in APPROVER_IDS


def _channel_check(interaction: discord.Interaction) -> bool:
    cid = config.DISCORD_CHANNEL_ID
    return not cid or str(interaction.channel_id) == cid


@tree.command(name="report", description="Resumo das campanhas da semana atual")
async def report(interaction: discord.Interaction):
    if not _channel_check(interaction):
        await interaction.response.send_message("Use este comando no canal do projeto.", ephemeral=True)
        return
    await interaction.response.defer()
    today = date.today()
    start = today - timedelta(days=today.weekday())
    body = build_report_for_period(start, today)
    await interaction.followup.send(f"```\n{body}\n```")


@tree.command(name="pendentes", description="Recomendações aguardando aprovação")
async def pendentes(interaction: discord.Interaction):
    if not _channel_check(interaction):
        await interaction.response.send_message("Use este comando no canal do projeto.", ephemeral=True)
        return
    await interaction.response.defer()
    items = approvals.list_pending()
    if not items:
        await interaction.followup.send("✅ Nenhuma recomendação pendente.")
        return
    lines = ["**Recomendações pendentes:**"]
    for it in items:
        lines.append(
            f"`#{it['row']}` — **{it['campaign']}**\n"
            f"  {it['action']}\n  Motivo: {it['reason']}"
        )
    lines.append("\nUse `/aprovar id` ou `/rejeitar id`.")
    await interaction.followup.send("\n".join(lines))


@tree.command(name="aprovar", description="Aprova e executa uma recomendação")
@app_commands.describe(id="Número da recomendação (veja /pendentes)")
async def aprovar(interaction: discord.Interaction, id: int):
    if not _is_approver(interaction.user):
        await interaction.response.send_message(
            "🚫 Você não está na lista de aprovadores.", ephemeral=True
        )
        return
    await interaction.response.defer()
    result = approvals.approve(id, approver=str(interaction.user))
    await interaction.followup.send(f"✅ {result}")


@tree.command(name="rejeitar", description="Rejeita uma recomendação")
@app_commands.describe(id="Número da recomendação (veja /pendentes)")
async def rejeitar(interaction: discord.Interaction, id: int):
    if not _is_approver(interaction.user):
        await interaction.response.send_message(
            "🚫 Você não está na lista de aprovadores.", ephemeral=True
        )
        return
    await interaction.response.defer()
    result = approvals.reject(id, approver=str(interaction.user))
    await interaction.followup.send(f"❌ {result}")


@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot conectado como {client.user}")


if __name__ == "__main__":
    client.run(config.DISCORD_BOT_TOKEN)
