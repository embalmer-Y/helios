$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

# Live mode intentionally keeps .env-provided credentials.
& 'D:\Compiler\anaconda3\envs\helios-test\python.exe' -m pytest tests/test_channel_gateway.py tests/test_qq_channel.py tests/test_response_pipeline.py tests/test_memory_in_llm_context.py -q
exit $LASTEXITCODE
