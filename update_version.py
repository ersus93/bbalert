#!/usr/bin/env python3
"""
Script de control de versiones para BBAlert Bot.
Incrementa automáticamente la versión al iniciar/reiniciar el bot.

Uso:
    python update_version.py [major|minor|patch]  # Incrementar versión específica
    python update_version.py --auto               # Modo automático (incrementa patch)
    python update_version.py                      # Sin argumentos (incrementa patch)
"""

import os
import argparse
import subprocess
import sys

# Configuración
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, 'version.txt')


def load_version():
    """Carga la versión actual desde version.txt."""
    if not os.path.exists(VERSION_FILE):
        # Crear archivo con versión inicial si no existe
        save_version("1.0.0")
        return "1.0.0"
    with open(VERSION_FILE, 'r') as f:
        return f.read().strip()


def save_version(version):
    """Guarda la versión en version.txt."""
    with open(VERSION_FILE, 'w') as f:
        f.write(version)


def increment_version(part='patch', silent=False):
    """
    Incrementa la versión según la parte especificada.
    
    Args:
        part: 'major', 'minor', o 'patch' (default: 'patch')
        silent: Si True, solo imprime la nueva versión (para modo automático)
    
    Returns:
        str: La nueva versión
    """
    current = load_version()
    try:
        major, minor, patch = map(int, current.split('.'))
    except ValueError:
        if not silent:
            print(f"❌ Error: El formato de versión actual '{current}' no es válido (debe ser X.Y.Z)")
        # Resetear a versión válida
        major, minor, patch = 1, 0, 0

    if part == 'major':
        major += 1
        minor = 0
        patch = 0
    elif part == 'minor':
        minor += 1
        patch = 0
    elif part == 'patch':
        patch += 1
    
    new_version = f"{major}.{minor}.{patch}"
    save_version(new_version)
    
    if silent:
        # Modo automático: salida simple para logs
        print(f"🚀 Versión: {current} → {new_version}")
    else:
        print(f"✅ Versión actualizada: {current} ➡️  {new_version}")

    # Git automático (Opcional - descomentar si se desea)
    # try:
    #     subprocess.run(["git", "add", "version.txt"], check=True)
    #     subprocess.run(["git", "commit", "-m", f"🔖 Bump version a v{new_version}"], check=True)
    #     print("✅ Git Commit creado automáticamente.")
    # except Exception as e:
    #     print(f"⚠️ No se pudo hacer commit automático: {e}")

    return new_version


def main():
    """Función principal con soporte para modo automático."""
    parser = argparse.ArgumentParser(
        description="Actualizar versión del bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python update_version.py major   # 1.0.0 → 2.0.0
    python update_version.py minor   # 1.0.0 → 1.1.0
    python update_version.py patch   # 1.0.0 → 1.0.1
    python update_version.py --auto  # Modo automático (patch)
    python update_version.py         # Sin argumentos (patch)
        """
    )
    parser.add_argument(
        'part', 
        nargs='?', 
        choices=['major', 'minor', 'patch'],
        default='patch',
        help="Qué parte de la versión subir (default: patch)"
    )
    parser.add_argument(
        '--auto', 
        action='store_true',
        help="Modo automático para inicio del bot (incrementa patch silenciosamente)"
    )
    
    args = parser.parse_args()
    
    # Modo automático: salida simplificada
    silent = args.auto
    increment_version(args.part, silent=silent)


if __name__ == "__main__":
    main()