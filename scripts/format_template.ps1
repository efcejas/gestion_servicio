param(
    [Parameter(Mandatory = $true)]
    [string]$Template,

    [switch]$Check
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$templatesRoot = (Resolve-Path (Join-Path $repositoryRoot 'templates')).Path
$resolvedTemplate = (Resolve-Path -LiteralPath $Template).Path
$templatesPrefix = $templatesRoot.TrimEnd('\') + '\'

if (-not $resolvedTemplate.StartsWith($templatesPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Solo se pueden formatear archivos ubicados dentro de templates/.'
}

if ([System.IO.Path]::GetExtension($resolvedTemplate) -ne '.html') {
    throw 'El archivo debe tener extension .html.'
}

$djhtmlArguments = @('-m', 'djhtml', '--tabwidth', '4')
if ($Check) {
    $djhtmlArguments += '--check'
}
$djhtmlArguments += $resolvedTemplate

& python @djhtmlArguments
exit $LASTEXITCODE
