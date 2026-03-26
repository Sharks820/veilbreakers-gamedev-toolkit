# VB Bridge runner - wraps Python to ensure stdout capture works with Desktop Commander
# Usage: . .\run_bridge.ps1 <args>
# Example: . .\run_bridge.ps1 blender get_scene_info
# Example: . .\run_bridge.ps1 blender create_object mesh_type=cube position=[0,0,1]

$pyExe = 'C:\Users\Conner\AppData\Local\Programs\Python\Python312\python.exe'
$bridge = 'C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\Tools\cowork_bridge\vb_bridge.py'
$allArgs = "-u `"$bridge`" " + ($args -join ' ')

$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = $pyExe
$pinfo.Arguments = $allArgs
$pinfo.RedirectStandardOutput = $true
$pinfo.RedirectStandardError = $true
$pinfo.UseShellExecute = $false
$pinfo.WorkingDirectory = Split-Path $bridge

$p = [System.Diagnostics.Process]::Start($pinfo)
$stdout = $p.StandardOutput.ReadToEnd()
$stderr = $p.StandardError.ReadToEnd()
$p.WaitForExit()

if ($stdout) { Write-Host $stdout }
if ($stderr) { Write-Host "ERR: $stderr" }
exit $p.ExitCode
