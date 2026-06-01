$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$env:HELIOS_LLM_API_KEY = ''
$env:OPENAI_API_KEY = ''
$env:HELIOS_QQ_APP_ID = ''
$env:HELIOS_QQ_CLIENT_SECRET = ''
$env:HELIOS_QQ_SANDBOX = '1'

& 'D:\Compiler\anaconda3\envs\helios-test\python.exe' -m pytest -q
exit $LASTEXITCODE
