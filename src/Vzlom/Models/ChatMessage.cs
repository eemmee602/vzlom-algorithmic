using System.Windows.Media;

namespace Vzlom.Models;

public enum MessageRole { User, Assistant, System, Bash, Status }

public class ChatMessage
{
    public MessageRole Role { get; set; }
    public string Content { get; set; } = "";
    public string? BashCommand { get; set; }
    public bool IsStreaming { get; set; }
    public DateTime Timestamp { get; set; } = DateTime.Now;

    public SolidColorBrush RoleColor => Role switch
    {
        MessageRole.User => new SolidColorBrush(Color.FromRgb(0, 212, 255)),
        MessageRole.Assistant => new SolidColorBrush(Color.FromRgb(0, 255, 136)),
        MessageRole.Bash => new SolidColorBrush(Color.FromRgb(255, 170, 0)),
        MessageRole.Status => new SolidColorBrush(Color.FromRgb(136, 136, 153)),
        _ => new SolidColorBrush(Color.FromRgb(224, 224, 224)),
    };
}
