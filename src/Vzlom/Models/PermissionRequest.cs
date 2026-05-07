namespace Vzlom.Models;

public enum PermissionLevel
{
    Deny,
    AllowOnce,
    AllowSession,
    AllowAlways,
}

public enum PermissionType
{
    ReadScript,
    WriteScript,
    ExecuteCommand,
    ReadFile,
    WriteFile,
    GitPush,
    NetworkAccess,
    ModifyEditor,
}

public class PermissionEntry
{
    public PermissionType Type { get; set; }
    public PermissionLevel Level { get; set; }
    public string? Description { get; set; }
}
