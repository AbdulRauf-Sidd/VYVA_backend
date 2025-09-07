#!/usr/bin/env python3
"""
Logging Control Script for Vyva Backend

This script helps you easily control logging settings.
"""

import os
import sys
from pathlib import Path

def update_env_file(setting: str, value: str):
    """Update a setting in the .env file"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ .env file not found!")
        return False
    
    # Read current content
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Update or add the setting
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{setting}="):
            lines[i] = f"{setting}={value}\n"
            updated = True
            break
    
    if not updated:
        lines.append(f"{setting}={value}\n")
    
    # Write back to file
    with open(env_file, 'w') as f:
        f.writelines(lines)
    
    print(f"✅ Updated {setting}={value}")
    return True

def show_current_settings():
    """Show current logging settings"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ .env file not found!")
        return
    
    print("📋 Current Logging Settings:")
    print("-" * 40)
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if any(setting in line for setting in ['ENABLE_FILE_LOGGING', 'ENABLE_REQUEST_LOGGING', 'LOG_LEVEL']):
                print(f"  {line}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("🔧 Vyva Backend Logging Control")
        print("=" * 40)
        print("Usage:")
        print("  python logging_control.py show                    # Show current settings")
        print("  python logging_control.py file on|off            # Enable/disable file logging")
        print("  python logging_control.py requests on|off        # Enable/disable request logging")
        print("  python logging_control.py level DEBUG|INFO|WARN  # Set log level")
        print("  python logging_control.py all on|off             # Enable/disable all logging")
        print()
        show_current_settings()
        return
    
    command = sys.argv[1].lower()
    
    if command == "show":
        show_current_settings()
    
    elif command == "file":
        if len(sys.argv) < 3:
            print("❌ Please specify 'on' or 'off'")
            return
        value = "true" if sys.argv[2].lower() == "on" else "false"
        update_env_file("ENABLE_FILE_LOGGING", value)
        print("🔄 Restart your server to apply changes!")
    
    elif command == "requests":
        if len(sys.argv) < 3:
            print("❌ Please specify 'on' or 'off'")
            return
        value = "true" if sys.argv[2].lower() == "on" else "false"
        update_env_file("ENABLE_REQUEST_LOGGING", value)
        print("🔄 Restart your server to apply changes!")
    
    elif command == "level":
        if len(sys.argv) < 3:
            print("❌ Please specify log level (DEBUG, INFO, WARN, ERROR)")
            return
        level = sys.argv[2].upper()
        if level not in ["DEBUG", "INFO", "WARN", "ERROR"]:
            print("❌ Invalid log level. Use: DEBUG, INFO, WARN, ERROR")
            return
        update_env_file("LOG_LEVEL", level)
        print("🔄 Restart your server to apply changes!")
    
    elif command == "all":
        if len(sys.argv) < 3:
            print("❌ Please specify 'on' or 'off'")
            return
        value = "true" if sys.argv[2].lower() == "on" else "false"
        update_env_file("ENABLE_FILE_LOGGING", value)
        update_env_file("ENABLE_REQUEST_LOGGING", value)
        print("🔄 Restart your server to apply changes!")
    
    else:
        print("❌ Unknown command. Use 'python logging_control.py' to see usage.")

if __name__ == "__main__":
    main()
