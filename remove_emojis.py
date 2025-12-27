import re

# Read the file
with open('run_screener.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define emoji patterns to remove
emoji_patterns = [
    r'🏛️',
    r'🗺️',
    r'🌍',
    r'🎁',
    r'👔',
    r'📊',
    r'📈',
    r'📉',
    r'✓',
    r'✗',
    r'✅',
    r'❌',
    r'⚠️',
    r'ℹ️',
    r'💡',
    r'➡️',
    r'→',
    r'←',
    r'↑',
    r'↓',
    r'↗️',
    r'↘️',
    r'⏸️',
    r'📅',
    r'💰',
    r'🚀',
    r'🎯',
    r'🔍',
    r'📌',
    r'⭐',
    r'🟢',
    r'🟡',
    r'🔴',
    r'💪',
    r'📝',
    r'👍',
    r'🏆',
    r'🛠️',
    r'⚖️',
    r'⬅️',
    r'⬇️',
    r'🌡️',
    r'1️⃣',
    r'2️⃣',
    r'3️⃣',
    r'4️⃣',
]

# Remove each emoji
for emoji in emoji_patterns:
    content = re.sub(emoji + r'\s*', '', content)

# Write back
with open('run_screener.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed all emojis from run_screener.py")
