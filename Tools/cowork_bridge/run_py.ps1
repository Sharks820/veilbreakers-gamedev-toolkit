# Run arbitrary Python code with vb_bridge pre-imported
# Usage: . .\run_py.ps1 "blender('create_object', mesh_type='cube')"
# Usage: . .\run_py.ps1 "print(scene_info())"

param([string]$code)

$pyExe = 'C:\Users\Conner\AppData\Local\Programs\Python\Python312\python.exe'
$bridgeDir = 'C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\cowork_bridge'

$fullCode = @"
import sys, os, json
sys.path.insert(0, r'$bridgeDir')
from vb_bridge import *
$code
"@

$tmpFile = [System.IO.Path]::GetTempFileName() + '.py'
$fullCode | Out-File -FilePath $tmpFile -Encoding utf8

$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = $pyExe
$pinfo.Arguments = "-u `"$tmpFile`""
$pinfo.RedirectStandardOutput = $true
$pinfo.RedirectStandardError = $true
$pinfo.UseShellExecute = $false

$p = [System.Diagnostics.Process]::Start($pinfo)
$stdout = $p.StandardOutput.ReadToEnd()
$stderr = $p.StandardError.ReadToEnd()
$p.WaitForExit()

Remove-Item $tmpFile -ErrorAction SilentlyContinue

if ($stdout) { Write-Host $stdout }
if ($stderr) { Write-Host "ERR: $stderr" }
exit $p.ExitCode
