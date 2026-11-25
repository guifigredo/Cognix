param([int]$Port = 8000)
$uri = "http://127.0.0.1:$Port/"
for ($i = 0; $i -lt 100; $i++) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $uri -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Start-Process $uri
            exit 0
        }
    } catch {
        # O servidor ainda esta iniciando. Tentar novamente.
    }
    Start-Sleep -Milliseconds 500
}
exit 1
