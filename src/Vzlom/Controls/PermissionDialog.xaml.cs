using System.Windows;
using Vzlom.Models;

namespace Vzlom.Controls;

public partial class PermissionDialog : Window
{
    private readonly TaskCompletionSource<PermissionLevel> _tcs;

    public PermissionDialog(string description, TaskCompletionSource<PermissionLevel> tcs)
    {
        InitializeComponent();
        DataContext = new { Description = description };
        _tcs = tcs;
    }

    private void OnChoice(object sender, RoutedEventArgs e)
    {
        var btn = (System.Windows.Controls.Button)sender;
        var tag = btn.Tag?.ToString() ?? "Deny";
        var level = tag switch
        {
            "AllowOnce" => PermissionLevel.AllowOnce,
            "AllowSession" => PermissionLevel.AllowSession,
            "AllowAlways" => PermissionLevel.AllowAlways,
            _ => PermissionLevel.Deny,
        };
        _tcs.SetResult(level);
        Close();
    }
}
