using System.Text;

namespace Vzlom.Core;

/// <summary>
/// Mémoire persistante partagée entre TOUS les modèles IA.
/// Fichier append-only, commence vide, grandit naturellement.
/// Chaque session ajoute un bloc horodaté.
/// </summary>
public class MemoryManager
{
    private readonly string _filePath;
    private readonly int _maxContextChars = 8000; // limite pour le contexte

    public event Action<string>? OnStatus;

    public MemoryManager(string? customPath = null)
    {
        _filePath = customPath ?? Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "vzlom_memory.md");
        EnsureFile();
    }

    private void EnsureFile()
    {
        if (!File.Exists(_filePath))
        {
            File.WriteAllText(_filePath, $"# Vzlom Memory — {DateTime.Now:yyyy-MM-dd}\n\n");
            OnStatus?.Invoke($"🧠 Fichier mémoire créé: {Path.GetFileName(_filePath)}");
        }
    }

    /// <summary>
    /// Récupère la mémoire récente pour l'injecter dans le prompt système.
    /// Retourne les dernières entrées dans la limite de caractères.
    /// </summary>
    public string GetMemoryContext()
    {
        try
        {
            var content = File.ReadAllText(_filePath);
            if (content.Length <= _maxContextChars) return content;

            // Prendre la fin du fichier (mémoire la plus récente)
            return "... [début tronqué] ...\n" + content[^_maxContextChars..];
        }
        catch
        {
            return "";
        }
    }

    /// <summary>
    /// Ajoute une entrée mémoire avec horodatage automatique.
    /// Chaque modèle peut appeler ça via --memory-save--.
    /// </summary>
    public void SaveMemory(string content, string source = "user")
    {
        try
        {
            var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            var entry = $"\n--- {source} @ {timestamp} ---\n{content.Trim()}\n";
            File.AppendAllText(_filePath, entry);
            OnStatus?.Invoke($"🧠 Mémoire sauvegardée ({content.Length} chars)");
        }
        catch (Exception ex)
        {
            OnStatus?.Invoke($"❌ Erreur mémoire: {ex.Message}");
        }
    }

    /// <summary>
    /// Scanne la réponse de l'IA pour détecter les commandes mémoire.
    /// Format: --memory-save-- contenu important ici
    /// Format: --memory-forget-- identifiant
    /// </summary>
    public string? ProcessAiResponse(string response)
    {
        var saveIdx = response.IndexOf("--memory-save--");
        if (saveIdx >= 0)
        {
            var after = response[(saveIdx + 16)..].Trim();
            var end = after.IndexOf("--");
            var content = end >= 0 ? after[..end].Trim() : after;
            SaveMemory(content, "ai");
            return content;
        }
        return null;
    }

    /// <summary>
    /// Taille du fichier mémoire
    /// </summary>
    public long FileSize
    {
        get
        {
            try { return new FileInfo(_filePath).Length; }
            catch { return 0; }
        }
    }

    /// <summary>
    /// Ouvre la mémoire dans l'éditeur
    /// </summary>
    public string GetFilePath() => _filePath;

    /// <summary>
    /// Réinitialise la mémoire (garde juste l'en-tête)
    /// </summary>
    public void Clear()
    {
        File.WriteAllText(_filePath, $"# Vzlom Memory — {DateTime.Now:yyyy-MM-dd}\n\n");
        OnStatus?.Invoke("🧠 Mémoire réinitialisée");
    }
}
