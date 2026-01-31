#!/usr/bin/env python3
"""PERCIA v2.0 - CLI Principal"""
import click, json, sys
from pathlib import Path
from datetime import datetime

@click.group()
def cli():
    """PERCIA v2.0 CLI"""
    pass

@cli.command()
def init():
    """Inicializa sistema PERCIA"""
    click.echo("🚀 Inicializando PERCIA v2.0...")
    click.echo("Por favor, usa la interfaz web (manual/index.html) para una mejor experiencia")
    click.echo("O edita templates/bootstrap_template.json manualmente")

@cli.command()
def status():
    """Muestra estado del sistema"""
    snapshot_file = Path("mcp/snapshot.json")
    if not snapshot_file.exists():
        click.echo("❌ Sistema no inicializado")
        return
    
    with open(snapshot_file, 'r') as f:
        snapshot = json.load(f)
    
    click.echo(f"🔄 Ciclo: {snapshot['cycle']['current']}")
    click.echo(f"   Estado: {snapshot['cycle']['status']}")
    click.echo(f"📝 Propuestas: {len(snapshot.get('proposals_active', []))}")
    click.echo(f"⚔️  Challenges: {len(snapshot.get('challenges_active', []))}")

if __name__ == '__main__':
    cli()
