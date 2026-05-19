import platform
import subprocess
from datetime import datetime
from ..config import CONFIG
from ..logger import build_logger
from ..models import DiagosticReport, Resultado_Operacao
from ..utilitarios.network import ping_host, traduzir_hostname, teste_porta_tcp
from .printer_service import PrinterService
from .spooler_service import SpoolerService

class DiagnosticsService:
    def __init__(self):
        self.logger = build_logger("Serviço de Diagnostico")
        self.printer_service = PrinterService()
        self.spooler_service = SpoolerService()
        
    def detectar_impressora(self, printer_name):
        impressoras = self.printer_service.printers_instaladas()
        match = next((p for p in impressoras if p.name == printer_name), None)
        if not match:
            return None
        port = match.port_name
        if port.startswith("IP_"):
            return port.replace("IP_", "")
        return None
    
    def run_diagnostic(self, printer_name, ip_or_host):
        alvo = ip_or_host or self.detectar_impressora(printer_name) or CONFIG.hostname_printer_padrao
        resolvido = traduzir_hostname(alvo) if not alvo.replace(".", "").isdigit() else alvo
        anotacoes = []
        if not resolvido:
            resolvido = alvo
            anotacoes.append("Não foi possivel resolver o nome do host. Usando o destino bruto.")
            
        ping_ok = ping_host(resolvido, CONFIG.ping_timeout_ms)
        if not ping_ok:
            anotacoes.append("Falha no ping.")
            
        port_ok = teste_porta_tcp(resolvido, 9100, CONFIG.timeout_port9100)
        if not port_ok:
            anotacoes.append("Porta 9100 inacessível")
            
        spooler_running = self.spooler_service.verifica_spooler()
        if not spooler_running:
            anotacoes.append("O Spooler está parado.")
            
        online = ping_ok and port_ok and spooler_running
        if online:
            anotacoes.append("Impressora online.") 
        return DiagosticReport(
            nome_impressora=printer_name,
            ip=resolvido,
            ping_ok=ping_ok,
            porta_9100_ok=port_ok,
            spooler_rodando=spooler_running,
            printer_online=online,
            anotacoes=anotacoes,
        ) 
        
    def ping_continuo(self, host, count):
        return [ping_host(host, CONFIG.ping_timeout_ms) for _ in range(count)]
    
    def test_print(self, printer_name):
        script = (
            "$p = Get-Printer -Name '{name}' -ErrorAction SilentlyContinue; "
            "if ($null -eq $p) {{ exit 2 }}; "
            "Start-Process -FilePath notepad.exe -ArgumentList '/p' -PassThru | Out-Null"
        ).format(name=printer_name.replace("'", "''"))
        completado = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if completado.returncode != 0:
            return Resultado_Operacao(False, "Falha no comando para teste de impressão.")
        return Resultado_Operacao(True, "Teste de impressão acionado.")
    
    def relatorio_tecnico(self, report):
        path = CONFIG.log_dir / f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        payload = [
            f"App: {CONFIG.app_name}",
            f"OS: {platform.platform()}",
            f"Printer: {report.nome_impressora}",
            f"Target IP: {report.ip}",
            f"Ping: {'OK' if report.ping_ok else 'ERRO'}",
            f"Porta 9100: {'OK' if report.porta_9100_ok else 'ERRO'}",
            f"Spooler: {'RODANDO' if report.spooler_rodando else 'PARADO'}",
            f"Online: {'SIM' if report.printer_online else 'NÃO'}",
            "Anotacoes",
            *[f"- {item}" for item in report.anotacoes],
        ]
        try:
            path.write_text("\n".join(payload), encoding="utf-8")
            return Resultado_Operacao(True, "Relatório tecnico gerado.", {"path": str(path)})
        except Exception as exc:
            self.logger.exception("Falha na geração do relatório.")
            return Resultado_Operacao(False, f"Falha na geração do relatório: {exc}")
