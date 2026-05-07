# Vzlom Algorithmic

Éditeur de scripts Roblox + Interface IA Hermès — tout-en-un.

## Faces
- **📝 Editor** : éditeur Lua/Luau avec AvalonEdit + exécution Solara
- **🤖 Hermes** : chat IA avec streaming, bash cards, permissions

## Build
```bash
dotnet build
```

## Structure
```
src/Vzlom/
├── Faces/          # EditorFace + HermesFace
├── Controls/       # BashCard, StatusBar, PermissionDialog
├── Core/           # API, Permissions, Update, Scripts
├── Theme/          # Dark theme XAML
└── Models/         # ChatMessage, PermissionRequest
```
