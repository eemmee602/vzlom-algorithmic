using System.Text;
using Renci.SshNet;

namespace Vzlom.Core;

public class SshClient : IDisposable
{
    private Renci.SshNet.SshClient? _client;
    private bool _connected = false;

    public event Action<string, bool>? OnCommandResult; // output, isError
    public event Action<string>? OnStatus;

    public void Configure(string host, int port, string user, string auth, bool isKey = false)
    {
        if (isKey)
        {
            var keyFile = new PrivateKeyFile(auth);
            var keyFiles = new[] { keyFile };
            _client = new Renci.SshNet.SshClient(host, port, user, keyFiles);
        }
        else
        {
            _client = new Renci.SshNet.SshClient(host, port, user, auth);
        }
    }

    public bool Connect()
    {
        try
        {
            _client?.Connect();
            _connected = _client?.IsConnected ?? false;
            OnStatus?.Invoke(_connected ? "🔗 SSH connecté" : "❌ SSH échec connexion");
            return _connected;
        }
        catch (Exception ex)
        {
            OnStatus?.Invoke($"❌ SSH : {ex.Message}");
            return false;
        }
    }

    public string Execute(string command, int timeoutSec = 30)
    {
        if (_client == null || !_client.IsConnected)
        {
            OnCommandResult?.Invoke("SSH non connecté. Utilise --ssh-config-- d'abord.", true);
            return "";
        }

        OnStatus?.Invoke($"⚡ bash $ {command}");

        try
        {
            var result = new StringBuilder();

            using var cmd = _client.RunCommand(command);
            if (!string.IsNullOrEmpty(cmd.Result))
                result.Append(cmd.Result.TrimEnd());

            if (!string.IsNullOrEmpty(cmd.Error))
                result.AppendLine().Append("STDERR: ").Append(cmd.Error.TrimEnd());

            var output = result.ToString();
            OnCommandResult?.Invoke(output, !string.IsNullOrEmpty(cmd.Error));
            return output;
        }
        catch (Exception ex)
        {
            OnCommandResult?.Invoke($"Erreur: {ex.Message}", true);
            return $"Error: {ex.Message}";
        }
    }

    public void Disconnect()
    {
        _client?.Disconnect();
        _connected = false;
        OnStatus?.Invoke("🔌 SSH déconnecté");
    }

    public bool IsConnected => _connected;

    public void Dispose()
    {
        _client?.Dispose();
    }
}
